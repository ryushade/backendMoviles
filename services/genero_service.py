import db.database as db

def obtener_generos_por_tipo(tipo_material):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT id_genero, nombre_genero
                    FROM genero
                    WHERE tipo = %s OR tipo = 'ambos'
                """, (tipo_material,))
                generos = cursor.fetchall()
        return generos
    except Exception as e:
        print("Error al obtener géneros:", e)
        return None
