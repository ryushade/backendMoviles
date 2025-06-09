import db.database as db
from datetime import datetime

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
        print("Error:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    
def registrar_solicitud(data):
    try:
        # Validaciones básicas
        if not data.get("url_portada") or not data.get("url_zip"):
            return {"code": 1, "msg": "Debes subir la portada y el archivo ZIP."}, 400

        if not data.get("titulo") or not data.get("autores") or not data.get("tipo"):
            return {"code": 1, "msg": "Faltan campos obligatorios como título, autores o tipo."}, 400

        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO solicitud_publicacion (
                        id_user, tipo, titulo, autores, anio_publicacion,
                        precio_volumen, restriccion_edad, editorial,
                        genero_principal, descripcion, url_portada, url_zip
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data["id_user"],
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

        return {"code": 0, "msg": "Solicitud de publicación registrada correctamente."}, 201

    except Exception as e:
        print("Error:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500


    
    



