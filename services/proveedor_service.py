import db.database as db

def solicitar_proveedor(email):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE usuario
                    SET proveedor_solicitud = 1, proveedor_fecha_solicitud = NOW()
                    WHERE email = %s
                    """, (email.strip(),))
                    
                conexion.commit()

                if cursor.rowcount == 0:
                    return {"code": 1, "msg": "Usuario no encontrado"}, 404

                return {"code": 0, "msg": "Solicitud de proveedor registrada correctamente."}, 200

    except Exception as e:
        print("Error:", e)
        return {"code": 1, "msg": "Error interno del servidor"}, 500


