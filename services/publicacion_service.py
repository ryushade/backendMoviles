# services/publicacion_service.py
from __future__ import annotations
import os, threading, zipfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import requests
from flask import current_app
from pymysql.cursors import DictCursor

import db.database as db

# ▸ Re-utilizamos toda la lógica de clasificación / caché del módulo de solicitudes
from services.solicitud_service import (
    _catalog,           # dado un id_solicitud   → {capítulo: [files]}
    _cache_path,        # (id_solicitud, cap, filename) → ruta JPEG en CACHE_DIR
    _warm_cache,        # genera la entrada JPEG on-demand
    _zip_path           # id_solicitud → ruta ZIP absoluta
)

# carpeta donde viven los ZIP subidos por los autores
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..",
                          "static", "uploads", "zips")

# ═════════════════════  APROBAR SOLICITUD  ════════════════════════════════════
def aprobar_solicitud(id_solicitud: int, id_admin: int):
    """
    • Inserta historieta + volumen 1 y vínculos a autores y género.
    • Cambia la solicitud a 'aprobado'.
    • Lanza un job que recorre todo el ZIP y precalienta la caché JPEG.
    """
    try:
        with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:

            # 1) Solicitud pendiente (bloqueo fila)
            cur.execute("""
                SELECT *
                  FROM solicitud_publicacion
                 WHERE id_solicitud = %s AND estado = 'pendiente'
                 FOR UPDATE
            """, (id_solicitud,))
            row = cur.fetchone()
            if not row:
                return {"code": 1,
                        "msg": "Solicitud no encontrada o ya procesada"}, 404

            # 2) Tx explícita
            cn.start_transaction()

            # 3) Historieta
            cur.execute("""
                INSERT INTO historieta
                      (titulo, descripcion, portada_url, tipo,
                       restriccion_edad, anio_publicacion,
                       estado, id_editorial)
                VALUES (%s,%s,%s,%s,%s,%s,'aprobado',
                       (SELECT id_editorial
                          FROM editorial
                         WHERE nombre_editorial=%s LIMIT 1))
            """, (
                row["titulo"], row["descripcion"], row["url_portada"],
                row["tipo"],   row["restriccion_edad"], row["anio_publicacion"],
                row["editorial"]
            ))
            id_hist = cur.lastrowid

            # 4) Volumen 1
            cur.execute("""
                INSERT INTO volumen
                      (id_historieta, numero_volumen, titulo_volumen,
                       formato_contenido, ruta_contenido,
                       precio_venta, fecha_publicacion)
                VALUES (%s, 1, %s, 'zip', %s, %s, CURDATE())
            """, (
                id_hist,
                f"{row['titulo']} Vol.1",
                row["url_zip"],
                row["precio_volumen"] or 0.00
            ))
            id_vol = cur.lastrowid

            # 5) Autores (coma-separado)
            for nombre in (a.strip() for a in row["autores"].split(",") if a.strip()):
                cur.execute("SELECT id_autor FROM autor WHERE nombre_autor=%s", (nombre,))
                res = cur.fetchone()
                id_autor = res["id_autor"] if res else (
                    cur.execute("INSERT INTO autor(nombre_autor) VALUES(%s)", (nombre,)),
                    cur.lastrowid
                )[1]
                cur.execute("""
                    INSERT IGNORE INTO historieta_autor(id_historieta, id_autor)
                    VALUES (%s,%s)
                """, (id_hist, id_autor))

            # 6) Género principal  (YA viene como id_genero en la solicitud)
            cur.execute("""
                INSERT IGNORE INTO historieta_genero(id_historieta, id_genero)
                VALUES (%s, %s)
            """, (id_hist, row["id_genero"]))

            # 7) Marcar solicitud
            cur.execute("""
                UPDATE solicitud_publicacion
                   SET estado='aprobado',
                       id_historieta_creada=%s,
                       id_admin_aprobador=%s,
                       fecha_respuesta = NOW()
                 WHERE id_solicitud=%s
            """, (id_hist, id_admin, id_solicitud))

            cn.commit()

        # 8) Precalentar caché (hilo aparte)
        threading.Thread(
            target=_precalentar_volumen,
            args=(id_solicitud,),   # usamos el id_solicitud — es el que entiende solicitud_service
            daemon=True
        ).start()

        return {"code": 0,
                "msg": f"Historieta publicada (ID {id_hist})"}, 200

    except Exception:
        current_app.logger.exception("aprobar_solicitud")
        # si la conexión sigue viva, intenta rollback
        try:
            if cn.in_transaction:    # type: ignore
                cn.rollback()
        except Exception:
            ...
        return {"code": 1,
                "msg": "Error interno al aprobar"}, 500

# ════════════════  PRECALENTAMIENTO DE CACHÉ  ════════════════════════════════
def _precalentar_volumen(id_solicitud: int):
    """
    Recorre TODO el ZIP asociado a la solicitud y fuerza la generación de todas
    las entradas JPEG en CACHE_DIR para que el lector móvil las obtenga al
    instante.  Re-utiliza _warm_cache() del módulo de solicitudes.
    """
    try:
        cat = _catalog(id_solicitud)  # {capítulo: [lista archivos]}
        for chap, files in cat.items():
            for f in files:
                _warm_cache(id_solicitud, chap,
                            os.path.basename(f))  # genera/guarda JPEG
        current_app.logger.info("Caché precalentada para solicitud %s", id_solicitud)

    except Exception as exc:
        current_app.logger.warning(
            "Precalentamiento solicitud %s falló: %s", id_solicitud, exc
        )
