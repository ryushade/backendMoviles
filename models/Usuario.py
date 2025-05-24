class Usuario(object):
    def __init__(self, id, email_user, pass_user, id_rol=None,
                 proveedor_solicitud=False, proveedor_aprobado=False, proveedor_fecha_solicitud=None):
        self.id = id
        self.email_user = email_user
        self.pass_user = pass_user
        self.id_rol = id_rol
        self.proveedor_solicitud = proveedor_solicitud
        self.proveedor_aprobado  = proveedor_aprobado
        self.proveedor_fecha_solicitud = proveedor_fecha_solicitud

    def __str__(self):
        return f"Usuario(id={self.id}, email_user='{self.email_user}')"

    def json(self):
        return {
            "id": self.id,
            "email_user": self.email_user,
            "pass_user": self.pass_user,
            "id_rol": self.id_rol,
            "proveedor_solictud": self.proveedor_solicitud,
            "proveedor_aceptado": self.proveedor_aprobado,
            "proveedor_fecha_solicitud": self.proveedor_fecha_solicitud
        }
