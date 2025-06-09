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
        campos_obligatorios = ("id_user", "tipo", "titulo", "autores",
                               "url_portada", "url_zip")
        faltantes = [c for c in campos_obligatorios if not data.get(c)]
        if faltantes:
            return {"code": 1,
                    "msg": f"Faltan campos obligatorios: {', '.join(faltantes)}"}, 400

        # --- 2. Inserción --------------------------------
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                sql = """
                    INSERT INTO solicitud_publicacion
                      (id_user, tipo, titulo, autores,
                       anio_publicacion, precio_volumen, restriccion_edad,
                       editorial, genero_principal, descripcion,
                       url_portada, url_zip)
                    VALUES (%s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s)
                """
                cursor.execute(sql, (
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

        return {"code": 0,
                "msg": "Solicitud de publicación registrada correctamente."}, 201

    except Exception as e:
        print("Error al registrar solicitud:", e)
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
    
    



    
    



