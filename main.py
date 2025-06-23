from flask import Flask, request, jsonify, url_for, current_app
from werkzeug.exceptions import RequestEntityTooLarge
from pymysql.cursors import DictCursor
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
import services.comentario_service as comentario_service
import services.stripe_service as stripe_service
import services.venta_service as venta_service
import services.lector_vol_service as vol_srv
import services.lista_deseo_service as lista_deseo_service
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
import firebase_admin
from firebase_admin import credentials

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER_PORTADAS = os.path.join(BASE_DIR, "static", "uploads", "portadas")
UPLOAD_FOLDER_ZIPS     = os.path.join(BASE_DIR, "static", "uploads", "zips")
os.makedirs(UPLOAD_FOLDER_PORTADAS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_ZIPS, exist_ok=True)

app = Flask(__name__)
app.debug = True
app.config["JWT_SECRET_KEY"] = "secret"
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB
jwt = JWTManager(app)


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sa_path  = os.path.join(BASE_DIR, 'db', 'firebase-sa.json')

if not firebase_admin._apps:
    cred = credentials.Certificate(sa_path)
    firebase_admin.initialize_app(cred)

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

from firebase_admin import auth as firebase_auth

@app.route("/auth_google", methods=["POST"])
def auth_google():
    id_token = request.json.get("id_token")
    print("ID_TOKEN RECIBIDO:", id_token)
    try:
        # 1) Verificamos el ID token de Firebase
        decoded = firebase_auth.verify_id_token(id_token)
        email = decoded.get("email")
        if not email:
            raise ValueError("No viene email en el token")

        # 2) Comprobamos/creamos al usuario en nuestra BD
        with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
            # ¿Ya existe?
            cur.execute("SELECT id_user FROM usuario WHERE email = %s", (email,))
            fila = cur.fetchone()

            if not fila:
                # a) Insertamos en usuario
                cur.execute(
                    "INSERT INTO usuario (email, pass, id_rol) VALUES (%s, %s, %s)",
                    (email, "", 1)
                )
                new_user_id = cur.lastrowid
                print(f"Usuario nuevo creado: id_user={new_user_id}")

                # b) Insertamos registro en lector (si es tu comportamiento deseado)
                cur.execute(
                    "INSERT INTO lector (dni_lec, nom_lec, apellidos_lec, id_user) "
                    "VALUES (%s, %s, %s, %s)",
                    ("", "", "", new_user_id)
                )
                print(f"Lector asociado creado para id_user={new_user_id}")

                cn.commit()

        # 3) Generamos nuestro JWT interno
        access_token = create_access_token(identity=email)
        return jsonify({"access_token": access_token}), 200

    except Exception as e:
        current_app.logger.exception("auth_google falló")
        return jsonify({"msg": f"Token inválido o error interno: {str(e)}"}), 401

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

@app.route("/api_borrar_solicitud_publicacion/<int:id_solicitud>", methods=["DELETE"])
@jwt_required()
def borrar_solicitud_publicacion(id_solicitud):
    resp, status = proveedor_service.borrar_solicitud_publicacion(id_solicitud)
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


@app.route("/proveedor_dashboard", methods=["GET"])
@jwt_required()
def obtener_dashboard_proveedor():
    # 1) identificamos al proveedor
    email = get_jwt_identity()
    with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
        cur.execute("SELECT id_user FROM usuario WHERE email = %s", (email,))
        fila = cur.fetchone()
        if not fila:
            return jsonify({"msg":"Usuario no encontrado"}), 404
        id_user = fila["id_user"]

        # 2) solicitudes pendientes
        cur.execute("""
            SELECT COUNT(*) AS pendientes
            FROM solicitud_publicacion
            WHERE id_user=%s
              AND estado='pendiente'
        """, (id_user,))
        pendientes = cur.fetchone()["pendientes"]

        # 3) historietas aprobadas para este proveedor
        #    (aquellas que ya tienen id_historieta_creada en sus solicitudes)
        cur.execute("""
            SELECT COUNT(*) AS activas
            FROM historieta h
            WHERE h.estado='aprobado'
              AND h.id_historieta IN (
                  SELECT sp.id_historieta_creada
                  FROM solicitud_publicacion sp
                  WHERE sp.id_user=%s
                    AND sp.id_historieta_creada IS NOT NULL
              )
        """, (id_user,))
        activas = cur.fetchone()["activas"]

        # 4) lista de volúmenes de esas historietas
        cur.execute("""
            SELECT v.id_volumen,
                   v.titulo_volumen,
                   h.titulo         AS historieta,
                   v.precio_venta,
                   v.fecha_subida
            FROM volumen v
            JOIN historieta h
              ON h.id_historieta = v.id_historieta
            WHERE h.id_historieta IN (
                SELECT sp.id_historieta_creada
                FROM solicitud_publicacion sp
                WHERE sp.id_user=%s
                  AND sp.id_historieta_creada IS NOT NULL
            )
            ORDER BY v.fecha_subida DESC
        """, (id_user,))
        volumenes = cur.fetchall()

    return jsonify({
        "activas": activas,
        "pendientes": pendientes,
        "volumenes": volumenes
    }), 200


@app.route("/admin_dashboard", methods=["GET"])
@jwt_required()
def api_dashboard_admin():
    with db.obtener_conexion() as conexion:
        with conexion.cursor(DictCursor) as cursor:

            # 1) Proveedores pendientes
            cursor.execute("""
                SELECT COUNT(*) AS total 
                FROM usuario 
                WHERE proveedor_solicitud = 1
            """)
            proveedores_pendientes = cursor.fetchone()["total"]

            # 2) Publicaciones pendientes
            cursor.execute("""
                SELECT COUNT(*) AS total 
                FROM solicitud_publicacion 
                WHERE estado = 'pendiente'
            """)
            publicaciones_pendientes = cursor.fetchone()["total"]

            # 3) Solicitudes por día (últimos 7 días)
            cursor.execute("""
                SELECT DATE(fecha_solicitud) AS fecha, COUNT(*) AS total
                FROM solicitud_publicacion
                WHERE fecha_solicitud >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY fecha
                ORDER BY fecha
            """)
            solicitudes_por_dia = cursor.fetchall()

            # 4) Solicitudes recientes (últimas 5)
            cursor.execute("""
                SELECT s.id_solicitud, s.titulo, s.fecha_solicitud, u.email
                FROM solicitud_publicacion s
                JOIN usuario u ON s.id_user = u.id_user
                ORDER BY s.fecha_solicitud DESC
                LIMIT 5
            """)
            recientes = cursor.fetchall()

    return jsonify({
        "code": 0,
        "stats": {
            "proveedores_pendientes": proveedores_pendientes,
            "publicaciones_pendientes": publicaciones_pendientes
        },
        "grafico": solicitudes_por_dia,
        "recientes": recientes
    }), 200




@app.route("/historietas/genero/<int:id_genero>", methods=["GET"])
@jwt_required()
def api_por_genero(id_genero):
    data = hist_srv.por_genero(id_genero)
    return jsonify(data), 200


@app.route("/volumenes/<int:id_vol>", methods=["GET"])
def api_ficha(id_vol):
    data, st = vol_srv.ficha_volumen(id_vol)
    return jsonify(data), st


@app.route("/volumenes/<int:id_vol>/chapters", methods=["GET"])
@jwt_required()
def api_listar_capitulos_volumen(id_vol):
    email_user = get_jwt_identity()
    current_app.logger.debug(f"[api_listar_capitulos_volumen] email: {email_user}, volumen: {id_vol}")

    comprado = vol_srv.usuario_compro_volumen(email_user, id_vol)
    current_app.logger.debug(f"[api_listar_capitulos_volumen] comprado: {comprado}")

    resp, status = vol_srv.listar_capitulos(id_vol)
    if status != 200 or resp.get("code") != 0:
        return jsonify(resp), status

    # Extraemos tipo y capítulos
    tipo     = resp.get("tipo")
    chapters = resp.get("chapters", [])

    if not comprado:
        return jsonify({
            "code":     0,
            "tipo":     tipo,
            "chapters": chapters[:1],
            "locked":   True
        }), 200

    return jsonify({
        "code":     0,
        "tipo":     tipo,
        "chapters": chapters,
        "locked":   False
    }), 200


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


from services.lector_vol_service import usuario_compro_volumen

@app.route("/carrito/agregar", methods=["POST"])
@jwt_required()
def api_agregar_carrito():
    data        = request.json or {}
    id_user     = get_jwt_identity()
    id_volumen  = data.get("id_volumen")
    cant        = data.get("cantidad", 1)

    if not id_volumen:
        return jsonify({"msg": "Falta id_volumen"}), 400

    # Verificar si el volumen ya fue comprado
    email_user = id_user  # si `get_jwt_identity()` retorna email
    if usuario_compro_volumen(email_user, id_volumen):
        return jsonify({"msg": "Ya compraste este volumen"}), 400

    resp, st = carrito_service.agregar_al_carrito(id_user, id_volumen, cant)
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
    id_user    = get_jwt_identity()
    id_volumen = request.args.get("id_volumen", type=int)  # antes eras id_historieta

    if id_volumen is None:
        return jsonify({"code": 1, "msg": "Falta id_volumen"}), 400

    resp, st = carrito_service.eliminar_item(id_user, id_volumen)
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

@app.route("/api_rechazar_solicitud_publicacion", methods=["POST"])
@jwt_required()
def rechazar_solicitud_publicacion():
    data = request.get_json(silent=True) or {}
    if "id_solicitud" not in data:
        return jsonify({"code": 1, "msg": "Datos de rechazo no proporcionados"}), 400
    id_solicitud = data["id_solicitud"]
    return proveedor_service.rechazar_solicitud_publicacion(id_solicitud)


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

@app.route("/api_cancelar_solicitud_proveedor", methods=["PUT"])
@jwt_required()
def cancelar_solicitud_proveedor():
    email = get_jwt_identity() 
    return proveedor_service.cancelar_solicitud_proveedor(email)

@app.route("/api_lista_busqueda", methods=["GET"])
@jwt_required()
def lista_busqueda():
    try:
        user_identity = get_jwt_identity()
        q = request.args.get('q', '').strip()

        with db.obtener_conexion() as conexion:
            with conexion.cursor(DictCursor) as cursor:
                sql = """
                    SELECT
                        id_historieta,
                        titulo,
                        descripcion,
                        portada_url,
                        tipo
                    FROM historieta
                    WHERE estado = 'aprobado'
                      AND titulo LIKE %s
                    ORDER BY fecha_creacion DESC
                    LIMIT 15
                """
                like_pattern = f"%{q}%"
                cursor.execute(sql, (like_pattern,))
                resultados = cursor.fetchall()

        return jsonify({"success": True, "data": resultados}), 200

    except Exception as e:
        print("Error en lista_busqueda:", e)
        return jsonify({"success": False, "message": "Error interno del servidor"}), 500
        

@app.route("/api_registrar_solicitud", methods=["POST"])
@jwt_required()
def insertar_solicitud():
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"code": 1, "msg": "Datos de solicitud no proporcionados"}), 400
    email_user = get_jwt_identity()
    return proveedor_service.registrar_solicitud(email_user, data)


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
    current_app.logger.debug(f"[api_obtener_mis_solicitudes] email_user: {email_user}")

    respuesta, status = proveedor_service.getMisSolicitudes(email_user)
    current_app.logger.debug(
        f"[api_obtener_mis_solicitudes] filas devueltas: {len(respuesta['data'])}"
    )

    return jsonify(respuesta), status


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
    
@app.route("/api_obtener_solicitud_historieta", methods=["GET"])
@jwt_required()
def api_obtener_solicitud_historieta():
    """
    GET /api_obtener_solicitud_historieta
    Devuelve todas las solicitudes de publicación de historietas en estado 'pendiente'.
    """
    try:
        # Llama al servicio que ya tienes implementado
        solicitudes = admin_service.obtener_solicitud_publicacion()
        # Si quieres envolver la respuesta en un objeto:
        # return jsonify({"solicitudes": solicitudes}), 200
        return jsonify(solicitudes), 200
    except Exception as e:
        current_app.logger.exception("api_obtener_solicitud_historieta - error")
        return jsonify({
            "msg": "Error al obtener las solicitudes de historietas",
            "detalle": str(e)
        }), 500
    
    
@app.route("/api_crear_comentario", methods=["POST"])
@jwt_required()
def obtener_crear_comentario():
    data = request.get_json(silent=True) or {}
    id_historieta = data.get("id_historieta")
    texto         = data.get("comentario", "").strip()
    email    = get_jwt_identity()   # tu JWT guarda el email

    # Validaciones básicas
    if not id_historieta or not texto:
        return jsonify({"msg": "id_historieta y comentario son obligatorios"}), 400

    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                # Recuperar id_lec a partir del email
                cursor.execute(
                    """
                    SELECT l.id_lec
                      FROM lector l
                      JOIN usuario u ON l.id_user = u.id_user
                     WHERE u.email = %s
                    """,
                    (email,)
                )
                fila = cursor.fetchone()
                if not fila:
                    return jsonify({"msg": "No eres un lector registrado"}), 403
                id_lec = fila[0] if isinstance(fila, (list, tuple)) else fila["id_lec"]
                # Insertar el comentario
                sql_insert = """
                    INSERT INTO comentario (id_historieta, id_lec, comentario)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(sql_insert, (id_historieta, id_lec, texto))
                nuevo_id = cursor.lastrowid
                conexion.commit()
        return jsonify({"id_comentario": nuevo_id}), 201
    except Exception as e:
        current_app.logger.exception("crear_comentario - error transacción")
        return jsonify({"msg": "Error interno al crear comentario"}), 500

@app.route("/api_obtener_comentarios/<int:id_historieta>", methods=["GET"])
@jwt_required()
def get_comentarios(id_historieta):
    try:
        comentarios = comentario_service.obtener_comentarios(id_historieta)
        if comentarios is not None:
            return jsonify({"comentarios": comentarios}), 200
        else:
            return jsonify({"msg": "No se encontraron comentarios"}), 404
    except Exception as e:
        current_app.logger.exception("Error al obtener comentarios")
        return jsonify({"msg": "Error interno al obtener comentarios"}), 500
    
    
@app.route("/api/users/items", methods=["GET"])
@jwt_required()
def api_get_items():
    # 1) Extraemos el email del JWT
    email = get_jwt_identity()

    # 2) Resolvemos el id_user
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute("SELECT id_user FROM usuario WHERE email = %s", (email,))
        fila = cur.fetchone()
    if not fila:
        return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
    id_user = fila["id_user"] if isinstance(fila, dict) else fila[0]

    # 3) Llamamos al servicio
    tipo = request.args.get('type', 'purchases')
    return usuario_service.get_items_usuario(id_user, tipo)

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
    

@app.route("/volumenes_mas_vendidos", methods=["GET"])
@jwt_required()
def api_volumenes_mas_vendidos_top_10():
    """
    Devuelve los 10 volúmenes más vendidos.
    """
    try:
        data = hist_srv.mas_vendidos(limit=10)
        return jsonify({"code": 0, "data": data}), 200
    except Exception:
        current_app.logger.exception("api_volumenes_mas_vendidos")
        return jsonify({"code": 1, "msg": "Error interno al obtener más vendidos"}), 500
    
@app.route("/api_guardar_venta", methods=["POST"])
@jwt_required()
def api_guardar_venta():
    data              = request.get_json(force=True)
    carrito           = data.get("carrito")
    payment_intent_id = data.get("payment_intent_id")

    # 1) Validaciones básicas
    if not carrito or not isinstance(carrito, list):
        return jsonify({"code": 1, "msg": "Carrito vacío o inválido"}), 400
    if not payment_intent_id:
        return jsonify({"code": 1, "msg": "Falta payment_intent_id"}), 400

    # 2) Verificar con Stripe que el pago se completó
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.error.StripeError as e:
        current_app.logger.exception("Error al consultar PaymentIntent")
        return jsonify({"code": 1, "msg": "Error al verificar pago"}), 500

    if intent.status != "succeeded":
        return jsonify({"code": 1, "msg": "Pago no confirmado"}), 400

    # 3) Resuelve id_user a partir del email del JWT
    email = get_jwt_identity()
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT id_user FROM usuario WHERE email = %s",
            (email,)
        )
        fila = cur.fetchone()

    if not fila:
        return jsonify({"code": 1, "msg": "Usuario no encontrado"}), 404

    id_user = fila["id_user"] if isinstance(fila, dict) else fila[0]

    # 4) Confirma y registra la venta
    try:
        id_ven = venta_service.confirmar_venta_from_intent(
            payment_intent_id,
            carrito,
            id_user
        )
        return jsonify({"code": 0, "id_venta": id_ven}), 201

    except ValueError as ve:
        # errores de lógica en el servicio (venta no encontrada, etc.)
        return jsonify({"code": 1, "msg": str(ve)}), 400

    except Exception:
        current_app.logger.exception("api_guardar_venta")
        return jsonify({"code": 1, "msg": "Error interno al guardar venta"}), 500



def _resolve_id_user_from_jwt():
    email = get_jwt_identity()
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute("SELECT id_user FROM usuario WHERE email = %s", (email,))
        fila = cur.fetchone()
    if not fila:
        return None
    return fila["id_user"] if isinstance(fila, dict) else fila[0]

@app.route("/api_agregar_wishlist", methods=["POST"])
@jwt_required()
def agregar_wishlist():
    id_user = _resolve_id_user_from_jwt()
    if id_user is None:
        return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

    data = request.get_json(force=True) or {}
    id_volumen = data.get("id_volumen")
    if not id_volumen:
        return jsonify({"success": False, "message": "Falta id_volumen"}), 400

    resp, status = lista_deseo_service.agregar_lista_deseo(id_user, int(id_volumen))
    return jsonify(resp), status


@app.route("/api_eliminar_wishlist/<int:id_volumen>", methods=["DELETE"])
@jwt_required()
def api_eliminar_wishlist(id_volumen):
    id_user = _resolve_id_user_from_jwt()
    if id_user is None:
        return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

    resp, status = lista_deseo_service.eliminar_lista_deseo(id_user, id_volumen)
    return jsonify(resp), status
    
    
@app.route("/payment-sheet", methods=["POST"])
@jwt_required()
def api_payment_sheet():
    data         = request.get_json(force=True)
    amount_cents = int(data.get("amount_cents", 0))

    if amount_cents <= 0:
        return jsonify({"msg": "amount_cents inválido"}), 400

    # 1) Resuelve id_user
    email = get_jwt_identity()
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute("SELECT id_user FROM usuario WHERE email = %s", (email,))
        fila = cur.fetchone()
    if not fila:
        return jsonify({"msg": "Usuario no encontrado"}), 404
    id_user = fila["id_user"] if isinstance(fila, dict) else fila[0]

    # 2) Inserta venta preliminar y obtén order_id
    try:
        order_id = venta_service.crear_pedido_preliminar(id_user, amount_cents)
    except Exception:
        current_app.logger.exception("crear_pedido_preliminar")
        return jsonify({"msg": "Error al crear pedido preliminar"}), 500

    # 3) Llama a stripe_service con la nueva firma
    try:
        payload = stripe_service.generar_payment_sheet(
            amount_cents,
            order_id,
            email
        )
        return jsonify(payload), 200

    except ValueError as e:
        return jsonify({"msg": str(e)}), 400

    except Exception:
        current_app.logger.exception("api_payment_sheet")
        return jsonify({"msg": "Error interno al crear payment sheet"}), 500
    
    
@app.route("/")
def home():
    valor = "Grupo 01"
    return f"<p>Bienvenido, {valor}</p>"




#! Iniciar el servidor
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)

@app.errorhandler(413)
def too_large(e):
    return {"msg": "El archivo es demasiado grande. Límite: 500 MB."}, 413