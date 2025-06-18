"""
services/solicitud_service.py  –  edición 2025-06-18
────────────────────────────────────────────────────
* Clasifica capítulos (regex + reset) con caché LRU.
* Recodifica todas las páginas a JPEG RGB quality 85.
* Usa ThreadPoolExecutor (8 hilos) para precargar el capítulo.
* send_file → conditional=True (304 cuando procede).
"""

from __future__ import annotations
import io, os, re, zipfile, itertools, logging, time, yaml
from collections import defaultdict
from contextlib import contextmanager
from functools import lru_cache
from typing import Dict, List

from PIL import Image
from flask import abort, current_app, send_file, url_for
from pymysql.cursors import DictCursor
from concurrent.futures import ThreadPoolExecutor

import db.database as db

# ───── Config ────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "..", "static", "uploads", "zips")
CACHE_DIR  = os.path.join(BASE_DIR, "..", "static", "cache")
RULES_FILE = os.path.join(BASE_DIR, "rules.yml")

MAX_PX           = 4096
RESET_THRESHOLD  = 5
MIN_PAGES_CHAP   = 8
ORPHAN_TOLERANCE = 0.03

logger   = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=8)

# ───── Regex rules ───────────────────────────────────────────────────────────
def _load_rules():
    if os.path.isfile(RULES_FILE):
        with open(RULES_FILE, encoding="utf-8") as fh:
            return [re.compile(d["regex"], re.I) for d in yaml.safe_load(fh)]
    return [                                              # fallback genérico
        re.compile(p, re.I) for p in (
            r"c(?P<chap>\d{3})/p?(?P<page>\d{1,3})\.[a-z]+$",
            r"(?P<chap>\d{3})[-_](?P<page>\d{2,3})\.[a-z]+$",
            r"DN[-_]?ch(?P<chap>\d{2,3})[-_]p?(?P<page>\d{2,3})\.[a-z]+$",
            r"[A-Za-z]+[-_]\d{2}[-_](?P<chap>\d{3})[-_](?P<page>\d{2,3})\.[a-z]+$",
        )
    ]

RULES = _load_rules()

def _parse(name: str):
    for rx in RULES:
        if m := rx.search(name):
            return int(m["chap"]), int(m["page"])
    return None

# ───── BD + ZIP helpers ──────────────────────────────────────────────────────
@lru_cache(maxsize=512)
def _zip_path(sid: int) -> str:
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute("SELECT url_zip FROM solicitud_publicacion WHERE id_solicitud=%s", (sid,))
        row = cur.fetchone()
    if not row:
        abort(404, "Solicitud no encontrada")
    path = os.path.join(UPLOAD_DIR, os.path.basename(row["url_zip"]))
    if not os.path.isfile(path):
        abort(404, "ZIP no encontrado")
    return path

@contextmanager
def _zip_open(sid: int):
    try:
        with zipfile.ZipFile(_zip_path(sid), "r") as zf:
            yield zf
    except zipfile.BadZipFile:
        abort(500, "ZIP corrupto")

# ───── Catálogo ──────────────────────────────────────────────────────────────
def _is_img(n: str) -> bool:
    return (
        not n.startswith(("__MACOSX/", "."))
        and n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    )

def _numeric_tokens(s: str):
    return [int("".join(g)) for k, g in itertools.groupby(s, str.isdigit) if k]

def _split_reset(names: List[str]):
    chaps, current, last, idx = {}, [], None, 1
    for n in names:
        page = _numeric_tokens(n)[-1] if _numeric_tokens(n) else None
        if (
            last is not None and page is not None
            and page <= RESET_THRESHOLD and last >= RESET_THRESHOLD + 3
            and len(current) >= MIN_PAGES_CHAP
        ):
            chaps[idx] = current
            idx += 1
            current = []
        current.append(n)
        last = page
    if current:
        chaps[idx] = current
    return chaps

def _detect(zf: zipfile.ZipFile):
    chap, pending = defaultdict(list), []
    for n in sorted(f for f in zf.namelist() if _is_img(f)):
        r = _parse(n)
        (chap[r[0]].append((r[1], n)) if r else pending.append(n))
    if pending:
        offset = max(chap) if chap else 0
        for i, names in _split_reset(pending).items():
            chap[offset + i].extend((None, n) for n in names)
    # ordenar páginas
    return {
        c: [n for _, n in sorted(v, key=lambda x: (x[0] is None, x[0], x[1]))]
        for c, v in chap.items()
    }

@lru_cache(maxsize=256)
def _catalog(sid: int):
    with _zip_open(sid) as zf:
        return _detect(zf)

# ───── Conversión + caché ───────────────────────────────────────────────────
def _cache_path(sid: int, chap: int, filename: str):
    return os.path.join(
        CACHE_DIR, str(sid), f"c{chap:03d}", os.path.splitext(filename)[0] + ".jpg"
    )

def _convert_only(zip_path: str, inner: str, dst: str):
    with zipfile.ZipFile(zip_path) as zf, zf.open(inner) as fp:
        img = Image.open(fp)
        if max(img.size) > MAX_PX:
            img.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
        if img.mode != "RGB":
            img = img.convert("RGB")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        img.save(dst, "JPEG", quality=85, optimize=True, progressive=True)

def _warm_cache(sid: int, chap: int, filename: str):
    try:
        inner = next(p for p in _catalog(sid)[chap] if p.endswith(filename))
        _convert_only(_zip_path(sid), inner, _cache_path(sid, chap, filename))
    except Exception as e:
        logger.debug("Prewarm fallo %s/%s/%s → %s", sid, chap, filename, e)

# ───── Endpoints ─────────────────────────────────────────────────────────────
def listar_capitulos(sid: int):
    return {"code": 0, "chapters": [f"c{c:03d}" for c in sorted(_catalog(sid))]}, 200

def listar_paginas(sid: int, chap_name: str):
    t0   = time.perf_counter()
    chap = int(chap_name.lstrip("c"))
    cat  = _catalog(sid)
    if chap not in cat:
        return {"code": 1, "msg": "Capítulo no encontrado"}, 404

    pages = [
        url_for("serve_chapter_page",
                id=sid, chapter=chap_name,
                filename=os.path.basename(p), _external=True)
        for p in cat[chap]
    ]

    # Lanzar precalentamiento sin bloquear
    for p in cat[chap]:
        executor.submit(_warm_cache, sid, chap, os.path.basename(p))

    logger.debug("listar_paginas %s/c%03d → %.1f ms",
                 sid, chap, 1_000*(time.perf_counter() - t0))
    return {"code": 0, "pages": pages}, 200

def serve_chapter_page(id: int, chapter: str, filename: str):
    t0   = time.perf_counter()
    chap = int(chapter.lstrip("c"))
    dst  = _cache_path(id, chap, filename)

    # 1 – si está en caché
    if os.path.isfile(dst):
        return send_file(dst, mimetype="image/jpeg",
                         max_age=31536000, conditional=True)

    # 2 – generar JPEG y servir
    cat = _catalog(id)
    target = [p for p in cat.get(chap, []) if p.endswith(filename)]
    if not target:
        abort(404)

    _convert_only(_zip_path(id), target[0], dst)

    logger.debug("serve_page %s/c%03d/%s %.1f ms",
                 id, chap, filename, 1_000*(time.perf_counter() - t0))
    return send_file(dst, mimetype="image/jpeg",
                     max_age=31536000, conditional=True)
