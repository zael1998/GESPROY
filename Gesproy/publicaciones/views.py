from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PublicacionForm
from .models import Publicacion
from .permisos import puede_descargar, puede_editar, proyectos_permitidos


@login_required
def lista_publicaciones(request):
    publicaciones = Publicacion.objects.prefetch_related("proyectos").all()
    titulo = request.GET.get("titulo", "").strip()[:200]
    autores = request.GET.get("autores", "").strip()[:200]
    anio = request.GET.get("anio", "").strip()
    if titulo:
        publicaciones = publicaciones.filter(titulo__icontains=titulo)
    if autores:
        publicaciones = publicaciones.filter(autores__icontains=autores)
    if anio:
        if anio.isdigit() and len(anio) == 4:
            publicaciones = publicaciones.filter(anio=int(anio))
        else:
            publicaciones = publicaciones.none()
    publicaciones = publicaciones[:200]
    permitidos = set(proyectos_permitidos(request.user).values_list("pk", flat=True))
    filas = []
    for publicacion in publicaciones:
        proyecto_ids = {p.pk for p in publicacion.proyectos.all()}
        filas.append({
            "obj": publicacion,
            "descargable": publicacion.difusion != Publicacion.CONFIDENCIAL or request.user.is_staff or request.user.is_superuser or bool(proyecto_ids & permitidos),
            "editable": puede_editar(request.user, publicacion),
        })
    return render(request, "publicaciones/lista.html", {"filas": filas, "titulo": titulo, "autores": autores, "anio": anio, "puede_crear": proyectos_permitidos(request.user).exists()})


@login_required
def crear_publicacion(request):
    if not request.user.is_active or not proyectos_permitidos(request.user).exists():
        raise PermissionDenied("No tienes proyectos autorizados para registrar publicaciones.")
    formulario = PublicacionForm(request.POST or None, request.FILES or None, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            publicacion = formulario.save(commit=False)
            publicacion.creado_por = request.user
            publicacion.nombre_archivo = request.FILES["archivo"].name[:255]
            publicacion.save()
            formulario.save_m2m()
        messages.success(request, "Publicación registrada.")
        return redirect("publicaciones:lista")
    return render(request, "publicaciones/formulario.html", {"formulario": formulario, "titulo_pagina": "Nueva publicación"})


@login_required
def editar_publicacion(request, pk):
    publicacion = get_object_or_404(Publicacion, pk=pk)
    if not puede_editar(request.user, publicacion):
        raise PermissionDenied("No tienes permiso para editar esta publicación.")
    archivo_anterior = publicacion.archivo.name
    almacenamiento = publicacion.archivo.storage
    formulario = PublicacionForm(request.POST or None, request.FILES or None, instance=publicacion, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        nuevo_archivo = request.FILES.get("archivo")
        with transaction.atomic():
            obj = formulario.save(commit=False)
            if nuevo_archivo:
                obj.nombre_archivo = nuevo_archivo.name[:255]
            obj.save()
            formulario.save_m2m()
        if nuevo_archivo and archivo_anterior and archivo_anterior != obj.archivo.name:
            almacenamiento.delete(archivo_anterior)
        messages.success(request, "Publicación actualizada.")
        return redirect("publicaciones:lista")
    return render(request, "publicaciones/formulario.html", {"formulario": formulario, "titulo_pagina": "Editar publicación", "publicacion": publicacion})


@login_required
@require_POST
def eliminar_publicacion(request, pk):
    publicacion = get_object_or_404(Publicacion, pk=pk)
    if not puede_editar(request.user, publicacion):
        raise PermissionDenied("No tienes permiso para eliminar esta publicación.")
    nombre = publicacion.archivo.name
    almacenamiento = publicacion.archivo.storage
    publicacion.delete()
    if nombre:
        almacenamiento.delete(nombre)
    messages.success(request, "Publicación eliminada.")
    return redirect("publicaciones:lista")


@login_required
def descargar_publicacion(request, pk):
    publicacion = get_object_or_404(Publicacion.objects.prefetch_related("proyectos"), pk=pk)
    if not puede_descargar(request.user, publicacion):
        raise PermissionDenied("No tienes permiso para descargar este archivo.")
    if not publicacion.archivo:
        raise Http404("El documento no está disponible.")
    try:
        archivo = publicacion.archivo.open("rb")
    except (OSError, FileNotFoundError):
        raise Http404("El documento no está disponible.")
    nombre = publicacion.nombre_archivo or Path(publicacion.archivo.name).name
    return FileResponse(archivo, as_attachment=True, filename=nombre)