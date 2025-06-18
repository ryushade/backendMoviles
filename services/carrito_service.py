# services/carrito_service.py
from __future__ import annotations
import datetime
from typing import Tuple, List, Dict

from pymysql.cursors import DictCursor
import db.database as db


# ───────────────────────────────────────────────────────────────
# Funciones públicas
# ───────────────────────────────────────────────────────────────

def obtener_o_crear_carrito(id_user: int) -> int:
    """
    Devuelve el id_carrito ACTIVO (abierto) del usuario.  
    Si no existe, crea uno nuevo y lo devuelve.
    """
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(
            "SELECT id_carrito FROM carrito WHERE id_user=%s LIMIT 1",
            (id_user,)
        )
        row = cur.fetchone()
        if row:
            return row["id_carrito"]

        cur.execute(
            """
            INSERT INTO carrito (id_user, fecha_creacion)
            VALUES (%s, %s)
            """,
            (id_user, datetime.datetime.now())
        )
        return cur.lastrowid


def agregar_al_carrito(id_user: int, id_historieta: int, cantidad: int = 1
                       ) -> Tuple[Dict, int]:
    """
    Agrega `cantidad` unidades de la historieta al carrito del usuario.
    Si ya existe, simplemente incrementa la cantidad.

    Retorna (json, status_code)
    """
    if cantidad < 1:
        return {"code": 1, "msg": "Cantidad debe ser ≥1"}, 400

    try:
        id_carrito = obtener_o_crear_carrito(id_user)

        with db.obtener_conexion() as cn, cn.cursor() as cur:
            # ── `ON DUPLICATE KEY` para sumar cantidades ──
            cur.execute(
                """
                INSERT INTO detalle_carrito
                    (id_detalle_carrito, id_historieta, cantidad)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    cantidad = cantidad + VALUES(cantidad)
                """,
                (id_carrito, id_historieta, cantidad)
            )
            cn.commit()

        return {"code": 0, "msg": "Añadido al carrito"}, 200

    except Exception as e:
        return {"code": 1, "msg": f"Error interno: {e}"}, 500


def actualizar_cantidad(id_user: int, id_historieta: int, cantidad: int
                        ) -> Tuple[Dict, int]:
    """
    Cambia la cantidad de un ítem concreto.
    Si cantidad == 0 se elimina la línea.
    """
    try:
        id_carrito = obtener_o_crear_carrito(id_user)

        with db.obtener_conexion() as cn, cn.cursor() as cur:
            if cantidad == 0:
                cur.execute(
                    """
                    DELETE FROM detalle_carrito
                    WHERE id_detalle_carrito=%s AND id_historieta=%s
                    """,
                    (id_carrito, id_historieta)
                )
            else:
                cur.execute(
                    """
                    UPDATE detalle_carrito
                       SET cantidad=%s
                     WHERE id_detalle_carrito=%s AND id_historieta=%s
                    """,
                    (cantidad, id_carrito, id_historieta)
                )
            cn.commit()

        return {"code": 0, "msg": "Cantidad actualizada"}, 200

    except Exception as e:
        return {"code": 1, "msg": f"Error interno: {e}"}, 500


def eliminar_item(id_user: int, id_historieta: int) -> Tuple[Dict, int]:
    """Elimina una línea concreta del carrito."""
    return actualizar_cantidad(id_user, id_historieta, 0)


def vaciar_carrito(id_user: int) -> Tuple[Dict, int]:
    """Borra TODO el carrito del usuario."""
    try:
        id_carrito = obtener_o_crear_carrito(id_user)
        with db.obtener_conexion() as cn, cn.cursor() as cur:
            cur.execute(
                "DELETE FROM detalle_carrito WHERE id_detalle_carrito=%s",
                (id_carrito,)
            )
            cn.commit()
        return {"code": 0, "msg": "Carrito vaciado"}, 200
    except Exception as e:
        return {"code": 1, "msg": f"Error interno: {e}"}, 500


def listar_carrito(id_user: int) -> Tuple[Dict, int]:
    """
    Devuelve el contenido completo:

    {
      "code": 0,
      "items": [
        {
          "id_historieta": 12,
          "titulo": "Death Note",
          "portada_url": "https://...",
          "cantidad": 2,
          "precio_unit": 5.99
        },
        ...
      ],
      "total": 11.98
    }
    """
    try:
        id_carrito = obtener_o_crear_carrito(id_user)

        with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
            cur.execute(
                """
                SELECT dc.id_historieta,
                       h.titulo,
                       h.portada_url,
                       dc.cantidad,
                       IFNULL(MIN(v.precio_venta), 0) AS precio_unit
                  FROM detalle_carrito dc
                  JOIN historieta h USING(id_historieta)
                  LEFT JOIN volumen   v USING(id_historieta)
                 WHERE dc.id_detalle_carrito=%s
                 GROUP BY dc.id_historieta, dc.cantidad
                """,
                (id_carrito,)
            )
            filas = cur.fetchall()

        total = sum(f["cantidad"] * f["precio_unit"] for f in filas)

        return {"code": 0, "items": filas, "total": total}, 200

    except Exception as e:
        return {"code": 1, "msg": f"Error interno: {e}"}, 500
