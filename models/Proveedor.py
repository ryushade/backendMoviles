class Usuario(object):
    def __init__(self,  user_id , nombre_empresa, descripcion):
        self.user_id = user_id
        self.nombre_empresa = nombre_empresa
        self.descripcion = descripcion


    def __str__(self):
        return "User(id='%s')" % self.user_id
    
    def json(self):
        return {
            "user_id": self.user_id,
            "nombre_empresa": self.nombre_empresa,
            "descripcion": self.descripcion
        }