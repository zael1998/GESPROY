
"""
Configuración principal de URLs de Gesproy.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect


# ==========================================
# PÁGINA DE INICIO
# ==========================================

def inicio(request):

    # Usuario con sesión iniciada
    if request.user.is_authenticated:
        return redirect("mis_proyectos")

    # Usuario sin sesión
    return redirect("login")


# ==========================================
# RUTAS PRINCIPALES
# ==========================================

urlpatterns = [

    # INICIO DE GESPROY
    path("", inicio, name="inicio"),

    # ADMINISTRACIÓN DE DJANGO
    path("admin/", admin.site.urls),

    # PROYECTOS DE GESPROY
    path("", include("proyectos.urls")),

    # USUARIOS Y AUTENTICACIÓN
    path("usuarios/", include("usuarios.urls")),
]
