import db.database as db


def aprobar_proveedor(id_user, id_rol_proveedor=2):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT email FROM usuario WHERE id_user = %s", (id_user,))
                resultado = cursor.fetchone()

                if not resultado:
                    return False  

                email = resultado.get("email")

                cursor.execute(
                    "UPDATE usuario SET proveedor_aprobado = 1, id_rol = %s WHERE id_user = %s",
                    (id_rol_proveedor, id_user)
                )

                cursor.execute(
                    "INSERT INTO proveedor (id_user, id_rol, email_empresa) VALUES (%s, %s, %s)",
                    (id_user, id_rol_proveedor, email)
                )

            conexion.commit()
        return True
    except Exception as e:
        print("Error al aprobar proveedor:", e)
        return False

    

def obtener_proveedor_por_id(id_user):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id_proveedor, nombre_empresa
                    FROM proveedor
                    WHERE id_user = %s
                    """,
                    (id_user,)
                )
                proveedor = cursor.fetchone()
        if proveedor:
            return {
                "id_proveedor": proveedor.get("id_proveedor"),
                "nombre_empresa": proveedor.get("nombre_empresa")
            }
        return None
    except Exception as e:
        print("Error al obtener proveedor:", e)
        return None

def obtener_solicitudes_proveedor():
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        u.id_user, 
                        u.email, 
                        CONCAT(l.nom_lec, ' ', l.apellidos_lec) AS nombre_completo, 
                        u.proveedor_fecha_solicitud
                    FROM usuario u
                    INNER JOIN lector l ON u.id_user = l.id_user
                    WHERE u.proveedor_solicitud = 1 AND u.proveedor_aprobado = 0
                    """
                )
                resultados = cursor.fetchall()

        if resultados:
            return [
                {
                    "id_user": fila["id_user"],
                    "email": fila["email"],
                    "nombre": fila["nombre_completo"],
                    "fecha_solicitud": fila["proveedor_fecha_solicitud"]
                }
                for fila in resultados
            ]
        return []
    except Exception as e:
        print("Error al obtener solicitudes de proveedor:", e)
        return []


    

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
