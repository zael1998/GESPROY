
from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from proyectos.models import Proyecto
from usuarios.models import Investigador

from .forms import TareaForm
from .models import RegistroHoras, Tarea


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def obtener_proyecto_tareas(proyecto_id):
    """
    Las tareas se gestionan en proyectos en proceso.
    Los finalizados se pueden consultar.
    """

    proyecto = get_object_or_404(
        Proyecto,
        pk=proyecto_id
    )

    if proyecto.estado not in ("PROCESO", "FINALIZADO"):
        raise Http404(
            "Las tareas solo están disponibles para "
            "proyectos en proceso o finalizados."
        )

    return proyecto


def puede_gestionar_tareas(usuario, proyecto):
    """
    Administradores y responsables del proyecto
    pueden gestionar sus tareas mientras esté
    en proceso.
    """

    if not usuario.is_authenticated:
        return False

    if proyecto.estado != "PROCESO":
        return False

    if usuario.is_staff:
        return True

    return Investigador.objects.filter(
        usuario=usuario,
        pk=proyecto.investigador_principal_id
    ).exists()


def exigir_permiso_gestion(usuario, proyecto):

    if not puede_gestionar_tareas(usuario, proyecto):
        raise PermissionDenied(
            "No tienes permiso para modificar "
            "las tareas de este proyecto."
        )


def obtener_tarea(proyecto, tarea_id):

    return get_object_or_404(
        Tarea,
        pk=tarea_id,
        proyecto=proyecto
    )


def ordenar_tareas_en_arbol(tareas):
    """
    Devuelve tareas principales y subtareas
    en orden jerárquico.
    """

    tareas_por_id = {
        tarea.pk: tarea
        for tarea in tareas
    }

    por_padre = defaultdict(list)

    for tarea in tareas:

        padre_id = tarea.tarea_padre_id

        if padre_id not in tareas_por_id:
            padre_id = None

        por_padre[padre_id].append(tarea)

    resultado = []
    visitados = set()

    def recorrer(tarea, nivel):

        if tarea.pk in visitados:
            return

        visitados.add(tarea.pk)

        tarea.nivel = min(nivel, 4)
        resultado.append(tarea)

        for subtarea in por_padre.get(tarea.pk, []):
            recorrer(subtarea, nivel + 1)

    for tarea in por_padre.get(None, []):
        recorrer(tarea, 0)

    # Por seguridad, incluir tareas que pudieran
    # quedar fuera por datos antiguos incorrectos.
    for tarea in tareas:
        if tarea.pk not in visitados:
            recorrer(tarea, 0)

    return resultado


def obtener_descendientes(tarea):
    """
    Identifica todas las subtareas de una tarea,
    incluidos los niveles inferiores.
    """

    pendientes = [tarea.pk]
    visitados = {tarea.pk}
    descendientes = []

    while pendientes:

        padre_id = pendientes.pop()

        hijos = Tarea.objects.filter(
            tarea_padre_id=padre_id,
            proyecto_id=tarea.proyecto_id
        ).values_list("pk", flat=True)

        for hijo_id in hijos:

            if hijo_id not in visitados:

                visitados.add(hijo_id)
                descendientes.append(hijo_id)
                pendientes.append(hijo_id)

    return descendientes


# ==========================================
# LISTADO DE TAREAS DE UN PROYECTO
# ==========================================

@login_required
def tareas_proyecto(request, proyecto_id):

    proyecto = obtener_proyecto_tareas(
        proyecto_id
    )

    tareas = list(
        Tarea.objects.filter(
            proyecto=proyecto
        ).select_related(
            "responsable_investigador__usuario",
            "tarea_padre"
        ).order_by(
            "fecha_inicio",
            "pk"
        )
    )

    # Calcular las horas reales de cada tarea
    # sumando sus registros.

    horas_por_tarea = {
        registro["tarea_id"]: registro["total"]
        for registro in (
            RegistroHoras.objects.filter(
                tarea__proyecto=proyecto
            ).values(
                "tarea_id"
            ).annotate(
                total=Sum("horas")
            )
        )
    }

    horas_totales = Decimal("0.00")

    for tarea in tareas:

        tarea.horas_reales = horas_por_tarea.get(
            tarea.pk,
            Decimal("0.00")
        )

        horas_totales += tarea.horas_reales

        if tarea.horas_estimadas > 0:

            porcentaje = (
                tarea.horas_reales
                / tarea.horas_estimadas
            ) * 100

            tarea.porcentaje_horas = round(
                porcentaje,
                1
            )

            tarea.porcentaje_barra = min(
                float(porcentaje),
                100
            )

        else:

            tarea.porcentaje_horas = 0
            tarea.porcentaje_barra = 0

    total_tareas = len(tareas)

    tareas_finalizadas = sum(
        1 for tarea in tareas if tarea.finalizada
    )

    tareas_pendientes = (
        total_tareas - tareas_finalizadas
    )

    tareas = ordenar_tareas_en_arbol(tareas)

    contexto = {
        "proyecto": proyecto,
        "tareas": tareas,
        "total_tareas": total_tareas,
        "tareas_finalizadas": tareas_finalizadas,
        "tareas_pendientes": tareas_pendientes,
        "horas_totales": horas_totales,
        "puede_gestionar": puede_gestionar_tareas(
            request.user,
            proyecto
        ),
    }

    return render(
        request,
        "horas/tareas_proyecto.html",
        contexto
    )


# ==========================================
# CREAR TAREA
# ==========================================

@login_required
def crear_tarea(request, proyecto_id):

    proyecto = obtener_proyecto_tareas(
        proyecto_id
    )

    exigir_permiso_gestion(
        request.user,
        proyecto
    )

    if request.method == "POST":

        formulario = TareaForm(
            request.POST,
            proyecto=proyecto
        )

        if formulario.is_valid():

            tarea = formulario.save(
                commit=False
            )

            tarea.proyecto = proyecto
            tarea.save()

            messages.success(
                request,
                "Tarea creada correctamente."
            )

            return redirect(
                "horas:tareas_proyecto",
                proyecto_id=proyecto.pk
            )

    else:

        formulario = TareaForm(
            proyecto=proyecto
        )

    return render(
        request,
        "horas/formulario_tarea.html",
        {
            "proyecto": proyecto,
            "formulario": formulario,
            "titulo": "Nueva tarea",
            "modo_edicion": False,
        }
    )


# ==========================================
# EDITAR TAREA
# ==========================================

@login_required
def editar_tarea(request, proyecto_id, tarea_id):

    proyecto = obtener_proyecto_tareas(
        proyecto_id
    )

    exigir_permiso_gestion(
        request.user,
        proyecto
    )

    tarea = obtener_tarea(
        proyecto,
        tarea_id
    )

    if request.method == "POST":

        formulario = TareaForm(
            request.POST,
            instance=tarea,
            proyecto=proyecto
        )

        if formulario.is_valid():

            formulario.save()

            messages.success(
                request,
                "Tarea actualizada correctamente."
            )

            return redirect(
                "horas:tareas_proyecto",
                proyecto_id=proyecto.pk
            )

    else:

        formulario = TareaForm(
            instance=tarea,
            proyecto=proyecto
        )

    return render(
        request,
        "horas/formulario_tarea.html",
        {
            "proyecto": proyecto,
            "tarea": tarea,
            "formulario": formulario,
            "titulo": "Editar tarea",
            "modo_edicion": True,
        }
    )


# ==========================================
# FINALIZAR TAREA
# ==========================================

@login_required
@require_POST
def finalizar_tarea(request, proyecto_id, tarea_id):

    proyecto = obtener_proyecto_tareas(
        proyecto_id
    )

    exigir_permiso_gestion(
        request.user,
        proyecto
    )

    tarea = obtener_tarea(
        proyecto,
        tarea_id
    )

    # Al finalizar una tarea principal también
    # se finalizan sus subtareas, como en
    # el sistema antiguo.

    descendientes = obtener_descendientes(
        tarea
    )

    with transaction.atomic():

        Tarea.objects.filter(
            proyecto=proyecto,
            pk__in=[tarea.pk] + descendientes
        ).update(
            finalizada=True
        )

    messages.success(
        request,
        "Tarea finalizada correctamente."
    )

    return redirect(
        "horas:tareas_proyecto",
        proyecto_id=proyecto.pk
    )


# ==========================================
# REABRIR TAREA
# ==========================================

@login_required
@require_POST
def reabrir_tarea(request, proyecto_id, tarea_id):

    proyecto = obtener_proyecto_tareas(
        proyecto_id
    )

    exigir_permiso_gestion(
        request.user,
        proyecto
    )

    tarea = obtener_tarea(
        proyecto,
        tarea_id
    )

    # Reabrimos la tarea y, si tenía padres
    # finalizados, también los reabrimos.

    ids_reabrir = [tarea.pk]
    padre = tarea.tarea_padre
    visitados = {tarea.pk}

    while padre is not None:

        if padre.pk in visitados:
            break

        visitados.add(padre.pk)
        ids_reabrir.append(padre.pk)
        padre = padre.tarea_padre

    with transaction.atomic():

        Tarea.objects.filter(
            proyecto=proyecto,
            pk__in=ids_reabrir
        ).update(
            finalizada=False
        )

    messages.success(
        request,
        "Tarea reabierta correctamente."
    )

    return redirect(
        "horas:tareas_proyecto",
        proyecto_id=proyecto.pk
    )


# ==========================================
# ELIMINAR TAREA
# ==========================================

@login_required
@require_POST
def eliminar_tarea(request, proyecto_id, tarea_id):

    proyecto = obtener_proyecto_tareas(
        proyecto_id
    )

    exigir_permiso_gestion(
        request.user,
        proyecto
    )

    tarea = obtener_tarea(
        proyecto,
        tarea_id
    )

    # No se puede borrar una tarea con subtareas.

    if Tarea.objects.filter(
        tarea_padre=tarea
    ).exists():

        messages.error(
            request,
            "No puedes eliminar una tarea que "
            "tiene subtareas asociadas."
        )

        return redirect(
            "horas:tareas_proyecto",
            proyecto_id=proyecto.pk
        )

    # Tampoco una tarea con horas registradas.

    if RegistroHoras.objects.filter(
        tarea=tarea
    ).exists():

        messages.error(
            request,
            "No puedes eliminar una tarea que "
            "tiene horas registradas."
        )

        return redirect(
            "horas:tareas_proyecto",
            proyecto_id=proyecto.pk
        )

    try:

        tarea.delete()

        messages.success(
            request,
            "Tarea eliminada correctamente."
        )

    except ProtectedError:

        messages.error(
            request,
            "No se puede eliminar esta tarea "
            "porque tiene datos relacionados."
        )

    return redirect(
        "horas:tareas_proyecto",
        proyecto_id=proyecto.pk
    )
