from django.urls import path

from . import views


urlpatterns = [

    # Autenticación
    path(
        "csrf/",
        views.obtener_csrf,
        name="api_csrf",
    ),

    path(
        "login/",
        views.iniciar_sesion,
        name="api_login",
    ),

    path(
        "logout/",
        views.cerrar_sesion,
        name="api_logout",
    ),

    path(
        "usuario/",
        views.usuario_actual,
        name="api_usuario_actual",
    ),

    # Proyectos
    path(
        "mis-proyectos/",
        views.mis_proyectos,
        name="api_mis_proyectos",
    ),

    path(
        "proyectos/<int:id>/",
        views.detalle_proyecto,
        name="api_detalle_proyecto",
    ),

]