from django.contrib import admin
from .models import Publicacion


@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "anio", "difusion", "creado_en")
    list_filter = ("difusion", "anio")
    search_fields = ("titulo", "autores", "referencia")
    filter_horizontal = ("proyectos",)