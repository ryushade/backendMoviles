import db.database as db
from datetime import datetime
from pymysql.cursors import DictCursor


def obtener_usuario(email):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT id_user, email, pass, id_rol, proveedor_solicitud, proveedor_aprobado, proveedor_fecha_solicitud FROM usuario WHERE email = %s", (email,))
                usuario = cursor.fetchone()
        return usuario  # <-- retorna el dict directamente
    except Exception as e:
        print("Error: ", e)
        return None


def get_historietas():
    """
    Devuelve hasta 15 historietas aprobadas para que el cliente
    las cargue y filtre localmente en el frontend.
    """
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT
                      id_historieta,
                      titulo,
                      descripcion,
                      portada_url,
                      tipo
                    FROM historieta
                    WHERE estado = 'aprobado'
                    ORDER BY fecha_creacion DESC
                    LIMIT 15
                """)
                rows = cursor.fetchall()

        return {"success": True, "data": rows}, 200

    except Exception as e:
        print("Error en get_historietas:", e)
        return {"success": False, "message": "Error interno del servidor"}, 500



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
    

def obtener_usuario_data_manga(email):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        CONCAT(l.nom_lec, ' ', l.apellidos_lec) AS nombre_completo, 
                        u.email, u.id_rol,
                        u.proveedor_solicitud
                    FROM lector l
                    INNER JOIN usuario u ON l.id_user = u.id_user
                    WHERE u.email = %s
                    """, (email,))
                usuario = cursor.fetchone()
        if usuario:
            return {
                "nombre": usuario['nombre_completo'],  
                "email": usuario['email'],
                "id_rol": usuario['id_rol'],
                "proveedor_solicitud": usuario['proveedor_solicitud'] == 1  # convierte a booleano
            }
        return None
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
    
    
def actualizar_contraseña(email_user, nueva_contrasena):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE usuario 
                    SET pass = %s 
                    WHERE email = %s
                    """,
                    (nueva_contrasena, email_user)
                )
            conexion.commit()
        return True
    except Exception as e:
        print("Error al actualizar la contraseña:", e)
        return False

def eliminar_solicitud_proveedor(id_user):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE usuario
                    SET proveedor_solicitud = 0, proveedor_fecha_solicitud = NULL
                    WHERE id_user = %s
                    """, (id_user,)
                )
                conexion.commit()

                if cursor.rowcount == 0:
                    return {"code": 1, "msg": "Usuario no encontrado"}, 404

                return {"code": 0, "msg": "Solicitud de proveedor eliminada correctamente."}, 200
    except Exception as e:
        print("Error:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    
