import pymysql
import db.database as db
import threading
import requests
import zipfile
import os
from io import BytesIO
from pymysql.cursors import DictCursor


def aprobar_proveedor(id_user, id_rol_proveedor=2):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT email FROM usuario WHERE id_user = %s", (id_user,))
                resultado = cursor.fetchone()

                if not resultado:
                    return False  

                email = resultado.get("email")

                cursor.execute(
                    "UPDATE usuario SET proveedor_aprobado = 1, id_rol = %s WHERE id_user = %s",
                    (id_rol_proveedor, id_user)
                )

                cursor.execute(
                    "INSERT INTO proveedor (id_user, id_rol, email_empresa) VALUES (%s, %s, %s)",
                    (id_user, id_rol_proveedor, email)
                )

            conexion.commit()
        return True
    except Exception as e:
        print("Error al aprobar proveedor:", e)
        return False
    
    

def rechazar_proveedor(id_user):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT email FROM usuario WHERE id_user = %s", (id_user,))
                resultado = cursor.fetchone()

                if not resultado:
                    return {"msg": "Usuario no encontrado"}, 404

                cursor.execute(
                    "UPDATE usuario SET proveedor_aprobado = 0, proveedor_solicitud = 0 WHERE id_user = %s",
                    (id_user,)
                )
            conexion.commit()
        return {"msg": "Proveedor rechazado correctamente"}, 200
    except Exception as e:
        print("Error al rechazar proveedor:", e)
        return {"msg": "Error interno del servidor"}, 500

def rechazar_proveedor_por_id(id_user):
    try:
        # 0) Obtengo el id del admin que rechaza desde el JWT
        email_admin = get_jwt_identity()
        with db.obtener_conexion() as conexion, conexion.cursor(DictCursor) as cursor:
            cursor.execute(
                "SELECT id_user FROM usuario WHERE email = %s",
                (email_admin,)
            )
            admin_row = cursor.fetchone()
            if not admin_row:
                return {"msg": "Admin no encontrado"}, 403
            id_admin = admin_row["id_user"] if isinstance(admin_row, dict) else admin_row[0]

            # 1) Verifico estado actual
            cursor.execute(
                "SELECT proveedor_solicitud, proveedor_aprobado "
                "FROM usuario WHERE id_user = %s",
                (id_user,)
            )
            fila = cursor.fetchone()
            if not fila:
                return {"msg": "Usuario no encontrado"}, 404

            if fila["proveedor_solicitud"] != 1 or fila["proveedor_aprobado"] != 0:
                return {
                    "msg": "No se realizó ningún cambio. Usuario no tenía solicitud pendiente"
                }, 400

            # 2) Actualizo flags y columnas de auditoría
            cursor.execute("""
                UPDATE usuario
                   SET proveedor_solicitud      = 0,
                       proveedor_aprobado       = 0,
                       fecha_modificacion       = NOW(),
                       id_usuario_modificacion  = %s
                 WHERE id_user = %s
                   AND proveedor_solicitud = 1
                   AND proveedor_aprobado  = 0
            """, (id_admin, id_user))
            conexion.commit()

        return {"msg": "Proveedor rechazado correctamente"}, 200

    except Exception as e:
        # imprime traza en logs para depuración
        import traceback; traceback.print_exc()
        return {"msg": "Error interno del servidor"}, 500
    
def obtener_proveedor_por_id(id_user):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id_proveedor, nombre_empresa
                    FROM proveedor
                    WHERE id_user = %s
                    """,
                    (id_user,)
                )
                proveedor = cursor.fetchone()
        if proveedor:
            return {
                "id_proveedor": proveedor.get("id_proveedor"),
                "nombre_empresa": proveedor.get("nombre_empresa")
            }
        return None
    except Exception as e:
        print("Error al obtener proveedor:", e)
        return None

def obtener_solicitud_publicacion():  
    try: 
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT sp.id_solicitud, u.email, sp.titulo, sp.autores,
                            sp.tipo,
                           sp.anio_publicacion, sp.precio_volumen, sp.restriccion_edad,
                           sp.genero_principal,
                           sp.editorial, sp.descripcion,
                           sp.url_portada, sp.url_zip, sp.fecha_solicitud
                    FROM solicitud_publicacion sp
                    INNER JOIN usuario u ON sp.id_user = u.id_user
                    WHERE sp.estado = 'pendiente'
                    """
                )
                solicitudes = cursor.fetchall()

        if solicitudes:
            return [
                {
                    "id_solicitud": fila["id_solicitud"],
                    "email": fila["email"],
                    "tipo": fila["tipo"],
                    "titulo": fila["titulo"],
                    "autores": fila["autores"],
                    "anio_publicacion": fila["anio_publicacion"],
                    "precio_volumen": fila["precio_volumen"],
                    "restriccion_edad": fila["restriccion_edad"],
                    "editorial": fila["editorial"],
                    "genero_principal": fila["genero_principal"],
                    "descripcion": fila["descripcion"],
                    "url_portada": fila["url_portada"],
                    "url_zip": fila["url_zip"],
                    "fecha_solicitud": fila["fecha_solicitud"]
                }
                for fila in solicitudes
            ]
        return []
    except Exception as e:
        print("Error al obtener solicitudes de publicación:", e)
        return []

def obtener_solicitud_publicacion_por_id(id_solicitud):
    """
    Devuelve los detalles de una sola solicitud de publicación por su ID,
    solo si está en estado 'pendiente'.
    """
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT 
                        sp.id_solicitud, 
                        u.email, 
                        sp.titulo, 
                        sp.autores,
                        sp.tipo, 
                        sp.anio_publicacion, 
                        sp.precio_volumen, 
                        sp.restriccion_edad,
                        sp.editorial, 
                        sp.genero_principal,
                        sp.descripcion,
                        sp.url_portada, 
                        sp.url_zip, 
                        sp.fecha_solicitud
                    FROM solicitud_publicacion sp
                    INNER JOIN usuario u ON sp.id_user = u.id_user
                    WHERE sp.id_solicitud = %s AND sp.estado = 'pendiente';
                    """,
                    (id_solicitud,)
                )
                fila = cursor.fetchone()
        if fila:
            return {
                "id_solicitud": fila["id_solicitud"],
                "email": fila["email"],
                "titulo": fila["titulo"],
                "autores": fila["autores"],
                "anio_publicacion": fila["anio_publicacion"],
                "precio_volumen": fila["precio_volumen"],
                "restriccion_edad": fila["restriccion_edad"],
                "editorial": fila["editorial"],
                "genero_principal": fila["genero_principal"],
                "descripcion": fila["descripcion"],
                "url_portada": fila["url_portada"],
                "url_zip": fila["url_zip"],
                "fecha_solicitud": fila["fecha_solicitud"]
            }
        return None
    except Exception as e:
        print("Error al obtener solicitud de publicación por ID:", e)
        return None


def obtener_solicitudes_proveedor():
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        u.id_user, 
                        u.email, 
                        CONCAT(l.nom_lec, ' ', l.apellidos_lec) AS nombre_completo, 
                        u.proveedor_fecha_solicitud
                    FROM usuario u
                    INNER JOIN lector l ON u.id_user = l.id_user
                    WHERE u.proveedor_solicitud = 1 AND u.proveedor_aprobado = 0
                    """
                )
                resultados = cursor.fetchall()

        if resultados:
            return [
                {
                    "id_user": fila["id_user"],
                    "email": fila["email"],
                    "nombre": fila["nombre_completo"],
                    "fecha_solicitud": fila["proveedor_fecha_solicitud"]
                }
                for fila in resultados
            ]
        return []
    except Exception as e:
        print("Error al obtener solicitudes de proveedor:", e)
        return []

def agregar_administrador(id_user, id_rol=3):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id_user FROM usuario WHERE id_user = %s", (id_user,))
                if cursor.fetchone() is None:
                    return {"success": False, "message": "Usuario no encontrado."}
                cursor.execute(
                    "UPDATE usuario SET id_rol = %s WHERE id_user = %s",
                    (id_rol, id_user)
                )
            conexion.commit()
        return {"success": True, "message": "Usuario actualizado a administrador."}
    except Exception as e:
        print("Error: ", e)
        return {"success": False, "message": f"Error: {e}"}

def obtener_id_admin_por_email(email):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                cursor.execute(
                    "SELECT id_user FROM usuario WHERE email = %s AND id_rol = 3",
                    (email,)
                )
                resultado = cursor.fetchone()
                if resultado:
                    return resultado["id_user"]
        return None
    except Exception as e:
        print("Error al obtener ID de administrador por email:", e)
        return None