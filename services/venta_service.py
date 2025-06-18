# services/venta_service.py
# ----------------------------------------------------------------------
#  Gestiona las ventas y su detalle (historietas compradas)
# ----------------------------------------------------------------------
#  • crear_venta(id_user, carrito)   →  id de la venta creada
#  • obtener_ventas(id_user)        →  listado resumido de las ventas
#  • obtener_detalle(id_ven)        →  detalle con las historietas
# ----------------------------------------------------------------------
#  Estructura de «carrito» que envía el cliente:
#  [
#      {"id_historieta": 5, "precio": 4.99, "cantidad": 1},
#      {"id_historieta": 9, "precio": 3.50, "cantidad": 2}
#  ]
# ----------------------------------------------------------------------

from __future__ import annotations
from typing import List, Dict, Tuple

from pymysql.cursors import DictCursor
import db.database as db


# ──────────────────────────────────────────────────────────────────────
#  ALTA DE VENTA
# ──────────────────────────────────────────────────────────────────────
def crear_venta(id_user: int, carrito: List[Dict]) -> int:
    """
    Inserta cabecera + líneas en una transacción.
    Devuelve el id_ven generado.

    :param id_user:   comprador
    :param carrito:   lista de dicts con id_historieta, precio, cantidad
    """
    if not carrito:
        raise ValueError("carrito vacío")

    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cn.start_transaction()

        # 1) Cabecera
        cur.execute(
            "INSERT INTO venta (id_user, estado_ven) VALUES (%s, 1)",
            (id_user,)
        )
        id_ven: int = cur.lastrowid

        # 2) Detalle
        for item in carrito:
            cur.execute(
                """
                INSERT INTO detalle_venta
                    (id_venta, id_historieta, precio_ven, cantidad)
                VALUES (%s,%s,%s,%s)
                """,
                (
                    id_ven,
                    int(item["id_historieta"]),
                    float(item["precio"]),
                    int(item.get("cantidad", 1)),
                ),
            )

        cn.commit()
    return id_ven


# ──────────────────────────────────────────────────────────────────────
#  CONSULTAS
# ──────────────────────────────────────────────────────────────────────
def obtener_ventas(id_user: int) -> List[Dict]:
    """
    Devuelve las ventas del usuario con total y fecha.
    """
    sql = """
        SELECT v.id_ven,
               v.fec_ven,
               SUM(d.precio_ven * d.cantidad) AS total,
               COUNT(*)                       AS lineas
          FROM venta v
          JOIN detalle_venta d USING(id_ven)
         WHERE v.id_user = %s
         GROUP BY v.id_ven
         ORDER BY v.fec_ven DESC
    """
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(sql, (id_user,))
        return cur.fetchall()


def obtener_detalle(id_ven: int) -> Tuple[Dict, List[Dict]]:
    """
    Cabecera + líneas de una venta concreta.
    """
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        # Cabecera
        cur.execute("SELECT * FROM venta WHERE id_ven=%s", (id_ven,))
        cab = cur.fetchone()
        if not cab:
            raise ValueError("venta no encontrada")

        # Líneas
        cur.execute(
            """
            SELECT d.id_historieta,
                   h.titulo,
                   d.cantidad,
                   d.precio_ven
              FROM detalle_venta d
              JOIN historieta h USING(id_historieta)
             WHERE d.id_venta=%s
            """,
            (id_ven,),
        )
        det = cur.fetchall()

    return cab, det
