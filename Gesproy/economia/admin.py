
from django.contrib import admin

from .models import (
    CategoriaEconomica,
    EstudioEconomico,
    PartidaEconomica,
)


@admin.register(CategoriaEconomica)
class CategoriaEconomicaAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "nombre",
        "tipo",
        "padre",
        "orden",
    )

    list_filter = ("tipo",)

    search_fields = (
        "codigo",
        "nombre",
    )


@admin.register(EstudioEconomico)
class EstudioEconomicoAdmin(admin.ModelAdmin):

    list_display = (
        "proyecto",
        "fase",
        "version",
        "estado",
        "responsable",
        "fecha",
    )

    list_filter = (
        "fase",
        "estado",
    )

    search_fields = (
        "proyecto__acronimo",
        "proyecto__nombre",
    )


@admin.register(PartidaEconomica)
class PartidaEconomicaAdmin(admin.ModelAdmin):

    list_display = (
        "concepto",
        "estudio",
        "categoria",
        "importe",
    )

    search_fields = ("concepto",)
