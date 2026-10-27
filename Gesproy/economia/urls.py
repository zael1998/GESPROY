
from django.urls import path

from . import views


app_name = "economia"


urlpatterns = [

    # ======================================
    # ESTUDIOS ECONÓMICOS
    # ======================================

    path(
        "proyecto/<int:proyecto_id>/",
        views.estudio_proyecto,
        name="estudio",
    ),

    path(
        "proyecto/<int:proyecto_id>/crear/",
        views.crear_estudio,
        name="crear_estudio",
    ),

    # ======================================
    # PARTIDAS ECONÓMICAS
    # ======================================

    path(
        "proyecto/<int:proyecto_id>/<int:estudio_id>/partidas/nueva/",
        views.formulario_partida,
        name="nueva_partida",
    ),

    path(
        "proyecto/<int:proyecto_id>/<int:estudio_id>/partidas/<int:partida_id>/editar/",
        views.formulario_partida,
        name="editar_partida",
    ),

    path(
        "proyecto/<int:proyecto_id>/<int:estudio_id>/partidas/<int:partida_id>/eliminar/",
        views.eliminar_partida,
        name="eliminar_partida",
    ),

    # ======================================
    # CERRAR ESTUDIO
    # ======================================

    path(
        "proyecto/<int:proyecto_id>/<int:estudio_id>/cerrar/",
        views.cerrar_estudio,
        name="cerrar_estudio",
    ),

    # ======================================
    # ADMINISTRACIÓN DE CATEGORÍAS
    # ======================================

    path(
        "administracion/categorias/",
        views.gestionar_categorias,
        name="gestionar_categorias",
    ),

    path(
        "administracion/categorias/nueva/",
        views.crear_categoria,
        name="crear_categoria",
    ),

    path(
        "administracion/categorias/<int:categoria_id>/editar/",
        views.editar_categoria,
        name="editar_categoria",
    ),

    path(
        "administracion/categorias/<int:categoria_id>/eliminar/",
        views.eliminar_categoria,
        name="eliminar_categoria",
    ),
    # ======================================
# COMPARATIVA ECONÓMICA
# ======================================

path(
    "proyecto/<int:proyecto_id>/comparativa/",
    views.comparativa_estudios,
    name="comparativa",
),

]
