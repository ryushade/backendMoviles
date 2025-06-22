import db.database as db
from datetime import datetime
from pymysql.cursors import DictCursor
from flask import current_app


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
    

def get_items_usuario(id_user, tipo='purchases'):
    """
    Devuelve para el usuario:
      - purchases: id_venta, portada, titulo, autores, fecha
      - wishlist : id_lista, portada, titulo, autores, fecha_agregado
    """
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                if tipo == 'purchases':
                    sql = """
                    SELECT
                      v.id_ven                    AS id,
                      h.portada_url               AS portada,
                      h.titulo                    AS titulo,
                      GROUP_CONCAT(
                        CONCAT(a.nom_aut, ' ', a.apePat_aut)
                        SEPARATOR ', '
                      )                           AS autores,
                      v.fec_ven                   AS fecha
                    FROM venta v
                    JOIN detalle_venta dv 
                      ON v.id_ven = dv.id_venta
                    JOIN volumen vol 
                      ON dv.id_volumen = vol.id_volumen
                    JOIN historieta h 
                      ON vol.id_historieta = h.id_historieta
                    JOIN historieta_autor ha 
                      ON h.id_historieta = ha.id_historieta
                    JOIN autor a 
                      ON ha.id_autor = a.id_aut
                    WHERE v.id_user = %s
                    GROUP BY v.id_ven, vol.id_volumen
                    ORDER BY v.fec_ven DESC
                    """
                elif tipo == 'wishlist':
                    sql = """
                    SELECT
                      ld.id_lista                 AS id,
                      h.portada_url               AS portada,
                      h.titulo                    AS titulo,
                      GROUP_CONCAT(
                        CONCAT(a.nom_aut, ' ', a.apePat_aut)
                        SEPARATOR ', '
                      )                           AS autores,
                      ld.fecha_agregado           AS fecha
                    FROM lista_deseo ld
                    JOIN volumen vol 
                      ON ld.id_volumen = vol.id_volumen
                    JOIN historieta h 
                      ON vol.id_historieta = h.id_historieta
                    JOIN historieta_autor ha 
                      ON h.id_historieta = ha.id_historieta
                    JOIN autor a 
                      ON ha.id_autor = a.id_aut
                    WHERE ld.id_user = %s
                    GROUP BY ld.id_lista
                    ORDER BY ld.fecha_agregado DESC
                    """
                else:
                    return {"success": False, "message": "Tipo inválido"}, 400

                cursor.execute(sql, (id_user,))
                rows = cursor.fetchall()

        return {"success": True, "type": tipo, "data": rows}, 200

    except Exception as e:
        current_app.logger.exception(f"get_items_usuario ({tipo})")
        return {"success": False, "message": "Error interno del servidor"}, 500