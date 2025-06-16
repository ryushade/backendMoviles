# services/solicitud_service.py

import os
import zipfile
from flask import current_app, url_for
import db.database as db
from pymysql.cursors import DictCursor

# Debe coincidir con la carpeta donde subes los zips en tu main app
# Si la defines en tu módulo principal, importa la constante en lugar de repetirla.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER_ZIPS = os.path.join(BASE_DIR, "..", "static", "uploads", "zips")


def listar_capitulos(id_solicitud):
    """
    Retorna la lista de carpetas (capítulos) dentro del ZIP de la solicitud.
    """
    try:
        # 1) Obtener la URL del ZIP desde la BD
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                cursor.execute(
                    "SELECT url_zip FROM solicitud_publicacion WHERE id_solicitud = %s",
                    (id_solicitud,)
                )
                fila = cursor.fetchone()

        if not fila:
            return {"code": 1, "msg": "Solicitud no encontrada"}, 404

        # 2) Construir la ruta local al ZIP
        zip_url  = fila["url_zip"]
        zip_name = os.path.basename(zip_url)
        zip_path = os.path.join(UPLOAD_FOLDER_ZIPS, zip_name)

        if not os.path.isfile(zip_path):
            return {"code": 1, "msg": "ZIP no encontrado en el servidor"}, 404

        # 3) Leer nombres de carpeta
        with zipfile.ZipFile(zip_path, "r") as zf:
            entries = zf.namelist()
        # Extraer la parte anterior a la primera '/' para cada archivo
        chapters = {
            e.split("/", 1)[0]
            for e in entries
            if "/" in e and not e.endswith("/")
        }

        return {"code": 0, "chapters": sorted(chapters)}, 200

    except zipfile.BadZipFile:
        return {"code": 1, "msg": "Archivo ZIP corrupto"}, 500
    except Exception as e:
        print("Error en servicio listar_capitulos:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500


def listar_paginas(id_solicitud, chapter_name):
    """
    Retorna la lista de URLs para cada imagen dentro de un capítulo concreto.
    """
    try:
        # 1) Obtener URL del ZIP
        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                cursor.execute(
                    "SELECT url_zip FROM solicitud_publicacion WHERE id_solicitud = %s",
                    (id_solicitud,)
                )
                fila = cursor.fetchone()

        if not fila:
            return {"code": 1, "msg": "Solicitud no encontrada"}, 404

        zip_url  = fila["url_zip"]
        zip_name = os.path.basename(zip_url)
        zip_path = os.path.join(UPLOAD_FOLDER_ZIPS, zip_name)

        if not os.path.isfile(zip_path):
            return {"code": 1, "msg": "ZIP no encontrado en el servidor"}, 404

        # 2) Recorre el ZIP y genera una URL por cada archivo dentro de chapter_name/
        pages = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            for entry in sorted(zf.namelist()):
                if entry.startswith(f"{chapter_name}/") and not entry.endswith("/"):
                    filename = os.path.basename(entry)
                    # construye la URL apuntando al endpoint que sirve la imagen
                    pages.append(
                        url_for(
                            "serve_chapter_page",
                            id=id_solicitud,
                            chapter=chapter_name,
                            filename=filename,
                            _external=True
                        )
                    )

        return {"code": 0, "pages": pages}, 200

    except zipfile.BadZipFile:
        return {"code": 1, "msg": "Archivo ZIP corrupto"}, 500
    except Exception as e:
        print("Error en servicio listar_paginas:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500
