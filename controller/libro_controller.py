from flask import jsonify
import services.libro_service as libro_service
from models.Libro import Libro

def libro_completo():
    try:
        libros = libro_service.obtener_libro_completo()
        if libros:
            # Convertir cada fila a un objeto `Libro` y luego a JSON
            libros_json = [Libro(*libro).json() for libro in libros]
            return jsonify({"code": 0, "msg": "Libros obtenidos correctamente", "data": libros_json}), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontraron libros"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener los libros: {str(e)}"}), 500

def libro_por_isbn(isbn_lib):
    try:
        libro = libro_service.obtener_libro_por_isbn(isbn_lib)
        if libro:
            libro_json = Libro(*libro).json()  # Convierte la fila a un objeto `Libro` y luego a JSON
            return jsonify({"code": 0, "msg": "Libro obtenido correctamente", "data": libro_json}), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontró el libro"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener el libro: {str(e)}"}), 500


def libros_comprados_por_usuario(email_user):
    try:
        libros = libro_service.obtener_libros_comprados_por_usuario(email_user)
        if libros:
            libros_json = [Libro(*libro).json() for libro in libros]
            return jsonify({"code": 0, "msg": "Libros comprados obtenidos correctamente", "data": libros_json}), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontraron libros comprados"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener los libros comprados: {str(e)}"}), 500




def libros_mas_vendidos():
    try:
        libros = libro_service.obtener_libros_mas_vendidos()
        if libros:
            libros_json = [Libro(*libro).json() for libro in libros]
            return jsonify({"code": 0, "msg": "Libros obtenidos correctamente", "data": libros_json}), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontraron libros"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener los libros: {str(e)}"}), 500


def libros_antiguos():
    try:
        libros = libro_service.obtener_libros_antiguos()
        if libros:
            libros_json = [Libro(*libro).json() for libro in libros]
            return jsonify({"code": 0, "msg": "Libros antiguos obtenidos correctamente", "data": libros_json}), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontraron libros antiguos"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener los libros antiguos: {str(e)}"}), 500

def libros_actuales():
    try:
        libros = libro_service.obtener_libros_actuales()
        if libros:
            libros_json = [Libro(*libro).json() for libro in libros]
            return jsonify({"code": 0, "msg": "Libros actuales obtenidos correctamente", "data": libros_json}), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontraron libros actuales"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener los libros actuales: {str(e)}"}), 500

def obtener_preview_libro_por_id(libro_id):
    try:
        libro = libro_service.obtener_detalle_libro_por_isbn(libro_id)
        if libro:
            return jsonify({
                "code": 0,
                "msg": "Libro obtenido correctamente",
                "data": {
                    "id": libro[0],  # Reemplaza con el índice correcto
                    "title": libro[1],  # Reemplaza con el índice correcto
                    "webReaderLink": libro[2]  # Reemplaza con el índice correcto
                }
            }), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontró el libro"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener el libro: {str(e)}"}), 500


def mejores_autores_libros():
    try:
        autores, libros = libro_service.obtener_libros_mejores_autores()
        if autores and libros:
            autores_json = [
    {
        "id_aut": autor[0],  # Cambia "id_aut" a índice numérico 0
        "nom_aut": autor[1],  # Cambia "nom_aut" a índice numérico 1
        "apePat_aut": autor[2],  # Cambia "apePat_aut" a índice numérico 2
        "apeMat_aut": autor[3]  # Cambia "apeMat_aut" a índice numérico 3
    }
    for autor in autores
]
            libros_json = [Libro(*libro).json() for libro in libros]

            return jsonify({
                "code": 0,
                "msg": "Autores y sus libros obtenidos correctamente",
                "autores": autores_json,
                "libros": libros_json
            }), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontraron autores o libros"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener los autores o libros: {str(e)}"}), 500