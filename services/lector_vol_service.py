# services/lector_vol_service.py
from __future__ import annotations
import os, io, zipfile
from functools   import lru_cache
from contextlib  import contextmanager
from typing      import List, Dict
from pymysql.cursors import DictCursor
from flask  import abort, url_for, send_file, current_app
from PIL    import Image
import db.database as db

# ───────── config reutilizada ─────────
BASE_DIR  = os.path.abspath(os.path.dirname(__file__))
UPLOAD_ZIPS = os.path.join(BASE_DIR, "..", "static", "uploads", "zips")
from services.solicitud_service import (          # ← ¡YA EXISTEN!
    _load_rules, _numeric_tokens, _split_reset,
    _is_img, _detect, MAX_PX, CACHE_DIR,          # mismas constantes
)

RULES = _load_rules()                             # mismas expresiones

# ───────── helpers específicos de volumen ──────
@lru_cache(maxsize=512)
def _zip_path_vol(id_vol:int) -> str:
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute("SELECT ruta_contenido FROM volumen WHERE id_volumen=%s", (id_vol,))
        row = cur.fetchone()
    if not row: abort(404, "Volumen no encontrado")
    path = os.path.join(UPLOAD_ZIPS, os.path.basename(row["ruta_contenido"]))
    if not os.path.isfile(path): abort(404, "ZIP no existe")
    return path


@contextmanager
def _zip_open(id_vol:int):
    try:
        with zipfile.ZipFile(_zip_path_vol(id_vol), "r") as zf:
            yield zf
    except zipfile.BadZipFile:
        abort(500, "ZIP corrupto")


@lru_cache(maxsize=256)
def _catalogo(id_vol:int) -> Dict[int, List[str]]:
    with _zip_open(id_vol) as zf:
        return _detect(zf)                         # ¡misma heurística!


# ───────── endpoints “lógicos” (llamados desde main.py) ────────
def ficha_volumen(id_vol:int):
    """Datos para la pantalla de detalles (sinopsis, precio, etc.)."""
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute("""
            SELECT v.id_volumen, v.titulo_volumen     AS titulo,
                   h.descripcion                      AS sinopsis,
                   h.portada_url                      AS portada,
                   v.precio_venta                     AS precio,
                   h.anio_publicacion                 AS anio,
                   h.tipo
              FROM volumen  v
              JOIN historieta h USING(id_historieta)
             WHERE v.id_volumen=%s
        """, (id_vol,))
        fila = cur.fetchone()
    if not fila:
        return {"code":1, "msg":"Volumen no encontrado"}, 404
    return fila, 200


def listar_capitulos(id_vol:int):
    caps = [f"c{c:03d}" for c in sorted(_catalogo(id_vol))]
    return {"code":0, "chapters":caps}, 200


def listar_paginas(id_vol:int, chap:str):
    c = int(chap.lstrip("c"))
    cat = _catalogo(id_vol)
    if c not in cat:
        return {"code":1,"msg":"Capítulo no encontrado"},404
    pages = [url_for("srv_vol_page", id=id_vol, chapter=chap,
                     filename=os.path.basename(p), _external=True)
             for p in cat[c]]
    return {"code":0,"pages":pages}, 200


# conversión + caché idéntica a solicitud_service -----------------
def _cache_path(id_vol:int, chap:int, fname:str):
    base = os.path.splitext(fname)[0]+".jpg"
    return os.path.join(CACHE_DIR, f"v{id_vol}", f"c{chap:03d}", base)


def serve_page(id_vol:int, chapter:str, filename:str):   # ← registrado en main.py
    chap=int(chapter.lstrip("c"))
    dst=_cache_path(id_vol,chap,filename)
    if os.path.isfile(dst):
        return send_file(dst, mimetype="image/jpeg", max_age=31536000)

    cat=_catalogo(id_vol)
    target=[p for p in cat.get(chap,[]) if p.endswith(filename)]
    if not target: abort(404)

    with _zip_open(id_vol) as zf:
        img=Image.open(io.BytesIO(zf.read(target[0])))

    if max(img.size)>MAX_PX: img.thumbnail((MAX_PX,MAX_PX), Image.LANCZOS)
    if img.mode!="RGB": img=img.convert("RGB")

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    img.save(dst,"JPEG",quality=85,optimize=True,progressive=True)
    return send_file(dst,mimetype="image/jpeg",max_age=31536000)


def usuario_compro_volumen(email_user: str, id_vol: int) -> bool:
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cursor:
        # 1) Obtener id_user
        cursor.execute("SELECT id_user FROM usuario WHERE email = %s", (email_user,))
        fila = cursor.fetchone()
        if not fila:
            return False
        id_user = fila["id_user"]

        # 2) Verificar compra por volumen
        cursor.execute(
            """
            SELECT 1
              FROM venta v
              JOIN detalle_venta dv ON v.id_ven = dv.id_venta
             WHERE v.id_user    = %s
               AND dv.id_volumen = %s
             LIMIT 1
            """,
            (id_user, id_vol)
        )
        return cursor.fetchone() is not None
