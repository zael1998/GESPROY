from django.urls import path

from . import views
from . import horas_views
from . import editar_horas_views


urlpatterns = [

    # ======================================
    # AUTENTICACIÓN
    # ======================================

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

    # ======================================
    # PROYECTOS
    # ======================================

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

    # ======================================
    # TAREAS
    # ======================================

    path(
        "proyectos/<int:proyecto_id>/tareas/",
        horas_views.tareas_proyecto,
        name="api_tareas_proyecto",
    ),

    # ======================================
    # HORAS
    # ======================================

    path(
        "horas/",
        horas_views.mis_horas,
        name="api_mis_horas",
    ),

    path(
        "horas/registrar/",
        horas_views.registrar_horas,
        name="api_registrar_horas",
    ),

    # ======================================
    # EDICIÓN Y ELIMINACIÓN
    # ======================================

    path(
        "horas/<int:registro_id>/",
        editar_horas_views.gestionar_registro,
        name="api_gestionar_registro",
    ),

]