from __future__ import annotations
from typing import List, Dict, Tuple

from pymysql.cursors import DictCursor
import db.database as db


def crear_venta(id_user: int, carrito: List[Dict]) -> int:
    """
    Inserta una nueva venta y sus líneas de detalle usando el esquema actual,
    y luego elimina el carrito y sus detalles para ese usuario.
    """
    if not carrito:
        raise ValueError("carrito vacío")

    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cn.begin()

        # 0) Obtener id_carrito activo del usuario
        cur.execute(
            "SELECT id_carrito FROM carrito WHERE id_user = %s",
            (id_user,)
        )
        fila = cur.fetchone()
        id_carrito = fila["id_carrito"] if isinstance(fila, dict) else (fila[0] if fila else None)

        # 1) Cabecera de la venta
        cur.execute(
            "INSERT INTO venta (id_user, estado_ven) VALUES (%s, 1)",
            (id_user,)
        )
        id_ven: int = cur.lastrowid

        # 2) Detalle de la venta (ahora referencia id_volumen)
        for item in carrito:
            cur.execute(
                """
                INSERT INTO detalle_venta
                    (id_venta, id_volumen, precio_ven, cantidad)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    id_ven,
                    int(item["id_volumen"]),
                    float(item["precio_ven"]),
                    int(item.get("cantidad", 1)),
                ),
            )

        # 3) Vaciar el carrito del usuario
        if id_carrito is not None:
            # borra líneas asociadas
            cur.execute(
                "DELETE FROM detalle_carrito WHERE id_detalle_carrito = %s",
                (id_carrito,)
            )
            # borra la cabecera del carrito (cascade elimina detalles restantes)
            cur.execute(
                "DELETE FROM carrito WHERE id_carrito = %s",
                (id_carrito,)
            )

        cn.commit()

    return id_ven



# ──────────────────────────────────────────────────────────────────────
#  CONSULTAS
# ──────────────────────────────────────────────────────────────────────
def obtener_ventas(id_user: int) -> List[Dict]:
    """
    Devuelve el listado de ventas de un usuario con:
      - id_ven, fecha, total de cada venta y número de líneas
    Adaptado a detalle_venta.id_venta
    """
    sql = """
        SELECT
          v.id_ven,
          v.fec_ven,
          SUM(d.precio_ven * d.cantidad) AS total,
          COUNT(*)                       AS lineas
        FROM venta v
        JOIN detalle_venta d
          ON v.id_ven = d.id_venta
        WHERE v.id_user = %s
        GROUP BY v.id_ven
        ORDER BY v.fec_ven DESC
    """
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute(sql, (id_user,))
        return cur.fetchall()


def obtener_detalle(id_ven: int) -> Tuple[Dict, List[Dict]]:
    """
    Devuelve la cabecera y las líneas de detalle de una venta:
      - cabecera: todos los campos de venta
      - líneas: id_volumen, título, número de volumen, cantidad y precio unitario
    """
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        # Cabecera
        cur.execute("SELECT * FROM venta WHERE id_ven = %s", (id_ven,))
        cab = cur.fetchone()
        if not cab:
            raise ValueError("venta no encontrada")

        # Líneas de detalle (ahora unimos via volumen → historieta)
        cur.execute(
            """
            SELECT
              d.id_volumen,
              h.titulo,
              vol.numero_volumen,
              d.cantidad,
              d.precio_ven
            FROM detalle_venta d
            JOIN volumen vol
              ON d.id_volumen = vol.id_volumen
            JOIN historieta h
              ON vol.id_historieta = h.id_historieta
            WHERE d.id_venta = %s
            """,
            (id_ven,),
        )
        det = cur.fetchall()

    return cab, det

def crear_pedido_preliminar(id_user: int, amount_cents: int) -> int:
    """
    Inserta una venta PENDIENTE (estado_ven = 0) con el monto y devuelve su id_ven.
    """
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute("""
            INSERT INTO venta (id_user, estado_ven, monto_cents)
            VALUES (%s, %s, %s)
        """, (id_user, 0, amount_cents))  # <–– usar 0 en vez de 'PENDIENTE'
        cn.commit()
        return cur.lastrowid


def confirmar_venta_from_intent(payment_intent_id: str, carrito: list, id_user: int) -> int:
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cn.begin()
        # 1) Recuperar id_ven
        cur.execute("""
            SELECT id_ven
              FROM venta
             WHERE stripe_pi_id = %s
               AND id_user      = %s
        """, (payment_intent_id, id_user))
        fila = cur.fetchone()
        if not fila:
            raise ValueError("Venta preliminar no encontrada")
        id_ven = fila["id_ven"] if isinstance(fila, dict) else fila[0]

        # 2) Marcar como completada
        cur.execute("""
            UPDATE venta
               SET estado_ven = 1,
                   fec_ven    = NOW()
             WHERE id_ven = %s
        """, (id_ven,))

        # 3) Para cada item, recuperar precio real y guardar detalle
        for item in carrito:
            id_vol = int(item["id_volumen"])
            cantidad = int(item.get("cantidad", 1))

            # Busca el precio en la tabla volumen
            cur.execute(
                "SELECT precio_venta FROM volumen WHERE id_volumen = %s",
                (id_vol,)
            )
            vol = cur.fetchone()
            if not vol:
                raise ValueError(f"Volumen {id_vol} no existe")
            precio = float(vol["precio_venta"] if isinstance(vol, dict) else vol[0])

            cur.execute("""
                INSERT INTO detalle_venta
                    (id_venta, id_volumen, precio_ven, cantidad)
                VALUES (%s,       %s,         %s,        %s)
            """, (id_ven, id_vol, precio, cantidad))

        # 4) Vaciar carrito
        cur.execute("SELECT id_carrito FROM carrito WHERE id_user = %s", (id_user,))
        fc = cur.fetchone()
        if fc:
            id_car = fc["id_carrito"] if isinstance(fc, dict) else fc[0]
            cur.execute("DELETE FROM detalle_carrito WHERE id_detalle_carrito = %s", (id_car,))
            cur.execute("DELETE FROM carrito WHERE id_carrito = %s", (id_car,))

        cn.commit()
        return id_ven