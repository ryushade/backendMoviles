class Lector(object):
    def __init__(self, dni_lec, nom_lec, apellidos_lec, fecha_nac, user_id):
        self.dni_lec = dni_lec
        self.nom_lec = nom_lec
        self.apellidos_lec = apellidos_lec
        self.fecha_nac = fecha_nac
        self.user_id = user_id

    def __str__(self):
        return "Lector(dni='%s')" % self.dni_lec
    
    def json(self):
        return {
            "dni_lec": self.dni_lec,
            "nom_lec": self.nom_lec,
            "apellidos_lec": self.apellidos_lec,
            "fecha_nac": self.fecha_nac,
            "user_id": self.user_id
        }