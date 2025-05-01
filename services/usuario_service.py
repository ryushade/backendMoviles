import db.database as db

def obtener_usuario(email):
    try:
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT id_user, email, pass FROM usuario WHERE email = %s", (email,))
                usuario = cursor.fetchone()
        return usuario
    except Exception as e:
        print("Error: ", e)
        return None
    
def obtener_usuario_id(id):
    try:
        conexion = db.obtener_conexion()
        usuario = None
        with db.obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT id_user, email, pass FROM usuario WHERE id_user = %s", (id,))
                usuario = cursor.fetchone()
        return usuario
    except Exception as e:
        return None
    
def registrar_usuario(email_user, pass_user):
    try:
        conexion = db.obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("INSERT INTO usuario (email, pass) VALUES (%s, %s)",
                            (email_user, pass_user))
            id_user = cursor.lastrowid
        conexion.commit()
        
        return id_user
    except Exception as e:
        print("Error: ", e)
        return None