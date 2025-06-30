from flask import jsonify, request, current_app
from flask_jwt_extended import get_jwt_identity
from pymysql.cursors import DictCursor

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
    # 1) Cargo y valido el JSON
    data = request.json or {}
    id_objetivo      = data.get("id_user")
    id_rol_proveedor = data.get("id_rol_proveedor", 2)
    if not id_objetivo:
        return jsonify({"success": False, "message": "Falta el campo id_user"}), 400

    try:
        with db.obtener_conexion() as cn, cn.cursor(DictCursor) as cur:
            # 2) Obtengo el id del admin desde el JWT
            email_admin = get_jwt_identity()
            cur.execute("SELECT id_user FROM usuario WHERE email = %s", (email_admin,))
            fila = cur.fetchone()
            if not fila:
                return jsonify({"success": False, "message": "Admin no encontrado"}), 404
            id_admin = fila["id_user"] if isinstance(fila, dict) else fila[0]

            # 3) Actualizo el usuario objetivo marcándolo como proveedor y registro auditoría
            cur.execute("""
                UPDATE usuario
                   SET id_rol                  = %s,
                       proveedor_aprobado      = 1,
                       fecha_modificacion      = NOW(),
                       id_usuario_modificacion = %s
                 WHERE id_user = %s
            """, (id_rol_proveedor, id_admin, id_objetivo))
            cn.commit()

            if cur.rowcount == 0:
                return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

        # 4) Éxito
        return jsonify({"success": True, "message": "Proveedor aprobado correctamente"}), 200

    except Exception as e:
        current_app.logger.exception("Error en aprobar_proveedor")
        return jsonify({"success": False, "message": f"Error interno: {e}"}), 500

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

