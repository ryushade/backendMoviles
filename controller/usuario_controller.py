import bcrypt
from flask import jsonify, request
import services.usuario_service as usuario_service
import services.lector_service as lector_service
from models.Usuario import Usuario
from models.Lector import Lector
from datetime import datetime

def registrarUsuario():
    response = {"data": []}
    try:
        # Verificar si llegan correctamente desde el frontend
        if not ("id_rol" in request.json and "proveedor_solicitud" in request.json):
            return jsonify({
                "code": 1,
                "msg": "El frontend no está enviando id_rol o proveedor_solicitud",
                "json_recibido": request.json
            }), 400


        # Campos para la tabla usuario
        email_user      = request.json["email_user"]
        pass_user       = request.json["pass_user"]
        proveedor_solicitud = request.json.get("proveedor_solicitud", False)
        id_rol          = int(request.json.get("id_rol", 1))

        # Campos para la tabla lector
        dni_lec         = request.json["dni_lec"]
        nom_lec         = request.json["nom_lec"]
        apellidos_lec   = request.json["apellidos_lec"]
        fecha_nac       = request.json["fecha_nac"]

        proveedor_fecha_solicitud = (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S") if proveedor_solicitud else None
        )

        # Hash de la contraseña en texto
        hashed_pass_user = (
            bcrypt.hashpw(pass_user.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        )

        # Inserción en tabla usuario
        id_user = usuario_service.registrar_usuario(
            email_user,
            hashed_pass_user,
            proveedor_solicitud=proveedor_solicitud,
            proveedor_fecha_solicitud=proveedor_fecha_solicitud,
            id_rol=id_rol,
        )

        # Inserción en tabla lector
        lector_service.registrar_lector(
            dni_lec, nom_lec, apellidos_lec, fecha_nac, id_user
        )

        response["code"] = 0
        response["msg"] = "Usuario registrado correctamente"
        return jsonify(response), 200

    except Exception as e:
        response["code"] = 1
        response["msg"]  = f"Error al registrar usuario: {e}"
        return jsonify(response), 500
