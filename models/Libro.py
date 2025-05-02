class Libro(object):
    def __init__(self, isbn_lib=None, titulo_lib=None, anoPub_lib=None, estado_lib=None, clasificacion=None, id_edi=None, bookPDF=None, image=None, descripcion=None, calificacion_promedio=None, num_calificaciones=None, nombre_completo=None, precio_lib=None):
        self.isbn_lib = isbn_lib
        self.titulo_lib = titulo_lib
        self.anoPub_lib = anoPub_lib
        self.estado_lib = estado_lib
        self.clasificacion = clasificacion
        self.id_edi = id_edi
        self.bookPDF = bookPDF  # URL en formato de cadena
        self.image = image  # URL en formato de cadena
        self.descripcion = descripcion
        self.calificacion_promedio = calificacion_promedio
        self.num_calificaciones = num_calificaciones
        self.nombre_completo = nombre_completo  # Campo opcional para el nombre completo del autor
        self.precio_lib = precio_lib

    def json(self):
        # Solo incluye los atributos que no sean None en el diccionario
        return {k: v for k, v in self.__dict__.items() if v is not None}