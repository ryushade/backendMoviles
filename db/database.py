import pymysql

def obtener_conexion():
    return pymysql.connect(host='localhost',
                                user='root',
                                password='12345678',
                                db='db_mangaka')