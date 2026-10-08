from django.shortcuts import render
from .models import Proyecto
from .forms import ProyectoForm
from django.utils import timezone
from django.db.models import Sum
from horas.models import Tarea, RegistroHoras

def lista_proyectos(request):
    
    #dame todo los objetos proyecto que existen en la base de datos
    proyectos = Proyecto.objects.all()
    #con {"proyectos": proyectos} se le pasan los datos al template
    return render(request, 'proyectos/lista_proyectos.html', {"proyectos": proyectos})

def proyectos_solicitados(request):
    proyectos = Proyecto.objects.filter(estado = "SOLICITADO")
    
    return render(
        request,
        "proyectos/proyectos_solicitados.html",
        {"proyectos": proyectos }
    )
    
def proyectos_en_negociacion(request):
    proyectos = Proyecto.objects.filter(estado = "NEGOCIACION")
    
    return render(
        request,
        "proyectos/proyectos_en_negociacion.html",
        {"proyectos": proyectos }
    )
    

def proyectos_en_proceso(request):

    proyectos = Proyecto.objects.filter(estado="PROCESO")
    hoy = timezone.localdate()

    for proyecto in proyectos:

        # PRIMERA BARRA: TIEMPO TRANSCURRIDO

        proyecto.porcentaje_tiempo = 0

        if proyecto.fecha_inicio and proyecto.fecha_fin:

            duracion_total = (proyecto.fecha_fin - proyecto.fecha_inicio).days
            tiempo_transcurrido = (hoy - proyecto.fecha_inicio).days

            if duracion_total > 0:
                porcentaje = (tiempo_transcurrido / duracion_total) * 100
                proyecto.porcentaje_tiempo = max(0, min(100, porcentaje))

        # SEGUNDA BARRA: HORAS TRABAJADAS

        tareas = Tarea.objects.filter(proyecto=proyecto)

        horas_previstas = tareas.aggregate(
            total=Sum("horas_estimadas")
        )["total"] or 0

        horas_realizadas = RegistroHoras.objects.filter(
            tarea__proyecto=proyecto
        ).aggregate(
            total=Sum("horas")
        )["total"] or 0

        proyecto.porcentaje_trabajo = None

        if horas_previstas > 0:
            porcentaje = (horas_realizadas / horas_previstas) * 100
            proyecto.porcentaje_trabajo = min(100, porcentaje)

    return render(
        request,
        "proyectos/proyectos_en_proceso.html",
        {"proyectos": proyectos}
    )
    
def proyectos_finalizados(request):
    proyectos = Proyecto.objects.filter(estado = "FINALIZADO")
    
    return render(
        request,
        "proyectos/proyectos_finalizados.html",
        {"proyectos": proyectos }
    )

    
def proyectos_denegados(request):
    proyectos = Proyecto.objects.filter(estado = "DENEGADO")
    
    return render(
        request,
        "proyectos/proyectos_denegados.html",
        {"proyectos": proyectos }
    )

def proyectos_en_definicion(request):
    proyectos = Proyecto.objects.filter(estado = "DEFINICION")
    
    return render(
        request,
        "proyectos/proyectos_en_definicion.html",
        {"proyectos": proyectos }
    )

    #Este es para obtener cada proyecto individualmente
def detalle_proyecto(request, id):
        proyecto = Proyecto.objects.get(id=id)  
        return render(request, 'proyectos/detalle_proyecto.html', {"proyecto": proyecto})
    
def crear_proyecto(request):
    if request.method == "POST":
        formulario = ProyectoForm(request.POST)
        
        if formulario.is_valid():
            formulario.save()
            
    else:
        formulario = ProyectoForm()
        
    return render(
        request,
        "proyectos/crear_proyecto.html",
        {"formulario": formulario }
    )
        