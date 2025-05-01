import db.database as db

def obtener_lector_id(dni):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT dni_lec, nom_lec, apellidos_lec, fecha_nac, id_user FROM lector WHERE dni_lec = %s", (dni,))
                lector = cursor.fetchone()
        return lector
    except Exception as e:
        print("Error: ", e)
        return None

def registrar_lector(dni_lec, nom_lec, apellidos_lec, fecha_nac, id_user):
    try:
        conexion = db.obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("INSERT INTO lector (dni_lec, nom_lec, apellidos_lec, fecha_nac, id_user) VALUES (%s, %s, %s, %s, %s)",
                            (dni_lec, nom_lec, apellidos_lec, fecha_nac, id_user))
        conexion.commit()
    except Exception as e:
        print("Error: ", e)
        return None