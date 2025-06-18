from flask import Flask, request, jsonify, url_for, current_app
from flask_jwt_extended import jwt_required, JWTManager, create_access_token, get_jwt_identity
import db.database as db
import controller.auth_controller as auth_controller
import services.proveedor_service as proveedor_service
import services.admin_service as admin_service
import services.solicitud_service as solicitud_service
import controller.usuario_controller as usuario_controller
import controller.admin_controller as admin_controller
import services.genero_service as genero_service
import services.publicacion_service as publicacion_service
import services.lector_vol_service as vol_srv
import services.carrito_service as carrito_service
import services.historieta_service as hist_srv
import services.usuario_service as usuario_service
import stripe
import git
import os
import hmac
import hashlib
from werkzeug.utils import secure_filename
import uuid

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER_PORTADAS = os.path.join(BASE_DIR, "static", "uploads", "portadas")
UPLOAD_FOLDER_ZIPS     = os.path.join(BASE_DIR, "static", "uploads", "zips")
os.makedirs(UPLOAD_FOLDER_PORTADAS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_ZIPS, exist_ok=True)

app = Flask(__name__)
app.debug = True
app.config["JWT_SECRET_KEY"] = "secret"
jwt = JWTManager(app)




REPO_PATH = "/home/grupo1damb/mysite/backendMoviles"

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("GITHUB_WEBHOOK_SECRET no está configurado en las variables de entorno.")
WEBHOOK_SECRET = WEBHOOK_SECRET.encode()

def is_valid_signature(x_hub_signature, data):
    """Verifica la firma HMAC del webhook de GitHub."""
    if not x_hub_signature:
        return False
    try:
        sha_name, signature = x_hub_signature.split('=')
    except ValueError:
        return False
    if sha_name != 'sha1':
        return False
    mac = hmac.new(WEBHOOK_SECRET, msg=data, digestmod=hashlib.sha1)
    return hmac.compare_digest(mac.hexdigest(), signature)

@app.route('/update_server', methods=['POST'])
def update_server():
    signature = request.headers.get('X-Hub-Signature')
    if not is_valid_signature(signature, request.data):
        return jsonify({"msg": "Firma inválida"}), 403

    if request.headers.get('X-GitHub-Event') != "push":
        return jsonify({"msg": "Evento ignorado"}), 200

    try:
        repo = git.Repo(REPO_PATH)
        origin = repo.remotes.origin
        pull_result = origin.pull()
        return jsonify({"msg": "Repositorio actualizado", "resultado": str(pull_result)}), 200
    except Exception as e:
        return jsonify({"msg": "Error al hacer pull", "error": str(e)}), 500


@app.route("/auth", methods=["POST"]) 
def auth():
    return auth_controller.auth()


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload_portada", methods=["POST"])
@jwt_required()
def upload_portada():
    try:
        print("HEADERS:", dict(request.headers))           # <— confirma si llega Authorization
        if "file" not in request.files:
            return jsonify(msg="No se recibió archivo"), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify(msg="Archivo vacío"), 400
        if not allowed_file(file.filename):
            return jsonify(msg="Tipo de archivo no permitido"), 400

        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        destino = os.path.join(UPLOAD_FOLDER_PORTADAS, filename)
        print("GUARDANDO EN:", destino)                    # <— muestra la ruta real
        file.save(destino)                                 # <— si algo falla, saltará al except
        url = url_for("static", filename=f"uploads/portadas/{filename}", _external=True)
        return jsonify(url=url), 200

    except Exception as e:
        import traceback, sys
        traceback.print_exc()                              # <— traza completa en consola
        return jsonify(msg="Error interno", detail=str(e)), 500



@app.route("/upload_zip", methods=["POST"])
@jwt_required()
def upload_zip():
    if 'file' not in request.files:
        return jsonify({"msg": "No se recibió archivo"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"msg": "Archivo vacío"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER_ZIPS, filename)
    file.save(path)

    url = f"{request.host_url}static/uploads/zips/{filename}"
    return jsonify({"url": url}), 200

@app.route("/solicitudes/<int:id>/chapters", methods=["GET"])
@jwt_required()
def api_listar_capitulos(id):
    resp, status = solicitud_service.listar_capitulos(id)
    return jsonify(resp), status

@app.route("/solicitudes/<int:id>/<chapter>/<filename>")
def serve_chapter_page(id, chapter, filename):
    from services.solicitud_service import serve_chapter_page as handler
    return handler(id, chapter, filename)


@app.route("/solicitudes/<int:id>/chapters/<chapter>/pages", methods=["GET"])
@jwt_required()
def api_listar_paginas(id, chapter):
    resp, status = solicitud_service.listar_paginas(id, chapter)
    return jsonify(resp), status

@app.route("/api_aprobar_publicacion", methods=["POST"])
@jwt_required()
def api_aprobar_publicacion():
    # 1) Obtener al usuario autenticado
    email_admin = get_jwt_identity()          # tu JWT guarda el email
    if not email_admin:
        return jsonify({"msg": "No autenticado"}), 401

    # 2) Verificar que es administrador
    id_admin = admin_service.obtener_id_admin_por_email(email_admin)
    if id_admin is None:
        return jsonify({"msg": "No autorizado – se requiere rol ADMIN"}), 403

    # 3) Extraer id_solicitud del body JSON
    data = request.get_json(silent=True) or {}
    id_solicitud = data.get("id_solicitud")
    try:
        id_solicitud = int(id_solicitud)
    except (TypeError, ValueError):
        return jsonify({"msg": "Falta id_solicitud válido"}), 400
    if not id_solicitud:
        return jsonify({"msg": "Falta id_solicitud"}), 400

    # 4) Llamar al nuevo servicio (publicacion_service)
    resp, status = publicacion_service.aprobar_solicitud(id_solicitud, id_admin)
    return jsonify(resp), status


@app.route("/historietas/novedades", methods=["GET"])
@jwt_required()
def api_novedades():
    data = hist_srv.novedades()
    return jsonify(data), 200


# @app.route("/historietas/mas_vendidas", methods=["GET"])
# @jwt_required()
# def api_mas_vendidas():
#     data = hist_srv.mas_vendidas()
#     return jsonify(data), 200


@app.route("/historietas/genero/<int:id_genero>", methods=["GET"])
@jwt_required()
def api_por_genero(id_genero):
    data = hist_srv.por_genero(id_genero)
    return jsonify(data), 200


@app.route("/volumenes/<int:id_vol>", methods=["GET"])
def api_ficha(id_vol):
    data, st = vol_srv.ficha_volumen(id_vol)
    return jsonify(data), st

# capítulos y páginas
@app.route("/volumenes/<int:id_vol>/chapters", methods=["GET"])
def api_caps(id_vol):
    resp, st = vol_srv.listar_capitulos(id_vol)
    return jsonify(resp), st

@app.route("/volumenes/<int:id_vol>/chapters/<chapter>/pages", methods=["GET"])
def api_pages(id_vol, chapter):
    resp, st = vol_srv.listar_paginas(id_vol, chapter)
    return jsonify(resp), st

# imágenes
@app.route("/volumenes/<int:id>/<chapter>/<filename>")
def srv_vol_page(id, chapter, filename):
    return vol_srv.serve_page(id, chapter, filename)


@app.route("/carrito", methods=["GET"])
@jwt_required()
def api_listar_carrito():
    id_user = get_jwt_identity()           # según tu auth
    resp, status = carrito_service.listar_carrito(id_user)
    return jsonify(resp), status


@app.route("/carrito/agregar", methods=["POST"])
@jwt_required()
def api_agregar_carrito():
    data     = request.json or {}
    id_user  = get_jwt_identity()
    id_hist  = data.get("id_historieta")
    cant     = data.get("cantidad", 1)
    resp, st = carrito_service.agregar_al_carrito(id_user, id_hist, cant)
    return jsonify(resp), st


@app.route("/carrito/item", methods=["PUT"])
@jwt_required()
def api_actualizar_cantidad():
    d        = request.json or {}
    id_user  = get_jwt_identity()
    resp, st = carrito_service.actualizar_cantidad(
        id_user,
        d.get("id_historieta"),
        d.get("cantidad", 1)
    )
    return jsonify(resp), st


@app.route("/carrito/item", methods=["DELETE"])
@jwt_required()
def api_eliminar_item():
    id_user  = get_jwt_identity()
    id_hist  = request.args.get("id_historieta", type=int)
    resp, st = carrito_service.eliminar_item(id_user, id_hist)
    return jsonify(resp), st


@app.route("/carrito/vaciar", methods=["POST"])
@jwt_required()
def api_vaciar_carrito():
    id_user  = get_jwt_identity()
    resp, st = carrito_service.vaciar_carrito(id_user)
    return jsonify(resp), st

@app.route('/api_test', methods=['GET'])
def api_test():
    return jsonify({
        "status": "ok",
        "message": "Nunca hagan push de las variables de entorno a GitHub.",
        "autor": "grupo1damb"
    }), 200



@app.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    return auth_controller.protected()

@app.route("/api_registrarusuario", methods=["POST"])
def register():
    return usuario_controller.registrarUsuario()

@app.route("/api_actualizar_contraseña", methods=["POST"])
def cambiar_contraseña():
    data = request.json
    if not data or "email_user" not in data or "nueva_contrasena" not in data:
        return jsonify({"code": 1, "msg": "Datos de actualización no proporcionados"}), 400
    email_user = data["email_user"]
    nueva_contrasena = data["nueva_contrasena"]
    return usuario_service.actualizar_contraseña(email_user, nueva_contrasena)
    
    
@app.route("/api_eliminar_solicitud_proveedor", methods=["POST"])
@jwt_required()
def eliminar_solicitud_proveedor():
    data = request.json
    if not data or "id_user" not in data:
        return jsonify({"code": 1, "msg": "Datos de eliminación no proporcionados"}), 400
    id_user = data["id_user"]
    return usuario_service.eliminar_solicitud_proveedor(id_user)    

@app.route("/api_eliminar_solicitud_publicacion", methods=["POST"])
def eliminar_solicitud_publicacion():
    data = request.json
    if not data or "id_solicitud" not in data:
        return jsonify({"code": 1, "msg": "Datos de eliminación no proporcionados"}), 400
    id_solicitud = data["id_solicitud"]
    return proveedor_service.eliminar_solicitud_publicacion(id_solicitud)

@app.route("/api_registrar_administrador", methods=["POST"])
@jwt_required()
def registrar_administrador():
    return admin_controller.registrarAdministrador()

@app.route("/api_aprobar_proveedor", methods=["POST"])
@jwt_required()
def registrar_proveedor():
    return admin_controller.aprobar_proveedor()

@app.route("/api_rechazar_proveedor", methods=["POST"])
@jwt_required()
def rechaza_proveedor():
    data = request.get_json()
    id_objetivo = data.get("id_user")
    if id_objetivo is None:
        return jsonify({"msg": "Falta el id_user del usuario a rechazar"}), 400

    # llamamos a un servicio que trabaja por ID, no por email
    respuesta, status = admin_service.rechazar_proveedor_por_id(id_objetivo)
    return jsonify(respuesta), status

@app.route("/api_obtener_proveedor")
@jwt_required()
def obtener_proveedor():
    respuesta, status = admin_controller.get_solicitudes_proveedor()
    return jsonify(respuesta), status

@app.route("/api_solicitar_proveedor", methods=["PUT"])
@jwt_required()
def solicitar_proveedor():
    email = get_jwt_identity() 
    return proveedor_service.solicitar_proveedor(email)

@app.route("/api_registrar_solicitud", methods=["POST"])
@jwt_required()
def insertar_solicitud():
    data = request.json
    if not data:
        return jsonify({"code": 1, "msg": "Datos de solicitud no proporcionados"}), 400
    return proveedor_service.registrar_solicitud(data)

# @app.route("/api_aprobar_publicacion", methods=["POST"])
# @jwt_required()
# def aprobar_publicacion():
#     data = request.json
#     if not data or "id_solicitud" not in data or "id_admin" not in data:
#         return jsonify({"code": 1, "msg": "Datos de aprobación no proporcionados"}), 400
#     return admin_service.aprobar_publicacion(data["id_solicitud"], data["id_admin"])


@app.route("/api_obtener_generos", methods=["GET"])
@jwt_required()
def api_obtener_generos():
    tipo_material = request.args.get("tipo_material") or request.args.get("tipo")
    if not tipo_material:
        return jsonify({"msg": "Falta el parámetro tipo_material"}), 400

    generos = genero_service.obtener_generos_por_tipo(tipo_material)
    if generos is None:
        return jsonify({"msg": "Error al obtener géneros"}), 500

    if len(generos) > 0 and isinstance(generos[0], dict):
        generos_list = [{"id_genero": g["id_genero"], "nombre_genero": g["nombre_genero"]} for g in generos]
    else:
        generos_list = [{"id_genero": g[0], "nombre_genero": g[1]} for g in generos]
    return jsonify(generos_list), 200  # <-- solo la lista, no un dict

@app.route("/api_obtener_mis_solicitudes", methods=["GET"])
@jwt_required()
def obtener_solicitudes():
    email_user = get_jwt_identity()
    if not email_user:
        return jsonify({"success": False, "message": "Usuario no autenticado"}), 401

    respuesta, status = proveedor_service.getMisSolicitudes(email_user)
    return jsonify(respuesta), status


@app.route("/api_obtener_solicitud_historieta", methods=["GET"])
@jwt_required()
def obtener_solicitud_historieta():
    respuesta = admin_service.obtener_solicitud_publicacion()
    return jsonify(respuesta), 200


@app.route("/api_obtener_usuario_data")
@jwt_required()
def obtener_usuario_data():
    return usuario_controller.obtener_usuario_data()

@app.route("/api_solicitud_publicacion/<int:id_solicitud>", methods=["GET"])
@jwt_required()
def obtener_solicitud_historieta_por_id(id_solicitud):
    resultado = admin_service.obtener_solicitud_publicacion_por_id(id_solicitud)
    if resultado:
        return jsonify(resultado), 200
    else:
        return jsonify({"msg": "Solicitud no encontrada o no está pendiente"}), 404


@app.route('/api_obtener_dni_lec', methods=['POST'])
def obtener_dni_lec():
    try:
        data = request.json
        email_user = data.get("email_user")

        if not email_user:
            return jsonify({"code": 1, "msg": "Correo electrónico no proporcionado"}), 400

        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT l.dni_lec FROM lector l
                    JOIN usuario u ON l.id_user = u.id_user
                    WHERE u.email_user = %s
                """, (email_user,))
                result = cursor.fetchone()

        if result:
            return jsonify({"code": 0, "dni_lec": result[0]}), 200
        else:
            return jsonify({"code": 1, "msg": "No se encontró el dni_lec para el correo proporcionado"}), 404
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Error al obtener el dni_lec: {str(e)}"}), 500

@app.route("/")
def home():
    valor = "Grupo 01"
    return f"<p>Bienvenido, {valor}</p>"




#! Iniciar el servidor
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)