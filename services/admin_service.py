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
