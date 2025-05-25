from flask import jsonify, request
import services.admin_service as admin_service

def registrarAdministrador():
    try:
        # Verificar que se envía el id_user
        if "id_user" not in request.json:
            return jsonify({
                "success": False,
                "message": "Falta el campo id_user"
            }), 400

        id_user = request.json["id_user"]

        # Llama al servicio para actualizar el rol
        resultado = admin_service.agregar_administrador(id_user)

        if resultado["success"]:
            return jsonify({
                "success": True,
                "message": resultado["message"]
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": resultado["message"]
            }), 404

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al registrar administrador: {e}"
        }), 500