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
        # Verificar que se envía el id_user
        if "id_user" not in request.json:
            return jsonify({
                "success": False,
                "message": "Falta el campo id_user"
            }), 400

        id_user = request.json["id_user"]
        id_rol_proveedor = request.json.get("id_rol_proveedor", 2)  # Valor por defecto: 2

        # Llama al servicio para aprobar el proveedor
        resultado = admin_service.aprobar_proveedor(id_user, id_rol_proveedor)

        if resultado:
            return jsonify({
                "success": True,
                "message": "Proveedor aprobado correctamente"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Error al aprobar proveedor: Usuario no encontrado"
            }), 404

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al aprobar proveedor: {e}"
        }), 500

def get_solicitudes_proveedor():
    try:
        solicitudes = admin_service.obtener_solicitudes_proveedor()
        if solicitudes:
            return {
                "success": True,
                "data": solicitudes
            }, 200
        else:
            return {
                "success": True,
                "data": [],
                "message": "No hay solicitudes de proveedor pendientes"
            }, 200  
    except Exception as e:
        return {
            "success": False,
            "message": "Error al obtener solicitudes de proveedor",
            "error": str(e)
        }, 500

