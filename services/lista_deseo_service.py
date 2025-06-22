from typing import Tuple, Dict
from pymysql.cursors import DictCursor
from pymysql.err import IntegrityError
from flask import current_app
import db.database as db


def agregar_lista_deseo(id_user: int, id_volumen: int) -> Tuple[Dict, int]:
    """
    Agrega un volumen a la lista de deseos de un usuario.
    Retorna (response_dict, status_code).
    """
    try:
        with db.obtener_conexion() as cn, cn.cursor() as cur:
            cur.execute(
                "INSERT INTO lista_deseo (id_user, id_volumen) VALUES (%s, %s)",
                (id_user, id_volumen)
            )
            cn.commit()
        return {"success": True, "message": "Volumen añadido a tu lista de deseos"}, 201

    except IntegrityError as ie:
        if ie.args[0] == 1062:
            return {"success": False, "message": "El volumen ya está en tu lista de deseos"}, 400
        current_app.logger.exception("agregar_lista_deseo - error de integridad")
        return {"success": False, "message": "Datos inválidos"}, 400

    except Exception:
        current_app.logger.exception("agregar_lista_deseo - error interno")
        return {"success": False, "message": "Error interno del servidor"}, 500



def eliminar_lista_deseo(id_user: int, id_volumen: int) -> Tuple[Dict, int]:
    """
    Elimina un volumen de la lista de deseos de un usuario.
    Retorna (response_dict, status_code).
    """
    try:
        with db.obtener_conexion() as cn, cn.cursor() as cur:
            cur.execute(
                "DELETE FROM lista_deseo WHERE id_user = %s AND id_volumen = %s",
                (id_user, id_volumen)
            )
            if cur.rowcount == 0:
                return {"success": False, "message": "Volumen no encontrado en tu lista de deseos"}, 404
            cn.commit()
        return {"success": True, "message": "Volumen eliminado de tu lista de deseos"}, 200

    except Exception:
        current_app.logger.exception("eliminar_lista_deseo - error interno")
        return {"success": False, "message": "Error interno del servidor"}, 500
