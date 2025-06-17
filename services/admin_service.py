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
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
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

                cursor.execute(
                    "UPDATE usuario "
                    "SET proveedor_aprobado = 0, proveedor_solicitud = 0 "
                    "WHERE id_user = %s",
                    (id_user,)
                )
                conexion.commit()

        return {"msg": "Proveedor rechazado correctamente"}, 200

    except Exception as e:
        print("Error al rechazar proveedor:", e)
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
                           g.nombre_genero AS genero_principal,
                           sp.editorial, sp.descripcion,
                           sp.url_portada, sp.url_zip, sp.fecha_solicitud
                    FROM solicitud_publicacion sp
                    INNER JOIN usuario u ON sp.id_user = u.id_user
                    LEFT JOIN genero g ON sp.id_genero = g.id_genero
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
                        g.nombre_genero AS genero_principal,
                        sp.descripcion,
                        sp.url_portada, 
                        sp.url_zip, 
                        sp.fecha_solicitud
                    FROM solicitud_publicacion sp
                    INNER JOIN usuario u ON sp.id_user = u.id_user
                    LEFT JOIN genero g ON sp.id_genero = g.id_genero
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


def aprobar_publicacion():
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute
                
    
    except Exception as e:
        print("Error al aprobar publicación:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500
    
def aprobar_solicitud(id_solicitud, id_admin):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor(dictionary=True) as cur:
                cur.execute("SELECT * FROM solicitud_publicacion "
                            "WHERE id_solicitud=%s AND estado='pendiente'",
                            (id_solicitud,))
                row = cur.fetchone()
                if not row:
                    return {"code": 1, "msg": "Solicitud no encontrada o ya procesada"}, 404

                conexion.start_transaction()

                cur.execute("""
                    INSERT INTO historieta
                      (titulo, descripcion, portada_url, tipo,
                       restriccion_edad, anio_publicacion,
                       estado, id_editorial)
                    VALUES (%s,%s,%s,%s,%s,%s,'aprobado',
                       (SELECT id_editorial FROM editorial WHERE nombre_editorial=%s LIMIT 1))
                """, (
                    row["titulo"],
                    row["descripcion"],
                    row["url_portada"],
                    row["tipo"],
                    row["restriccion_edad"],
                    row["anio_publicacion"],
                    row["editorial"]
                ))
                id_hist = cur.lastrowid

                # 4) Insertar volumen inicial
                cur.execute("""
                    INSERT INTO volumen
                      (id_historieta, numero_volumen, titulo_volumen,
                       formato_contenido, ruta_contenido, precio_venta,
                       fecha_publicacion)
                    VALUES (%s, 1, %s, 'zip', %s, %s, CURDATE())
                """, (
                    id_hist,
                    f"{row['titulo']} Vol.1",
                    row["url_zip"],
                    row["precio_volumen"] or 0.00
                ))
                id_vol = cur.lastrowid

                # 5) Registrar autores (separados por coma)
                for nombre in [a.strip() for a in row["autores"].split(",") if a.strip()]:
                    cur.execute("SELECT id_autor FROM autor WHERE nombre_autor=%s", (nombre,))
                    res = cur.fetchone()
                    if res:
                        id_autor = res["id_autor"]
                    else:
                        cur.execute("INSERT INTO autor (nombre_autor) VALUES (%s)", (nombre,))
                        id_autor = cur.lastrowid
                    cur.execute("INSERT IGNORE INTO historieta_autor VALUES (%s,%s)",
                                (id_hist, id_autor))

                # 6) Registrar género principal
                genero = row["genero_principal"]
                cur.execute("SELECT id_genero FROM genero WHERE nombre_genero=%s", (genero,))
                res = cur.fetchone()
                if res:
                    id_gen = res["id_genero"]
                else:
                    cur.execute("INSERT INTO genero (nombre_genero) VALUES (%s)", (genero,))
                    id_gen = cur.lastrowid
                cur.execute("INSERT IGNORE INTO historieta_genero VALUES (%s,%s)",
                            (id_hist, id_gen))

                # 7) Marcar solicitud como aprobada + referencia
                cur.execute("""
                    UPDATE solicitud_publicacion
                    SET estado='aprobado', id_historieta_creada=%s
                    WHERE id_solicitud=%s
                """, (id_hist, id_solicitud))

                # 8) Commit
                conexion.commit()

        # Lanzar job asíncrono para extraer ZIP y poblar páginas…
        lanzar_job_import_paginas(id_vol, row["url_zip"])

        return {"code": 0, "msg": "Historieta publicada con ID " + str(id_hist)}, 200

    except Exception as e:
        print("Error al aprobar:", e)
        if conexion.in_transaction:
            conexion.rollback()
        return {"code": 1, "msg": "Error interno"}, 500

def lanzar_job_import_paginas(id_volumen, url_zip):
    def job():
        try:
            # 1. Descargar el ZIP
            response = requests.get(url_zip)
            response.raise_for_status()
            zip_bytes = BytesIO(response.content)

            # 2. Extraer imágenes en una carpeta específica dentro de static
            extract_dir = os.path.join('static', 'volumenes', str(id_volumen))
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_bytes) as zip_ref:
                zip_ref.extractall(extract_dir)

            # 3. Insertar cada imagen en la tabla pagina con su orden
            imagenes = sorted([f for f in os.listdir(extract_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            with db.obtener_conexion() as conexion:
                with conexion.cursor() as cursor:
                    for idx, nombre_img in enumerate(imagenes, start=1):
                        ruta_img = os.path.join('volumenes', str(id_volumen), nombre_img)  # Ruta relativa a static
                        cursor.execute(
                            """
                            INSERT INTO pagina (id_volumen, numero_pagina, ruta_imagen)
                            VALUES (%s, %s, %s)
                            """,
                            (id_volumen, idx, ruta_img)
                        )
                conexion.commit()
            print(f"Importación de páginas completada para volumen {id_volumen}")
        except Exception as e:
            print(f"Error en job de importación de páginas: {e}")

    threading.Thread(target=job, daemon=True).start()

