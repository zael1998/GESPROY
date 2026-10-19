
from django.urls import path
from .calendario import mis_horas

from . import views


app_name = "horas"

urlpatterns = [

    # Listado de tareas de un proyecto
    path("proyecto/<int:proyecto_id>/tareas/", views.tareas_proyecto, name="tareas_proyecto"
    ),

    # Crear nueva tarea
    path("proyecto/<int:proyecto_id>/tareas/nueva/",views.crear_tarea,name="crear_tarea"
    ),

    # Editar tarea
    path("proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/editar/",views.editar_tarea,name="editar_tarea"
    ),

    # Finalizar tarea
    path( "proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/finalizar/", views.finalizar_tarea, name="finalizar_tarea"
    ),

    # Reabrir tarea
    path("proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/reabrir/",views.reabrir_tarea, name="reabrir_tarea"),

    # Eliminar tarea
    path("proyecto/<int:proyecto_id>/tareas/<int:tarea_id>/eliminar/",views.eliminar_tarea,name="eliminar_tarea"),
    
    
    path("mis-horas/",mis_horas,name="mis_horas"),
]
