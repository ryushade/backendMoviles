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
                    SELECT 
                      CONCAT(l.nom_lec, ' ', l.apellidos_lec) AS nombre_completo, 
                      h.id_historieta,
                      c.comentario, 
                      c.fecha_comentario
                    FROM lector l
                    INNER JOIN comentario c ON l.id_lec = c.id_lec
                    INNER JOIN historieta h ON h.id_historieta = c.id_historieta
                    WHERE h.id_historieta = %s
                """
                cursor.execute(sql, (id_historieta,))
                rows = cursor.fetchall()
                comentarios = []
                for row in rows:
                    if isinstance(row, dict):
                        comentarios.append({
                            "usuario": row.get("nombre_completo"),
                            "texto": row.get("comentario"),
                            "fecha": row.get("fecha_comentario")
                        })
                    else:
                        comentarios.append({
                            "usuario": row[0],
                            "texto": row[2],
                            "fecha": row[3]
                        })
                return comentarios
    except Exception as e:
        print("Error al obtener comentarios:", e)
        return None
