from django.shortcuts import render
from .models import Proyecto
from .forms import ProyectoForm

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
        