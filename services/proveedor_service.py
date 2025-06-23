import db.database as db
from datetime import datetime
from pymysql.cursors import DictCursor
from flask import current_app

def solicitar_proveedor(email):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE usuario
                    SET proveedor_solicitud = 1, proveedor_fecha_solicitud = NOW()
                    WHERE email = %s
                    """, (email.strip(),))
                    
                conexion.commit()

                if cursor.rowcount == 0:
                    return {"code": 1, "msg": "Usuario no encontrado"}, 404

                return {"code": 0, "msg": "Solicitud de proveedor registrada correctamente."}, 200
    except Exception as e:
        print("Error en solicitar_proveedor:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500

def cancelar_solicitud_proveedor(email):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE usuario
                    SET proveedor_solicitud = 0, proveedor_fecha_solicitud = NULL
                    WHERE email = %s
                    """, (email.strip(),))
                    
                conexion.commit()

                if cursor.rowcount == 0:
                    return {"code": 1, "msg": "Usuario no encontrado"}, 404

                return {"code": 0, "msg": "Solicitud de proveedor cancelada correctamente."}, 200
    except Exception as e:
        print("Error:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    
def registrar_solicitud(email_user, data):
    try:
        # Validar campos obligatorios (sin id_user)
        campos_obligatorios = ("tipo", "titulo", "autores",
                               "url_portada", "url_zip")
        faltantes = [c for c in campos_obligatorios if not data.get(c)]
        if faltantes:
            return {
                "code": 1,
                "msg": f"Faltan campos obligatorios: {', '.join(faltantes)}"
            }, 400

        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                # 1) Obtener id_user a partir del email
                cursor.execute(
                    "SELECT id_user FROM usuario WHERE email = %s",
                    (email_user,)
                )
                fila = cursor.fetchone()
                if not fila:
                    return {"code": 1, "msg": "Usuario no encontrado"}, 404
                id_user = fila["id_user"]

                # 2) Insertar solicitud con estado 'pendiente'
                sql = """
                    INSERT INTO solicitud_publicacion (
                      id_user, tipo, titulo, autores,
                      anio_publicacion, precio_volumen, restriccion_edad,
                      editorial, genero_principal, descripcion,
                      url_portada, url_zip, estado
                    ) VALUES (
                      %s, %s, %s, %s,
                      %s, %s, %s,
                      %s, %s, %s,
                      %s, %s, 'pendiente'
                    )
                """
                cursor.execute(sql, (
                    id_user,
                    data["tipo"],
                    data["titulo"],
                    data["autores"],
                    data.get("anio_publicacion"),
                    data.get("precio_volumen"),
                    data.get("restriccion_edad"),
                    data.get("editorial"),
                    data.get("genero_principal"),
                    data.get("descripcion"),
                    data["url_portada"],
                    data["url_zip"]
                ))
                conexion.commit()
                nuevo_id = cursor.lastrowid

        return {
            "code": 0,
            "msg": "Solicitud de publicación registrada correctamente.",
            "id_solicitud": nuevo_id
        }, 201

    except Exception as e:
        current_app.logger.exception("registrar_solicitud")
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    
def getSolicitudHistorieta(id_solicitud):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM solicitud_publicacion
                    WHERE id_solicitud = %s
                    """, (id_solicitud,))
                solicitud = cursor.fetchone()
                
                if not solicitud:
                    return {"code": 1, "msg": "Solicitud no encontrada"}, 404
                
                return {"code": 0, "solicitud": solicitud}, 200

    except Exception as e:
        print("Error al obtener solicitud de historieta:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    
    
def getMisSolicitudes(email_user):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                sql = """
                    SELECT
                      sp.id_solicitud,
                      sp.titulo,
                      sp.tipo,
                      DATE_FORMAT(
                        sp.fecha_solicitud,
                        '%%Y-%%m-%%d %%H:%%i:%%s'
                      ) AS fecha_solicitud,
                      sp.estado
                    FROM solicitud_publicacion sp
                    JOIN usuario u
                      ON sp.id_user = u.id_user
                    WHERE u.email = %s
                      AND sp.estado IN ('pendiente','rechazado','aprobado')
                    ORDER BY sp.fecha_solicitud DESC
                """
                cursor.execute(sql, (email_user,))
                solicitudes = cursor.fetchall()

        return {"success": True, "data": solicitudes}, 200

    except Exception:
        current_app.logger.exception("getMisSolicitudes")
        return {"success": False, "message": "Error interno del servidor"}, 500

    
def editar_solicitud_publicacion(data):
    try:
        campos = [
            "titulo", "tipo", "autores", "anio_publicacion", "precio_volumen",
            "restriccion_edad", "editorial", "genero_principal", "descripcion",
            "url_portada", "url_zip"
        ]
        set_clause = ", ".join([f"{campo} = %s" for campo in campos])

        valores = [data.get(campo) for campo in campos]
        valores.append(data["id_solicitud"])  # El id para el WHERE

        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE solicitud_publicacion
                    SET {set_clause}
                    WHERE id_solicitud = %s
                    """,
                    valores
                )
                conexion.commit()

        if cursor.rowcount == 0:
            return {"code": 1, "msg": "Solicitud no encontrada"}, 404

        return {"code": 0, "msg": "Solicitud actualizada correctamente."}, 200

    except Exception as e:
        print("Error al editar solicitud:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    
def rechazar_solicitud_publicacion(id_solicitud):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE solicitud_publicacion
                       SET estado = 'rechazado',
                           fecha_respuesta = NOW()
                     WHERE id_solicitud = %s
                    """,
                    (id_solicitud,)
                )
                conexion.commit()

                if cursor.rowcount == 0:
                    return {"code": 1, "msg": "Solicitud no encontrada"}, 404

                return {"code": 0, "msg": "Solicitud rechazada correctamente."}, 200

    except Exception as e:
        print("Error al rechazar solicitud:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500




            






