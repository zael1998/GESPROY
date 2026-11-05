"""Configuración principal de URLs de Gesproy."""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect


def inicio(request):
    if request.user.is_authenticated:
        return redirect("mis_proyectos")
    return redirect("login")


urlpatterns = [
    path("", inicio, name="inicio"),
    path("admin/", admin.site.urls),
    path("", include("proyectos.urls")),
    path("usuarios/", include("usuarios.urls")),
    path("horas/", include("horas.urls")),
    path("api/", include("api_movil.urls")),
    path("economia/", include("economia.urls")),
    path("publicaciones/", include("publicaciones.urls")),
]