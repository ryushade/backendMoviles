import db.database as db
from datetime import datetime


def obtener_usuario(email):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT id_user, email, pass, id_rol, proveedor_solicitud, proveedor_aprobado, proveedor_fecha_solicitud FROM usuario WHERE email = %s", (email,))
                usuario = cursor.fetchone()
        return usuario
    except Exception as e:
        print("Error: ", e)
        return None

def obtener_usuario_id(id):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT id_user, email, pass, id_rol, proveedor_solicitud, proveedor_aprobado, proveedor_fecha_solicitud FROM usuario WHERE id_user = %s", (id,))
                usuario = cursor.fetchone()
        return usuario
    except Exception as e:
        print("Error: ", e)
        return None

    
def registrar_usuario(email_user, pass_user, id_rol, proveedor_solicitud=False, proveedor_fecha_solicitud=None):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO usuario (
                        email, pass, id_rol, proveedor_solicitud, proveedor_aprobado, proveedor_fecha_solicitud
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        email_user,
                        pass_user,
                        id_rol,
                        int(proveedor_solicitud),
                        0,
                        proveedor_fecha_solicitud
                    )
                )
                id_user = cursor.lastrowid
            conexion.commit()
        return id_user
    except Exception as e:
        print("Error:", e)
        return None
