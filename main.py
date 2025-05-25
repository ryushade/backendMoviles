from flask import Flask, request, jsonify
from flask_jwt_extended import jwt_required, JWTManager, create_access_token
import db.database as db
import controller.auth_controller as auth_controller
import controller.usuario_controller as usuario_controller
import controller.admin_controller as admin_controller
import stripe

app = Flask(__name__)
app.debug = True
app.config["JWT_SECRET_KEY"] = "secret"
jwt = JWTManager(app)

@app.route("/auth", methods=["POST"]) 
def auth():
    return auth_controller.auth()

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