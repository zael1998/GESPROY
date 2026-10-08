from django.urls import path
from . import views

urlpatterns = [
    path("", views.lista_proyectos, name="lista_proyectos"),
    path("proyecto/<int:id>/", views.detalle_proyecto, name="detalle_proyecto"),
    path("proyecto/nuevo/", views.crear_proyecto, name = "crear_proyecto"),
    path("proyectos/solicitados/", views.proyectos_solicitados, name="proyectos_solicitados"),
    path("proyecto/en_definicion/", views.proyectos_en_definicion, name="proyectos_en_definicion"),
    path("proyecto/denegados/", views.proyectos_denegados, name="proyectos_denegados"),
    path("proyecto/en_negociacion/", views.proyectos_en_negociacion, name="proyectos_en_negociacion"),
    path("proyecto/en_proceso/", views.proyectos_en_proceso, name="proyectos_en_proceso"),
    path("proyecto/finalizados/", views.proyectos_finalizados, name="proyectos_finalizados")
]