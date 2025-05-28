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
    
def aprobar_proveedor():
    try:
        if "id_user" not in request.json or "nombre_empresa" not in request.json:
            return jsonify({
                "success": False,
                "message": "Faltan campos obligatorios: id_user y nombre_empresa"
            }), 400

        id_user = request.json["id_user"]
        nombre_empresa = request.json["nombre_empresa"]
        id_rol_proveedor = request.json.get("id_rol_proveedor", 2) 

        resultado = admin_service.aprobar_proveedor(id_user, nombre_empresa, id_rol_proveedor)

        if resultado:
            return jsonify({
                "success": True,
                "message": "Proveedor aprobado correctamente"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Error al aprobar proveedor"
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al aprobar proveedor: {e}"
        }), 500