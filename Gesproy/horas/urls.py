from django.urls import path
from . import views, validacion_informes, registros

app_name = "horas"

urlpatterns = [
    path(
        "proyecto/<int:proyecto_id>/tareas/",
        views.tareas_proyecto,
        name="tareas_proyecto",
    ),
    # Nueva vista de Gantt, solo consulta.
    path(
        "proyecto/<int:proyecto_id>/tareas/gantt/",
        views.gantt_proyecto,
        name="gantt_proyecto",
    ),
    path(
        "proyecto/<int:proyecto_id>/tareas/nueva/",
        views.crear_tarea,
        name="crear_tarea",
    ),
    # Historial de comentarios de cada tarea y subtarea.
    path(
        "proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/comentarios/",
        views.comentarios_tarea,
        name="comentarios_tarea",
    ),
    path(
        "proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/editar/",
        views.editar_tarea,
        name="editar_tarea",
    ),
    path(
        "proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/finalizar/",
        views.finalizar_tarea,
        name="finalizar_tarea",
    ),
    path(
        "proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/reabrir/",
        views.reabrir_tarea,
        name="reabrir_tarea",
    ),
    path(
        "proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/eliminar/",
        views.eliminar_tarea,
        name="eliminar_tarea",
    ),
    # Correcciones de registros del propio investigador.
    path(
        "mis-horas/registro/<int:registro_id>/editar/",
        registros.editar_registro,
        name="editar_registro",
    ),
    path(
        "mis-horas/registro/<int:registro_id>/eliminar/",
        registros.eliminar_registro,
        name="eliminar_registro",
    ),
    path("mis-horas/", validacion_informes.mis_horas_seguro, name="mis_horas"),
    path("", validacion_informes.inicio_horas, name="inicio_horas"),
    path("validar/", validacion_informes.validar_horas, name="validar_horas"),
    path("validar/accion/", validacion_informes.accion_validar, name="accion_validar"),
    path("informe/", validacion_informes.informe_horas, name="informe_horas"),

    # ==========================================
# EDITAR COMENTARIO
# ==========================================

path(
    "proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/comentarios/<int:comentario_id>/editar/",
    views.editar_comentario_tarea,
    name="editar_comentario_tarea",
),

# ==========================================
# ELIMINAR COMENTARIO
# ==========================================

path(
    "proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/comentarios/<int:comentario_id>/eliminar/",
    views.eliminar_comentario_tarea,
    name="eliminar_comentario_tarea",
),
]