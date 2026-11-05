import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.db import models

EXTENSIONES = ["pdf", "doc", "docx", "odt", "rtf", "txt", "csv", "xls", "xlsx", "ods", "ppt", "pptx", "odp", "png", "jpg", "jpeg", "gif", "tif", "tiff", "zip"]
TAMANO_MAXIMO = 25 * 1024 * 1024


def ruta_publicacion(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"publicaciones/{uuid.uuid4().hex}{extension}"


def validar_tamano(archivo):
    if archivo and archivo.size > TAMANO_MAXIMO:
        raise ValidationError("El archivo no puede superar los 25 MB.")


class Publicacion(models.Model):
    CONFIDENCIAL = "CONFIDENCIAL"
    RESTRINGIDO = "RESTRINGIDO"
    PUBLICO = "PUBLICO"
    DIFUSION = [(CONFIDENCIAL, "Confidencial"), (RESTRINGIDO, "Restringido"), (PUBLICO, "Público")]

    titulo = models.CharField(max_length=300)
    autores = models.TextField(help_text="Autores tal como aparecen en la publicación")
    referencia = models.TextField(blank=True, help_text="Revista, congreso, editorial o DOI")
    anio = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1900), MaxValueValidator(2100)])
    proyectos = models.ManyToManyField("proyectos.Proyecto", related_name="publicaciones")
    difusion = models.CharField(max_length=15, choices=DIFUSION, default=RESTRINGIDO)
    archivo = models.FileField(upload_to=ruta_publicacion, validators=[FileExtensionValidator(EXTENSIONES), validar_tamano])
    nombre_archivo = models.CharField(max_length=255, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="publicaciones_creadas")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-anio", "titulo", "pk"]
        verbose_name = "Publicación"
        verbose_name_plural = "Publicaciones"

    def __str__(self):
        return self.titulo