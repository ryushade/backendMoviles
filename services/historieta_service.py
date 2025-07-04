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


def mas_vendidos(limit: int = 10) -> List[Dict]:
    """
    Retorna los volúmenes más vendidos (sólo los que tienen al menos una venta),
    ordenados por cantidad total vendida.
    Cada elemento incluye:
      - id_volumen
      - titulo         (Título de la historieta)
      - portada_url    (URL de portada de la historieta)
      - total_vendido  (Suma de todas las cantidades vendidas)
    """
    sql = """
    SELECT
      v.id_volumen,
      h.titulo        AS titulo,
      h.portada_url   AS portada_url,
      SUM(dv.cantidad) AS total_vendido
    FROM volumen v
    JOIN detalle_venta dv  ON dv.id_volumen   = v.id_volumen
    JOIN historieta h      ON h.id_historieta = v.id_historieta
    WHERE h.estado = 'aprobado'
    GROUP BY
      v.id_volumen,
      h.titulo,
      h.portada_url
    ORDER BY total_vendido DESC
    LIMIT %s;
    """
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute(sql, (limit,))
        filas = cur.fetchall()

    resultados = []
    for fila in filas:
        # permite cursor DictCursor o tuplas
        id_vol     = fila["id_volumen"]    if isinstance(fila, dict) else fila[0]
        titulo     = fila["titulo"]        if isinstance(fila, dict) else fila[1]
        portada    = fila["portada_url"]    if isinstance(fila, dict) else fila[2]
        total      = fila["total_vendido"] if isinstance(fila, dict) else fila[3]

        resultados.append({
            "id_volumen":    id_vol,
            "titulo":        titulo,
            "portada_url":   portada,
            "total_vendido": int(total)
        })

    return resultados