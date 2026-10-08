from django.urls import path
from . import views

urlpatterns = [
    path("", views.lista_proyectos, name="lista_proyectos"),
    path("proyecto/<int:id>/", views.detalle_proyecto, name="detalle_proyecto"),
    path("proyecto/nuevo/", views.crear_proyecto, name = "crear_proyecto"),
    path("proyectos/solicitados/", views.proyectos_solicitados, name="proyectos_solicitados"),
]