import os
import pymysql
import socket

def obtener_conexion():
    entorno = 'local' if socket.gethostname() == 'localhost' or 'local' in socket.gethostname() else 'pythonanywhere'

    if entorno == 'local':
        return pymysql.connect(
            host='localhost',
            user='root',
            password='12345678',
            db='db_mangaka',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    else:
        return pymysql.connect(
            host='grupo1damb.mysql.pythonanywhere-services.com',
            user='grupo1damb',
            password=os.getenv('DB_PASSWORD'),  
            db='grupo1damb$db_mangakomi',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
