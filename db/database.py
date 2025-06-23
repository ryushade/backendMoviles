import os
import pymysql

def obtener_conexion():
    # Si DB_PASSWORD está definida (en tu WSGI) asumimos que es PythonAnywhere
    if os.getenv('DB_PASSWORD'):
        pa_user = os.getenv('USER')  # en PA es tu usuario Linux, ej. "grupo1damb"
        return pymysql.connect(
            host=f"{pa_user}.mysql.pythonanywhere-services.com",
            user=pa_user,
            password=os.getenv('DB_PASSWORD'),
            db=f"{pa_user}$db_mangakomi",   # confirma en Databases que es exactamente este nombre
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    # En local, sigue usando tu MySQL local
    return pymysql.connect(
        host='localhost',
        user='root',
        password='12345678',
        db='db_mangaka',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
