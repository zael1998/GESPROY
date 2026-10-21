from collections import defaultdict
from datetime import timedelta

from decimal import Decimal

from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.core.exceptions import PermissionDenied

from django.db import transaction

from django.db.models import Count, Sum

from django.db.models.deletion import ProtectedError

from django.http import Http404

from django.utils import timezone
from django.shortcuts import (

    get_object_or_404,

    redirect,

    render,

)

from django.views.decorators.http import require_POST

from proyectos.models import Dedicacion, Proyecto

from usuarios.models import Investigador


from .forms import TareaForm, ComentarioTareaForm

from .models import ComentarioTarea, RegistroHoras, Tarea

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

    # Número de comentarios individuales de cada tarea, sin mezclar
    # el comentario general que ya existía en el modelo Tarea.
    comentarios_por_tarea = {
        fila["tarea_id"]: fila["total"]
        for fila in (
            ComentarioTarea.objects.filter(tarea__proyecto=proyecto)
            .values("tarea_id")
            .annotate(total=Count("pk"))
        )
    }
    for tarea in tareas:
        tarea.total_comentarios = comentarios_por_tarea.get(tarea.pk, 0)

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


# ==========================================
# DIAGRAMA DE GANTT (SOLO CONSULTA)
# ==========================================

@login_required
def gantt_proyecto(request, proyecto_id):
    """
    Representación temporal de las tareas del proyecto.

    No modifica tareas ni registros de horas. Reutiliza las restricciones
    de consulta de obtener_proyecto_tareas() y las de edición mediante
    puede_gestionar_tareas(), al igual que el listado existente.
    """
    proyecto = obtener_proyecto_tareas(proyecto_id)

    # La escala afecta únicamente a la anchura visual de cada día.
    escalas = {"dia": 34, "semana": 17, "mes": 8}
    escala = request.GET.get("escala", "semana")
    if escala not in escalas:
        escala = "semana"
    pixeles_dia = escalas[escala]

    tareas = list(
        Tarea.objects.filter(proyecto=proyecto)
        .select_related("responsable_investigador__usuario", "tarea_padre")
        .order_by("fecha_inicio", "pk")
    )
    tareas = ordenar_tareas_en_arbol(tareas)

    contexto = {
        "proyecto": proyecto,
        "tareas": tareas,
        "puede_gestionar": puede_gestionar_tareas(request.user, proyecto),
        "escala": escala,
        "gantt_ancho": 0,
        "gantt_semanal": pixeles_dia * 7,
        "meses": [],
        "periodos": [],
        "mostrar_hoy": False,
    }

    if not tareas:
        return render(request, "horas/gantt_proyecto.html", contexto)

    # Alinear el eje con semanas completas (lunes-domingo).
    fecha_minima = min(tarea.fecha_inicio for tarea in tareas)
    fecha_maxima = max(
        max(tarea.fecha_inicio, tarea.fecha_fin)
        if tarea.fecha_fin is not None
        else tarea.fecha_inicio
        for tarea in tareas
    )
    inicio = fecha_minima - timedelta(days=fecha_minima.weekday())
    fin = fecha_maxima + timedelta(days=6 - fecha_maxima.weekday())
    # Para proyectos de muy pocos días, ofrecer cuatro semanas de contexto.
    if (fin - inicio).days < 27:
        fin = inicio + timedelta(days=27)
    fin_exclusivo = fin + timedelta(days=1)

    dias_totales = (fin_exclusivo - inicio).days
    ancho_total = dias_totales * pixeles_dia

    # Cabecera principal: meses reales, calculados por días exactos.
    meses = []
    cursor = inicio
    while cursor < fin_exclusivo:
        siguiente_mes = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        extremo = min(siguiente_mes, fin_exclusivo)
        meses.append({
            "etiqueta": cursor.strftime("%m/%Y"),
            "ancho": (extremo - cursor).days * pixeles_dia,
        })
        cursor = extremo

    # Cabecera secundaria: días, o semanas naturales según escala.
    periodos = []
    cursor = inicio
    while cursor < fin_exclusivo:
        if escala == "dia":
            extremo = cursor + timedelta(days=1)
            etiqueta = str(cursor.day)
        else:
            extremo = min(cursor + timedelta(days=7), fin_exclusivo)
            if escala == "semana":
                etiqueta = cursor.strftime("%d/%m")
            else:
                etiqueta = f"S{cursor.isocalendar().week:02d}"
        periodos.append({
            "etiqueta": etiqueta,
            "ancho": (extremo - cursor).days * pixeles_dia,
        })
        cursor = extremo

    # Las horas reales se muestran como dato, NO como progreso completado.
    horas_por_tarea = {
        fila["tarea_id"]: fila["total"]
        for fila in (
            RegistroHoras.objects.filter(tarea__proyecto=proyecto)
            .values("tarea_id")
            .annotate(total=Sum("horas"))
        )
    }

    for tarea in tareas:
        tarea.gantt_izquierda = (tarea.fecha_inicio - inicio).days * pixeles_dia
        tarea.gantt_sin_fin = tarea.fecha_fin is None
        if tarea.gantt_sin_fin:
            tarea.gantt_ancho = 0  # Se representa solo un marcador.
            fin_texto = "Sin fecha final"
        else:
            # El día de finalización forma parte del período mostrado.
            dias_duracion = max((tarea.fecha_fin - tarea.fecha_inicio).days + 1, 1)
            tarea.gantt_ancho = dias_duracion * pixeles_dia
            fin_texto = tarea.fecha_fin.strftime("%d/%m/%Y")

        responsable = (
            str(tarea.responsable_investigador)
            if tarea.responsable_investigador_id
            else "Sin responsable"
        )
        horas_reales = horas_por_tarea.get(tarea.pk, Decimal("0.00"))
        tarea.gantt_responsable = responsable
        tarea.gantt_titulo = (
            f"{tarea.nombre}\n"
            f"Inicio: {tarea.fecha_inicio:%d/%m/%Y}\n"
            f"Fin: {fin_texto}\n"
            f"Responsable: {responsable}\n"
            f"Horas: {horas_reales} registradas / "
            f"{tarea.horas_estimadas} previstas\n"
            f"Estado: {'Finalizada' if tarea.finalizada else 'Pendiente'}"
        )

    hoy = timezone.localdate()
    mostrar_hoy = inicio <= hoy <= fin
    contexto.update({
        "gantt_ancho": ancho_total,
        "gantt_semanal": 7 * pixeles_dia,
        "meses": meses,
        "periodos": periodos,
        "gantt_inicio": inicio,
        "gantt_fin": fin,
        "mostrar_hoy": mostrar_hoy,
        "hoy_izquierda": (hoy - inicio).days * pixeles_dia + (pixeles_dia / 2)
        if mostrar_hoy else 0,
    })
    return render(request, "horas/gantt_proyecto.html", contexto)

# ==========================================
# COMENTARIOS INDIVIDUALES DE TAREAS
# ==========================================

def puede_comentar_tarea(usuario, proyecto, tarea):
    """
    Se puede publicar solo en proyectos en proceso y siendo:
    - Administrador / superadministrador según la configuración actual is_staff.
    - Investigador principal del proyecto.
    - Investigador responsable de esta tarea.
    - Investigador que figura en las dedicaciones del proyecto.

    La lectura usa la misma política que el listado de tareas existente.
    """
    if not usuario.is_authenticated or proyecto.estado != "PROCESO":
        return False

    if puede_gestionar_tareas(usuario, proyecto):
        return True

    if tarea.responsable_investigador_id and Investigador.objects.filter(
        pk=tarea.responsable_investigador_id,
        usuario=usuario,
    ).exists():
        return True

    return Dedicacion.objects.filter(
        proyecto=proyecto,
        investigador__usuario=usuario,
    ).exists()


@login_required
def comentarios_tarea(request, proyecto_id, tarea_id):
    """Historial de comentarios de UNA tarea, también si es subtarea."""
    proyecto = obtener_proyecto_tareas(proyecto_id)
    tarea = obtener_tarea(proyecto, tarea_id)
    puede_comentar = puede_comentar_tarea(request.user, proyecto, tarea)

    if request.method == "POST":
        if not puede_comentar:
            raise PermissionDenied(
                "No tienes permiso para publicar comentarios en esta tarea."
            )

        formulario = ComentarioTareaForm(request.POST)
        if formulario.is_valid():
            ComentarioTarea.objects.create(
                tarea=tarea,
                autor=request.user,
                contenido=formulario.cleaned_data["contenido"],
            )
            messages.success(request, "Comentario publicado correctamente.")
            return redirect(
                "horas:comentarios_tarea",
                proyecto_id=proyecto.pk,
                tarea_id=tarea.pk,
            )
    else:
        formulario = ComentarioTareaForm() if puede_comentar else None

    comentarios = (
        ComentarioTarea.objects.filter(tarea=tarea)
        .select_related("autor")
        .order_by("fecha_creacion", "pk")
    )

    return render(
        request,
        "horas/comentarios_tarea.html",
        {
            "proyecto": proyecto,
            "tarea": tarea,
            "comentarios": comentarios,
            "total_comentarios": comentarios.count(),
            "puede_comentar": puede_comentar,
            "formulario": formulario,
        },
    )
