# services/historieta_service.py
from __future__ import annotations
import datetime, os
from typing import List, Dict, Tuple
from pymysql.cursors import DictCursor
import db.database as db


# ───────────────────────── helpers comunes ────────────────────────────
def _rows_to_json(rows) -> List[Dict]:
    """Convierte los rows crudos a un JSON compacto para la app."""
    return [
        {
            "id_volumen" : r["id_volumen"],
            "titulo"     : r["titulo_volumen"],
            "portada"    : r["portada_url"],
            "precio"     : float(r["precio_venta"] or 0),
            "anio"       : r["anio_publicacion"],
            # extra si quieres
        }
        for r in rows
    ]


# ────────────────────── consultas de negocio ──────────────────────────
def novedades(limit: int = 24):
    """
    Devuelve los volúmenes publicados más recientemente (orden fecha).
    """
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(
            """
            SELECT v.id_volumen, v.titulo_volumen, v.precio_venta,
                   h.portada_url, h.anio_publicacion
              FROM volumen v
              JOIN historieta h ON h.id_historieta = v.id_historieta
             WHERE h.estado = 'aprobado'
          ORDER BY v.fecha_publicacion DESC
             LIMIT %s
            """,
            (limit,),
        )
        return _rows_to_json(cur.fetchall())


def mas_vendidas(limit: int = 24):
    """
    TOP volúmenes por número de ventas (tabla venta_detalle).
    """
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(
            """
            SELECT v.id_volumen, v.titulo_volumen, v.precio_venta,
                   h.portada_url, h.anio_publicacion,
                   COUNT(*) AS ventas
              FROM venta_detalle d
              JOIN volumen        v ON v.id_volumen = d.id_volumen
              JOIN historieta     h ON h.id_historieta = v.id_historieta
             GROUP BY v.id_volumen
             ORDER BY ventas DESC
             LIMIT %s
            """,
            (limit,),
        )
        return _rows_to_json(cur.fetchall())


def por_genero(id_genero: int, limit: int = 24):
    """
    Volúmenes cuyo historieta tenga el género indicado.
    """
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(
            """
            SELECT v.id_volumen, v.titulo_volumen, v.precio_venta,
                   h.portada_url, h.anio_publicacion
              FROM historieta_genero g
              JOIN historieta h      ON h.id_historieta = g.id_historieta
              JOIN volumen    v      ON v.id_historieta = h.id_historieta
             WHERE g.id_genero = %s
          ORDER BY v.fecha_publicacion DESC
             LIMIT %s
            """,
            (id_genero, limit),
        )
        return _rows_to_json(cur.fetchall())
