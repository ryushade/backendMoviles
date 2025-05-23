import bcrypt
from flask import jsonify, request
import services.usuario_service as usuario_service
import services.lector_service as lector_service
from models.Usuario import Usuario
from models.Lector import Lector
from datetime import datetime

def registrarUsuario():
    response = dict()
    datos = []
    response["data"] = datos
    try:
        # Body del request
        email_user = request.json["email_user"]
        pass_user = request.json["pass_user"]
        dni_lec = request.json["dni_lec"]
        nom_lec = request.json["nom_lec"]
        apellidos_lec = request.json["apellidos_lec"]
        fecha_nac = request.json["fecha_nac"]

        # Nuevo: revisar si viene proveedor_solicitud (opcional, por defecto False)
        proveedor_solicitud = request.json.get("proveedor_solicitud", False)
        proveedor_fecha_solicitud = None
        if proveedor_solicitud:
            proveedor_fecha_solicitud = datetime.now()

        # Rol por defecto
        id_rol = 1  # usuario normal (ajusta según tus IDs de roles)

        # Codificar la contraseña usando bcrypt
        salt = bcrypt.gensalt()
        hashed_pass_user = bcrypt.hashpw(pass_user.encode('utf-8'), salt)

        # Registrar el usuario con los nuevos parámetros
        id_user = usuario_service.registrar_usuario(
            email_user, hashed_pass_user,
            proveedor_solicitud=proveedor_solicitud,
            proveedor_fecha_solicitud=proveedor_fecha_solicitud,
            id_rol=id_rol
        )

        lector_service.registrar_lector(
            dni_lec, nom_lec, apellidos_lec, fecha_nac, id_user
        )

        response["code"] = 0
        response["msg"] = "Usuario registrado correctamente"
        return jsonify(response), 200

    except Exception as e:
        response["code"] = 1
        response["msg"] = f"Error al registrar usuario: {str(e)}"
        return jsonify(response), 500
