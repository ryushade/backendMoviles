from __future__ import annotations
import datetime
from typing import Tuple, Dict, Union

from pymysql.cursors import DictCursor
import db.database as db


def _resolve_user_id(user: Union[int, str]) -> int:
    """
    Si 'user' es un entero, lo devuelve; si es string, lo busca por email.
    """
    if isinstance(user, int):
        return user
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(
            "SELECT id_user FROM usuario WHERE email=%s",
            (user,)
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"Usuario no encontrado: {user}")
    return row["id_user"]


def _obtener_o_crear_carrito(user: Union[int, str]) -> int:
    """
    Devuelve el id_carrito activo del usuario, creando uno si no existe.
    """
    id_user = _resolve_user_id(user)
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(
            "SELECT id_carrito FROM carrito WHERE id_user=%s LIMIT 1",
            (id_user,)
        )
        if row := cur.fetchone():
            return row["id_carrito"]
        cur.execute(
            "INSERT INTO carrito (id_user, fecha_creacion) VALUES (%s, %s)",
            (id_user, datetime.datetime.now())
        )
        cn.commit()
        return cur.lastrowid


def _item_en_carrito(user: Union[int, str], id_volumen: int) -> bool:
    """
    Verifica si el volumen ya está en el carrito del usuario.
    """
    id_carrito = _obtener_o_crear_carrito(user)
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(
            "SELECT 1 FROM detalle_carrito WHERE id_detalle_carrito=%s AND id_volumen=%s LIMIT 1",
            (id_carrito, id_volumen)
        )
        return cur.fetchone() is not None


def agregar_al_carrito(
    user: Union[int, str],
    id_volumen: int,
    cantidad: int = 1
) -> Tuple[Dict, int]:
    """
    Agrega 'cantidad' unidades del volumen al carrito del usuario.
    Si el volumen ya está en el carrito, devuelve error.
    """
    if cantidad < 1:
        return {"code": 1, "msg": "Cantidad debe ser ≥1"}, 400

    # Verificar si ya existe en carrito
    if _item_en_carrito(user, id_volumen):
        return {"code": 2, "msg": "Este volumen ya está en tu carrito"}, 400

    id_carrito = _obtener_o_crear_carrito(user)
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO detalle_carrito
               (id_detalle_carrito, id_volumen, cantidad)
            VALUES (%s, %s, %s)
            """,
            (id_carrito, id_volumen, cantidad)
        )
        cn.commit()

    return {"code": 0, "msg": "Añadido al carrito"}, 200


def actualizar_cantidad(
    user: Union[int, str],
    id_volumen: int,
    cantidad: int
) -> Tuple[Dict, int]:
    """
    Cambia la cantidad de un ítem; si cantidad ≤ 0 lo elimina.
    """
    id_carrito = _obtener_o_crear_carrito(user)
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        if cantidad <= 0:
            cur.execute(
                "DELETE FROM detalle_carrito WHERE id_detalle_carrito=%s AND id_volumen=%s",
                (id_carrito, id_volumen)
            )
        else:
            cur.execute(
                "UPDATE detalle_carrito SET cantidad=%s "
                "WHERE id_detalle_carrito=%s AND id_volumen=%s",
                (cantidad, id_carrito, id_volumen)
            )
        cn.commit()
    return {"code": 0, "msg": "Cantidad actualizada"}, 200


def eliminar_item(
    user: Union[int, str],
    id_volumen: int
) -> Tuple[Dict, int]:
    """Elimina una línea concreta del carrito."""
    return actualizar_cantidad(user, id_volumen, 0)


def vaciar_carrito(
    user: Union[int, str]
) -> Tuple[Dict, int]:
    """Borra TODO el carrito del usuario."""
    id_carrito = _obtener_o_crear_carrito(user)
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute(
            "DELETE FROM detalle_carrito WHERE id_detalle_carrito=%s",
            (id_carrito,)
        )
        cn.commit()
    return {"code": 0, "msg": "Carrito vaciado"}, 200


def listar_carrito(
    user: Union[int, str]
) -> Tuple[Dict, int]:
    """
    Devuelve contenido del carrito:
    { code, items: [...], total }
    Cada item: id_volumen, titulo_volumen, historieta, portada_url, cantidad, precio_unit
    """
    id_carrito = _obtener_o_crear_carrito(user)
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(
            """
            SELECT dc.id_volumen,
                   v.titulo_volumen,
                   h.titulo       AS historieta,
                   h.portada_url,
                   dc.cantidad,
                   v.precio_venta AS precio_unit
              FROM detalle_carrito dc
              JOIN volumen    v ON v.id_volumen = dc.id_volumen
              JOIN historieta h ON h.id_historieta = v.id_historieta
             WHERE dc.id_detalle_carrito = %s
            """,
            (id_carrito,)
        )
        items = cur.fetchall()

    total = sum(row["cantidad"] * row["precio_unit"] for row in items)
    return {"code": 0, "items": items, "total": total}, 200
