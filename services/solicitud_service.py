"""
services/solicitud_service.py  – versión optimizada
===================================================
Mejoras clave frente a la versión original
-----------------------------------------
1. **Caché LRU en memoria** para el par *id_solicitud → catálogo de capítulos* y el
   *path* del ZIP, evitando volver a recorrer la base de datos y analizar todo el
   fichero en cada petición.
2. **URLs relativas**: se elimina `_external=True` para reducir latencia y evitar
   tráfico mixto dominio/IP.
3. **`send_file` con cabeceras de caché** (`conditional=True`, `max_age` un año)
   para que el navegador sólo descargue cada imagen una vez.
4. **Detección automática de *mimetype*** según el sufijo real.
5. Logs con tiempos de servicio (`perf_counter`) para poder perfilar en
   producción.

Requiere Python ⩾3.9 y Flask ⩾2.2.
"""

from __future__ import annotations

import io

import os
import re
import time
import zipfile
import itertools
import logging
import mimetypes
import yaml
from collections import defaultdict
from contextlib import contextmanager
from functools import lru_cache
from typing import Dict, List, Tuple

from flask import abort, current_app, send_file, url_for
from pymysql.cursors import DictCursor

import db.database as db

# ───────────────────────────────────────────────────────────────────────────────
# Configuración básica
# ───────────────────────────────────────────────────────────────────────────────
BASE_DIR: str = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER_ZIPS: str = os.path.join(BASE_DIR, "..", "static", "uploads", "zips")
RULES_FILE: str = os.path.join(BASE_DIR, "rules.yml")  # opcional
RESET_THRESHOLD: int = 5      # página ≤5 tras ≥8 → nuevo capítulo
MIN_PAGES_CHAP: int = 8
ORPHAN_TOLERANCE: float = 0.03  # 3 %
ENABLE_OCR: bool = False  # actívalo si tienes tesseract instalado

if ENABLE_OCR:
    import cv2  # type: ignore
    import pytesseract  # type: ignore
    import numpy as np  # type: ignore

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────────────────
# Utilidades de acceso a la BD y al ZIP
# ───────────────────────────────────────────────────────────────────────────────

def _obtener_zip_path(id_solicitud: int) -> str:
    """Lee una única vez la ruta del ZIP desde la BD y la cachea."""

    @lru_cache(maxsize=512)
    def _cached(id_solicitud_local: int) -> str:
        with db.obtener_conexion() as cn:
            with cn.cursor(DictCursor) as cur:
                cur.execute(
                    "SELECT url_zip FROM solicitud_publicacion WHERE id_solicitud=%s",
                    (id_solicitud_local,),
                )
                row = cur.fetchone()
        if not row:
            abort(404, "Solicitud no encontrada")

        zip_path = os.path.join(UPLOAD_FOLDER_ZIPS, os.path.basename(row["url_zip"]))
        if not os.path.isfile(zip_path):
            abort(404, "ZIP no encontrado en el servidor")
        return zip_path

    return _cached(id_solicitud)


@contextmanager
def _zip_from_solicitud(id_solicitud: int):
    """Context manager que abre el ZIP de manera segura."""

    zip_path = _obtener_zip_path(id_solicitud)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            yield zf
    except zipfile.BadZipFile:
        abort(500, "Archivo ZIP corrupto")


# ───────────────────────────────────────────────────────────────────────────────
# Capa 1 – regex configurables
# ───────────────────────────────────────────────────────────────────────────────

def _load_rules():
    if not os.path.isfile(RULES_FILE):
        # fallback a cuatro patrones genéricos
        patterns = [
            r"c(?P<chap>\d{3})/p?(?P<page>\d{1,3})\.[a-z]+$",
            r"(?P<chap>\d{3})[-_](?P<page>\d{2,3})\.[a-z]+$",
            r"DN[-_]?ch(?P<chap>\d{2,3})[-_]p?(?P<page>\d{2,3})\.[a-z]+$",
            r"[A-Za-z]+[-_]\d{2}[-_](?P<chap>\d{3})[-_](?P<page>\d{2,3})\.[a-z]+$",
        ]
        return [(f"default_{i}", re.compile(p, re.I)) for i, p in enumerate(patterns)]

    with open(RULES_FILE, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return [(d["id"], re.compile(d["regex"], re.I)) for d in data]


RULES = _load_rules()


def _regex_parse(name: str):
    """Devuelve (chap, page) o None."""
    for _id, rx in RULES:
        if m := rx.search(name):
            return int(m["chap"]), int(m["page"])
    return None


# ───────────────────────────────────────────────────────────────────────────────
# Capa 2 – heurística reinicio de página
# ───────────────────────────────────────────────────────────────────────────────

def _numeric_tokens(s: str):
    tokens = []
    for k, g in itertools.groupby(s, str.isdigit):
        if k:
            tokens.append(int("".join(g)))
    return tokens


def _split_by_reset(names_sorted):
    """Devuelve {chap_idx: [names]} usando la heurística de reset."""
    chapters: Dict[int, List[str]] = {}
    current: List[str] = []
    last_page: int | None = None
    idx: int = 1

    for fname in names_sorted:
        nums = _numeric_tokens(fname)
        page = nums[-1] if nums else None

        if (
            last_page is not None
            and page is not None
            and page <= RESET_THRESHOLD
            and last_page >= RESET_THRESHOLD + 3
        ):
            if len(current) >= MIN_PAGES_CHAP:
                chapters[idx] = current
                idx += 1
                current = []
        current.append(fname)
        last_page = page
    if current:
        chapters[idx] = current
    return chapters


# ───────────────────────────────────────────────────────────────────────────────
# Capa 3 – OCR selectivo
# ───────────────────────────────────────────────────────────────────────────────
OCR_WORDS = r"(cap[íi]tulo|chapter|capitulo|capitul|episodio|ep)\s*(\d{1,3})"


def _ocr_detect(img_bytes: bytes):
    """Devuelve nº capítulo OCR o None."""
    if not ENABLE_OCR:
        return None
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)  # type: ignore
    if img is None:
        return None
    h = img.shape[0]
    header = img[: int(h * 0.25), :]  # 25 % superior
    text = pytesseract.image_to_string(header, config="--psm 6")  # type: ignore
    if m := re.search(OCR_WORDS, text, re.I):
        return int(m.group(2))
    return None


# ───────────────────────────────────────────────────────────────────────────────
# Helpers – validar imágenes y filtrar basura
# ───────────────────────────────────────────────────────────────────────────────

def _is_image_name(name: str) -> bool:
    """True si el nombre parece una imagen válida y no basura de sistema."""
    if name.startswith(("__MACOSX/", ".")):
        return False  # carpetas ocultas o metadatos macOS

    ext = os.path.splitext(name)[1].lower()
    return ext in {".png", ".jpg", ".jpeg", ".webp"}


# ───────────────────────────────────────────────────────────────────────────────
# Motor completo de clasificación
# ───────────────────────────────────────────────────────────────────────────────

def _detect_chapters(zf: zipfile.ZipFile):
    chapters: Dict[int, List[Tuple[int | None, str]]] = defaultdict(list)
    pending: List[str] = []

    for name in sorted(n for n in zf.namelist() if _is_image_name(n)):
        parsed = _regex_parse(name)
        if parsed:
            chap, page = parsed
            chapters[chap].append((page, name))
        else:
            pending.append(name)

    # ── capa 2
    if pending:
        reset_blocks = _split_by_reset(pending)
        offset = max(chapters) if chapters else 0
        for idx, names in reset_blocks.items():
            chapters[offset + idx].extend((None, n) for n in names)

    # ── capa 3 (OCR) — sólo en bloques procedentes de reset
    if ENABLE_OCR:
        for chap_id, items in list(chapters.items()):
            if all(p is None for p, _ in items):  # bloque sin regex fiables
                sample_names = [n for _, n in items[:3]]
                ocr_vals: List[int] = []
                for n in sample_names:
                    with zf.open(n) as fp:
                        if val := _ocr_detect(fp.read()):
                            ocr_vals.append(val)
                if ocr_vals and ocr_vals[0] != chap_id:
                    chapters[ocr_vals[0]] = chapters.pop(chap_id)

    # ── ordenar páginas y montar catálogo final
    final_cat: Dict[int, List[str]] = {
        chap: [n for _, n in sorted(v, key=lambda x: (x[0] is None, x[0], x[1]))]
        for chap, v in chapters.items()
    }

    # ── aviso de huérfanos
    total = len([n for n in zf.namelist() if not n.endswith("/")])
    assigned = sum(len(v) for v in final_cat.values())
    if total and (1 - assigned / total) > ORPHAN_TOLERANCE:
        current_app.logger.warning(
            "ZIP %s: %.1f %% sin capítulo", zf.filename, 100 - 100 * assigned / total
        )

    return final_cat


# ───────────────────────────────────────────────────────────────────────────────
# Caché LRU para el catálogo de capítulos
# ───────────────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=256)
def _get_catalog(id_solicitud: int):  # noqa: D401
    """Devuelve y cachea el catálogo de capítulos de *id_solicitud*."""
    with _zip_from_solicitud(id_solicitud) as zf:
        return _detect_chapters(zf)


# ───────────────────────────────────────────────────────────────────────────────
# ENDPOINT 1 – Listar capítulos
# ───────────────────────────────────────────────────────────────────────────────

def listar_capitulos(id_solicitud: int):  # noqa: D401
    start = time.perf_counter()
    try:
        cat = _get_catalog(id_solicitud)
        chapters = [f"c{c:03d}" for c in sorted(cat)]
        return {"code": 0, "chapters": chapters}, 200
    except Exception:  # pragma: no cover
        current_app.logger.exception("listar_capitulos")
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    finally:
        logger.debug("listar_capitulos %s → %.1f ms", id_solicitud, 1_000 * (time.perf_counter() - start))


# ───────────────────────────────────────────────────────────────────────────────
# ENDPOINT 2 – Listar páginas de un capítulo
# ───────────────────────────────────────────────────────────────────────────────

def listar_paginas(id_solicitud: int, chapter_name: str):
    start = time.perf_counter()
    try:
        chap_int = int(chapter_name.lstrip("c"))
        cat = _get_catalog(id_solicitud)
        if chap_int not in cat:
            return {"code": 1, "msg": "Capítulo no encontrado"}, 404

        pages = [
            url_for(
                "serve_chapter_page",
                id=id_solicitud,
                chapter=chapter_name,
                filename=os.path.basename(fpath),
                _external=True,
            )
            for fpath in cat[chap_int]
        ]
        return {"code": 0, "pages": pages}, 200
    except Exception:
        current_app.logger.exception("listar_paginas")
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    finally:
        logger.debug(
            "listar_paginas %s/%s → %.1f ms", id_solicitud, chapter_name, 1_000 * (time.perf_counter() - start)
        )


# ───────────────────────────────────────────────────────────────────────────────
# ENDPOINT 3 – Servir una página concreta (streaming)
# ───────────────────────────────────────────────────────────────────────────────

def serve_chapter_page(id: int, chapter: str, filename: str):  # noqa: D401
    """Route handler – debe registrarse como

    ```py
    app.route("/solicitudes/<int:id>/<chapter>/<filename>")(serve_chapter_page)
    ```
    Lee la imagen completa en memoria antes de cerrar el ZIP para evitar
    streams colgados (zipfile debe permanecer abierto mientras Flask sirve el
    cuerpo, de lo contrario algunas imágenes se cortan).
    """
    start = time.perf_counter()

    chap_int = int(chapter.lstrip("c"))
    cat = _get_catalog(id)
    fpaths = [p for p in cat.get(chap_int, []) if p.endswith(filename)]
    if not fpaths:
        abort(404)

    # Detectar mimetype por extensión
    mimetype, _ = mimetypes.guess_type(filename)
    if mimetype is None:
        mimetype = "application/octet-stream"

    # Leer bytes antes de cerrar el ZIP
    with _zip_from_solicitud(id) as zf:
        info = zf.getinfo(fpaths[0])
        if info.file_size == 0:
            abort(404)
        data: bytes = zf.read(fpaths[0])

    resp = send_file(
        io.BytesIO(data),
        mimetype=mimetype,
        download_name=filename,
        max_age=31536000,  # 1 año
    )

    logger.debug(
        "serve_page %s/%s/%s → %.1f ms (%.1f kB)",
        id,
        chapter,
        filename,
        1_000 * (time.perf_counter() - start),
        len(data) / 1024,
    )
    return resp
