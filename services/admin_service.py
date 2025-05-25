import db.database as db


def aprobar_proveedor(id_user, id_rol_proveedor=2):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "UPDATE usuario SET proveedor_aprobado = 1, id_rol = %s WHERE id_user = %s",
                    (id_rol_proveedor, id_user)
                )
            conexion.commit()
        return True
    except Exception as e:
        print("Error: ", e)
        return False
    

def agregar_administrador(id_user, id_rol=3):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id_user FROM usuario WHERE id_user = %s", (id_user,))
                if cursor.fetchone() is None:
                    return {"success": False, "message": "Usuario no encontrado."}
                cursor.execute(
                    "UPDATE usuario SET id_rol = %s WHERE id_user = %s",
                    (id_rol, id_user)
                )
            conexion.commit()
        return {"success": True, "message": "Usuario actualizado a administrador."}
    except Exception as e:
        print("Error: ", e)
        return {"success": False, "message": f"Error: {e}"}
