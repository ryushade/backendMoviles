import db.database as db

def publicar_comentario(id_historieta, id_lec, comentario):
 
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                sql = """
                    INSERT INTO comentario
                        (id_historieta, id_lec, comentario)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(
                    sql,
                    (id_historieta, id_lec, comentario)
                )
            conexion.commit()
            return cursor.lastrowid
    except Exception as e:
        print("Error al publicar comentario:", e)
        return None

def obtener_comentarios(id_historieta):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                sql = """
                    SELECT id, id_historieta, id_lec, comentario, fecha
                    FROM comentario
                    WHERE id_historieta = %s
                """
                cursor.execute(sql, (id_historieta,))
                return cursor.fetchall()
    except Exception as e:
        print("Error al obtener comentarios:", e)
        return None
    