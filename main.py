from flask import Flask, request, jsonify
from flask_jwt_extended import jwt_required, JWTManager, create_access_token
import db.database as db
import controller.auth_controller as auth_controller
import controller.usuario_controller as usuario_controller
import controller.admin_controller as admin_controller
import stripe
import git
import os
import hmac
import hashlib

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

@app.route("/api_registrar_administrador", methods=["POST"])
def registrar_administrador():
    return admin_controller.registrarAdministrador()



@app.route("/api_obtener_usuario_data")
@jwt_required()
def obtener_usuario_data():
    return usuario_controller.obtener_usuario_data()


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