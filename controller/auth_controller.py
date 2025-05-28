import bcrypt
from flask import jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity
import services.usuario_service as usuario_service
from models.Usuario import Usuario

def auth():
    email = request.json.get("email", None)
    password = request.json.get("password", None)

    if not email or not password:
        return jsonify({"msg": "Email y contraseña son requeridos"}), 400

    try:
        usuario = usuario_service.obtener_usuario(email)
        print("usuario:", usuario)

        if usuario:
            email_almacenado = usuario['email']
            hash_almacenado = usuario['contrasena']
            id_rol = usuario['id_rol']

            if not hash_almacenado:
                print(f"Usuario encontrado pero no tiene el hash de contraseña: {email}")
                return jsonify({"msg": "Error en configuración de cuenta. Contacte al administrador"}), 500

            if email == email_almacenado and bcrypt.checkpw(password.encode('utf-8'), hash_almacenado.encode('utf-8')):
                user = Usuario(usuario['id'], email_almacenado, password)
                access_token = create_access_token(identity=user.email_user)
                return jsonify(
                    access_token=access_token,
                    id_rol=id_rol
                ), 200
            else:
                return jsonify({"msg": "Credenciales incorrectas"}), 401
        else:
            return jsonify({"msg": "Usuario no encontrado"}), 404

    except Exception as e:
        print("Error en autenticación:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"msg": "Error durante autenticación"}), 500


def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200