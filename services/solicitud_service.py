# services/solicitud_service.py
import os, zipfile, re, itertools, yaml, logging
from collections import defaultdict
from contextlib import contextmanager

from flask import current_app, url_for, abort, send_file
import db.database as db
from pymysql.cursors import DictCursor

# ──────────────────────────────────────────────────────────────────────────────
# Configuración básica
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR          = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER_ZIPS = os.path.join(BASE_DIR, "..", "static", "uploads", "zips")
RULES_FILE        = os.path.join(BASE_DIR, "rules.yml")    # opcional
RESET_THRESHOLD   = 5      # página ≤5 tras ≥8 → nuevo capítulo
MIN_PAGES_CHAP    = 8
ORPHAN_TOLERANCE  = 0.03   # 3 %
ENABLE_OCR        = False  # actívalo si tienes tesseract instalado

if ENABLE_OCR:
    import cv2, pytesseract, numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Utilidad BD + ZIP
# ──────────────────────────────────────────────────────────────────────────────
@contextmanager
def _zip_from_solicitud(id_solicitud: int):
    """Devuelve un ZipFile abierto o lanza abort(404/500)."""
    with db.obtener_conexion() as cn:
        with cn.cursor(DictCursor) as cur:
            cur.execute("SELECT url_zip FROM solicitud_publicacion WHERE id_solicitud=%s",
                        (id_solicitud,))
            row = cur.fetchone()
    if not row:
        abort(404, "Solicitud no encontrada")

    zip_path = os.path.join(UPLOAD_FOLDER_ZIPS, os.path.basename(row["url_zip"]))
    if not os.path.isfile(zip_path):
        abort(404, "ZIP no encontrado en el servidor")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            yield zf
    except zipfile.BadZipFile:
        abort(500, "Archivo ZIP corrupto")

# ──────────────────────────────────────────────────────────────────────────────
# Capa 1 – regex configurables
# ──────────────────────────────────────────────────────────────────────────────
def _load_rules():
    if not os.path.isfile(RULES_FILE):
        # fallback a cuatro patrones genéricos
        patterns = [
            r'c(?P<chap>\d{3})/p?(?P<page>\d{1,3})\.[a-z]+$',
            r'(?P<chap>\d{3})[-_](?P<page>\d{2,3})\.[a-z]+$',
            r'DN[-_]?ch(?P<chap>\d{2,3})[-_]p?(?P<page>\d{2,3})\.[a-z]+$',
            r'[A-Za-z]+[-_]\d{2}[-_](?P<chap>\d{3})[-_](?P<page>\d{2,3})\.[a-z]+$',
        ]
        return [(f"default_{i}", re.compile(p, re.I)) for i, p in enumerate(patterns)]

    with open(RULES_FILE, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return [(d["id"], re.compile(d["regex"], re.I)) for d in data]

RULES = _load_rules()

def _regex_parse(name: str):
    """Devuelve (chap, page) o None."""
    for _id, rx in RULES:
        m = rx.search(name)
        if m:
            return int(m["chap"]), int(m["page"])
    return None

# ──────────────────────────────────────────────────────────────────────────────
# Capa 2 – heurística reinicio de página
# ──────────────────────────────────────────────────────────────────────────────
def _numeric_tokens(s: str):
    tokens = []
    for k, g in itertools.groupby(s, str.isdigit):
        if k:
            tokens.append(int("".join(g)))
    return tokens

def _split_by_reset(names_sorted):
    """Devuelve {chap_idx: [names]} usando la heurística de reset."""
    chapters, current, last_page, idx = {}, [], None, 1
    for fname in names_sorted:
        nums  = _numeric_tokens(fname)
        page  = nums[-1] if nums else None

        if (last_page is not None and page is not None
            and page <= RESET_THRESHOLD and last_page >= RESET_THRESHOLD + 3):
            if len(current) >= MIN_PAGES_CHAP:
                chapters[idx] = current
                idx += 1
                current = []
        current.append(fname)
        last_page = page
    if current:
        chapters[idx] = current
    return chapters

# ──────────────────────────────────────────────────────────────────────────────
# Capa 3 – OCR selectivo (opcional)
# ──────────────────────────────────────────────────────────────────────────────
OCR_WORDS = r'(cap[íi]tulo|chapter|capitulo|capitul|episodio|ep)\s*(\d{1,3})'

def _ocr_detect(img_bytes):
    """Devuelve nº capítulo OCR o None."""
    if not ENABLE_OCR:
        return None
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    h = img.shape[0]
    header = img[: int(h * 0.25), :]              # 25 % superior
    text = pytesseract.image_to_string(header, config="--psm 6")
    m = re.search(OCR_WORDS, text, re.I)
    return int(m.group(2)) if m else None

# ──────────────────────────────────────────────────────────────────────────────
# Motor completo de clasificación
# ──────────────────────────────────────────────────────────────────────────────
def _detect_chapters(zf: zipfile.ZipFile):
    chapters = defaultdict(list)
    pending  = []

    for name in sorted(n for n in zf.namelist() if not n.endswith("/")):
        parsed = _regex_parse(name)
        if parsed:
            chap, page = parsed
            chapters[chap].append((page, name))
        else:
            pending.append(name)

    # ── capa 2
    if pending:
        reset_blocks = _split_by_reset(pending)
        offset = max(chapters) if chapters else 0
        for idx, names in reset_blocks.items():
            chapters[offset + idx].extend((None, n) for n in names)

    # ── capa 3 (OCR) — sólo en bloques procedentes de reset
    if ENABLE_OCR:
        for chap_id, items in list(chapters.items()):
            # si el bloque es mixto regex+reset no tocamos (ya es confiable)
            if all(p is None for p, _ in items):
                sample_names = [n for _, n in items[:3]]  # primeras tres
                ocr_vals = []
                for n in sample_names:
                    with zf.open(n) as fp:
                        ocr_vals.append(_ocr_detect(fp.read()))
                ocr_vals = [v for v in ocr_vals if v is not None]
                if ocr_vals and ocr_vals[0] != chap_id:
                    # reasigna todo el bloque
                    chapters[ocr_vals[0]] = chapters.pop(chap_id)

    # ── ordenar páginas y montar catálogo final
    final_cat = {
        chap: [n for _, n in sorted(v, key=lambda x: (x[0] is None, x[0], x[1]))]
        for chap, v in chapters.items()
    }

    # ── aviso de huérfanos
    total = len([n for n in zf.namelist() if not n.endswith("/")])
    assigned = sum(len(v) for v in final_cat.values())
    if total and (1 - assigned / total) > ORPHAN_TOLERANCE:
        current_app.logger.warning("ZIP %s: %.1f %% sin capítulo",
                                   zf.filename, 100 - 100 * assigned / total)

    return final_cat

# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINT 1 – Listar capítulos
# ──────────────────────────────────────────────────────────────────────────────
def listar_capitulos(id_solicitud):
    try:
        with _zip_from_solicitud(id_solicitud) as zf:
            cat = _detect_chapters(zf)
        # Devuelve “c001”, “c002”… ordenados
        return {"code": 0, "chapters": [f"c{c:03d}" for c in sorted(cat)]}, 200
    except Exception:                           # pragma: no cover
        current_app.logger.exception("listar_capitulos")
        return {"code": 1, "msg": "Error interno del servidor"}, 500

# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINT 2 – Listar páginas de un capítulo
# ──────────────────────────────────────────────────────────────────────────────
def listar_paginas(id_solicitud, chapter_name):
    try:
        chap_int = int(chapter_name.lstrip("c"))
        with _zip_from_solicitud(id_solicitud) as zf:
            cat = _detect_chapters(zf)
            if chap_int not in cat:
                return {"code": 1, "msg": "Capítulo no encontrado"}, 404

            pages = [
                url_for("serve_chapter_page",
                        id=id_solicitud,
                        chapter=chapter_name,
                        filename=os.path.basename(fpath),
                        _external=True)
                for fpath in cat[chap_int]
            ]
        return {"code": 0, "pages": pages}, 200
    except Exception:
        current_app.logger.exception("listar_paginas")
        return {"code": 1, "msg": "Error interno del servidor"}, 500

# ──────────────────────────────────────────────────────────────────────────────
# EXTRA – servir una página concreta (usa streaming; sin descomprimir)
# ──────────────────────────────────────────────────────────────────────────────
def serve_chapter_page(id: int, chapter: str, filename: str):
    """
    Para usarlo debes registrar esta función como route:
      app.route("/solicitudes/<int:id>/<chapter>/<filename>")
    """
    with _zip_from_solicitud(id) as zf:
        # localiza la ruta interna exacta
        chap_int = int(chapter.lstrip("c"))
        cat = _detect_chapters(zf)
        if chap_int not in cat:
            abort(404)
        fpaths = [p for p in cat[chap_int] if p.endswith(filename)]
        if not fpaths:
            abort(404)

        # send_file acepta un objeto tipo File-like; ZipExtFile sirve perfecto
        fp = zf.open(fpaths[0])
        return send_file(fp, mimetype="image/jpeg", max_age=0)  # o image/png
