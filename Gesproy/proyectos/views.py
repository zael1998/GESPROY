from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Lower
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from datetime import date
from horas.models import Tarea, RegistroHoras
from django.db import transaction
from django.contrib import messages
import json
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urlparse
from usuarios.models import Investigador
from .models import (
    Proyecto,
    Socio,
    ContactoSocio,
    TipoProyecto,
    Organismo,
    TipoParticipacion,
    Area,
    Dedicacion,
    ParticipacionSocio,
    LineaInvestigacion,
    Asignacion,
    DenegacionProyecto,
    Festivo,
    )
from .forms import (
    ProyectoForm,
    EditarProyectoDefinicionForm,
    SolicitarProyectoForm,
    FinalizarProyectoDefinicionForm,
    EditarProyectoSolicitadoForm,
    NegociarProyectoForm,
    PasarProyectoAProcesoForm,
    PasarProyectoADenegadoForm,
    EditarProyectoNegociacionForm,
    EditarProyectoProcesoForm,
    VolverEstadoAnteriorProcesoForm,
    CopiarProyectoDenegadoForm,
    CrearSocioForm,
    CrearTipoProyectoForm,
    CrearOrganismoForm,
    CrearTipoParticipacionForm,
    CrearAreaForm,
    BuscarProyectosForm,
    CrearLineaInvestigacionForm,
    AsignacionLineaForm,
    EditarPorcentajeAsignacionForm,
    AsignacionProyectoForm,
    FestivoForm
)

from horas.models import Tarea, RegistroHoras


# LISTA DE TODOS LOS PROYECTOS


# ==========================================
# PÁGINA INICIAL DE GESPROY
# ==========================================

def inicio(request):

    # Si el usuario ya ha iniciado sesión
    if request.user.is_authenticated:
        return redirect("mis_proyectos")

    # Si no ha iniciado sesión, ir al login
    return redirect(settings.LOGIN_URL)


def lista_proyectos(request):
    proyectos = Proyecto.objects.all()

    return render(
        request,
        "proyectos/lista_proyectos.html",
        {"proyectos": proyectos}
    )


# PROYECTOS SOLICITADOS

def proyectos_solicitados(request):
    proyectos = Proyecto.objects.filter(estado="SOLICITADO")

    return render(
        request,
        "proyectos/proyectos_solicitados.html",
        {"proyectos": proyectos}
    )


# PROYECTOS EN NEGOCIACIÓN

def proyectos_en_negociacion(request):
    proyectos = Proyecto.objects.filter(estado="NEGOCIACION")

    return render(
        request,
        "proyectos/proyectos_en_negociacion.html",
        {"proyectos": proyectos}
    )


# PROYECTOS EN PROCESO

def proyectos_en_proceso(request):
    proyectos = Proyecto.objects.filter(estado="PROCESO")
    hoy = timezone.localdate()

    for proyecto in proyectos:

        # PRIMERA BARRA: TIEMPO TRANSCURRIDO
        proyecto.porcentaje_tiempo = 0

        if proyecto.fecha_inicio and proyecto.fecha_fin:

            duracion_total = (
                proyecto.fecha_fin - proyecto.fecha_inicio
            ).days

            tiempo_transcurrido = (
                hoy - proyecto.fecha_inicio
            ).days

            if duracion_total > 0:
                porcentaje = (
                    tiempo_transcurrido / duracion_total
                ) * 100

                proyecto.porcentaje_tiempo = max(
                    0, min(100, porcentaje)
                )

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
            porcentaje = (
                horas_realizadas / horas_previstas
            ) * 100

            proyecto.porcentaje_trabajo = min(
                100, porcentaje
            )

    return render(
        request,
        "proyectos/proyectos_en_proceso.html",
        {"proyectos": proyectos}
    )


# PROYECTOS FINALIZADOS

def proyectos_finalizados(request):
    proyectos = Proyecto.objects.filter(estado="FINALIZADO")

    return render(
        request,
        "proyectos/proyectos_finalizados.html",
        {"proyectos": proyectos}
    )


# PROYECTOS DENEGADOS

def proyectos_denegados(request):
    proyectos = Proyecto.objects.filter(estado="DENEGADO")

    return render(
        request,
        "proyectos/proyectos_denegados.html",
        {"proyectos": proyectos}
    )


# PROYECTOS EN DEFINICIÓN

def proyectos_en_definicion(request):
    proyectos = Proyecto.objects.filter(estado="DEFINICION")

    return render(
        request,
        "proyectos/proyectos_en_definicion.html",
        {"proyectos": proyectos}
    )


# DETALLE DE UN PROYECTO


# ==========================================
# FICHA DE DETALLES DE UN PROYECTO
# ==========================================

@login_required
def detalle_proyecto(request, id):

    proyecto = get_object_or_404(
        Proyecto.objects.select_related(
            "organismo",
            "tipo_proyecto",
            "tipo_participacion",
            "investigador_principal__usuario"
        ).prefetch_related(
            "areas",
            "denegaciones"
        ),
        pk=id
    )

    # --------------------------------------
    # PERMISOS DE CONSULTA
    # --------------------------------------

    investigador_actual = Investigador.objects.filter(
        usuario=request.user
    ).first()

    asociado = False

    if investigador_actual is not None:

        asociado = (
            proyecto.investigador_principal_id == investigador_actual.id
            or Dedicacion.objects.filter(
                proyecto=proyecto,
                investigador=investigador_actual
            ).exists()
        )

    es_publico_interno = proyecto.estado in [
        "PROCESO",
        "FINALIZADO"
    ]

    if not (
        request.user.is_staff
        or asociado
        or es_publico_interno
    ):
        raise PermissionDenied(
            "No tienes permiso para consultar este proyecto."
        )

    # --------------------------------------
    # PESTAÑA SELECCIONADA
    # --------------------------------------

    pestana = request.GET.get("pestana", "datos")

    pestanas_validas = {
        "datos",
        "investigadores",
        "socios",
        "denegaciones"
    }

    if pestana not in pestanas_validas:
        pestana = "datos"

    # --------------------------------------
    # LÍNEA DE ESTADOS
    # --------------------------------------

    estados = [
        ("DEFINICION", "Definición"),
        ("SOLICITADO", "Solicitado"),
        ("NEGOCIACION", "Negociación"),
        ("PROCESO", "En proceso"),
        ("FINALIZADO", "Finalizado"),
        ("DENEGADO", "Denegado")
    ]

    orden_actual = next(
        (
            indice
            for indice, (codigo, nombre) in enumerate(estados)
            if codigo == proyecto.estado
        ),
        0
    )

    pasos_estado = []

    for indice, (codigo, nombre) in enumerate(estados):

        pasos_estado.append({
            "codigo": codigo,
            "nombre": nombre,
            "activo": codigo == proyecto.estado,
            "completado": (
                proyecto.estado != "DENEGADO"
                and indice < orden_actual
                and codigo != "DENEGADO"
            ),
            "denegado": codigo == "DENEGADO"
        })

    # --------------------------------------
    # NOMBRE COMPLETO DE INVESTIGADORES
    # --------------------------------------

    def nombre_investigador(investigador):

        if investigador is None:
            return "—"

        usuario = investigador.usuario

        return (
            usuario.get_full_name().strip()
            or usuario.username
        )

    # --------------------------------------
    # INVESTIGADORES DEL PROYECTO
    # --------------------------------------

    dedicaciones = Dedicacion.objects.filter(
        proyecto=proyecto
    ).select_related(
        "investigador__usuario",
        "validador__usuario"
    ).order_by(
        "investigador__usuario__last_name",
        "investigador__usuario__first_name"
    )

    investigadores = []
    investigadores_incluidos = set()

    for dedicacion in dedicaciones:

        investigador = dedicacion.investigador

        investigadores_incluidos.add(investigador.pk)

        investigadores.append({
            "id": investigador.pk,
            "nombre": nombre_investigador(investigador),
            "porcentaje": dedicacion.porcentaje,
            "responsable": (
                proyecto.investigador_principal_id
                == investigador.pk
            ),
            "validador": nombre_investigador(
                dedicacion.validador
            )
        })

    # El investigador principal también debe aparecer,
    # aunque todavía no tenga una dedicación registrada.

    if (
        proyecto.investigador_principal_id
        and proyecto.investigador_principal_id
        not in investigadores_incluidos
    ):

        investigadores.append({
            "id": proyecto.investigador_principal_id,
            "nombre": nombre_investigador(
                proyecto.investigador_principal
            ),
            "porcentaje": None,
            "responsable": True,
            "validador": "—"
        })

    # --------------------------------------
    # SOCIOS DEL PROYECTO
    # --------------------------------------

    participaciones = list(
        ParticipacionSocio.objects.filter(
            proyecto=proyecto
        ).select_related(
            "socio",
            "investigador_responsable__usuario"
        ).order_by(
            "socio__nombre_empresa"
        )
    )

    socios_ids = {
        participacion.socio_id
        for participacion in participaciones
    }

    contactos_por_socio = {}

    if socios_ids:

        contactos = ContactoSocio.objects.filter(
            socio_id__in=socios_ids
        ).order_by(
            "apellido",
            "nombre"
        )

        for contacto in contactos:

            if contacto.socio_id not in contactos_por_socio:

                contactos_por_socio[contacto.socio_id] = (
                    f"{contacto.nombre} {contacto.apellido}"
                ).strip()

    socios = []

    for participacion in participaciones:

        socios.append({
            "id": participacion.pk,
            "empresa": participacion.socio.nombre_empresa,
            "contacto": contactos_por_socio.get(
                participacion.socio_id,
                "—"
            ),
            "porcentaje": participacion.porcentaje_participacion,
            "importe": participacion.importe,
            "responsable": nombre_investigador(
                participacion.investigador_responsable
            )
        })

    # --------------------------------------
    # LÍNEAS DE INVESTIGACIÓN DEL PROYECTO
    # --------------------------------------

    asignaciones = Asignacion.objects.filter(
        proyecto=proyecto
    ).select_related(
        "linea_investigacion"
    )

    nombres_lineas = [
        asignacion.linea_investigacion.nombre
        for asignacion in asignaciones
    ]

    # --------------------------------------
    # HISTORIAL DE DENEGACIONES
    # --------------------------------------

    denegaciones = [
        {
            "fecha": denegacion.fecha,
            "causa": denegacion.causa,
            "solo_fecha": False
        }
        for denegacion in proyecto.denegaciones.all()
    ]

    # Compatibilidad con datos anteriores a la
    # creación del modelo DenegacionProyecto.

    if (
        not denegaciones
        and (
            proyecto.fecha_denegacion
            or proyecto.causa_denegacion
        )
    ):

        denegaciones.append({
            "fecha": proyecto.fecha_denegacion,
            "causa": proyecto.causa_denegacion or "Sin causa registrada",
            "solo_fecha": True
        })

    # --------------------------------------
    # PERMISOS DE EDICIÓN
    # --------------------------------------

    puede_editar = request.user.is_staff

    # --------------------------------------
    # MOSTRAR FICHA
    # --------------------------------------

    return render(
        request,
        "proyectos/detalle_proyecto.html",
        {
            "proyecto": proyecto,
            "pestana": pestana,
            "pasos_estado": pasos_estado,
            "investigadores": investigadores,
            "socios": socios,
            "denegaciones": denegaciones,
            "nombres_lineas": nombres_lineas,
            "puede_editar": puede_editar,
            "total_investigadores": len(investigadores),
            "total_socios": len(socios),
            "total_denegaciones": len(denegaciones)
        }
    )



# CREAR PROYECTO

def crear_proyecto(request):

    if request.method == "POST":
        formulario = ProyectoForm(request.POST)

        if formulario.is_valid():
            formulario.save()

            return redirect("proyectos_en_definicion")

    else:
        formulario = ProyectoForm()

    return render(
        request,
        "proyectos/crear_proyecto.html",
        {"formulario": formulario}
    )


# EDITAR PROYECTO EN DEFINICIÓN

def editar_proyecto_definicion(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="DEFINICION"
    )

    formulario = EditarProyectoDefinicionForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        return redirect("proyectos_en_definicion")

    return render(
        request,
        "proyectos/editar_proyecto_definicion.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# PASAR PROYECTO A SOLICITADO

def solicitar_proyecto(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="DEFINICION"
    )

    formulario = SolicitarProyectoForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():
        proyecto = formulario.save(commit=False)

        proyecto.estado = "SOLICITADO"
        proyecto.save()
        formulario.save_m2m()

        return redirect("proyectos_solicitados")

    return render(
        request,
        "proyectos/solicitar_proyecto.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# FINALIZAR PROYECTO EN DEFINICIÓN

def finalizar_proyecto_definicion(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="DEFINICION"
    )

    formulario = FinalizarProyectoDefinicionForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():
        proyecto = formulario.save(commit=False)

        proyecto.estado = "FINALIZADO"
        proyecto.save()
        formulario.save_m2m()

        return redirect("proyectos_finalizados")

    return render(
        request,
        "proyectos/finalizar_proyecto_definicion.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# BORRAR PROYECTO EN DEFINICIÓN

def borrar_proyecto_definicion(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="DEFINICION"
    )

    error = None

    if request.method == "POST":
        try:
            proyecto.delete()

            return redirect("proyectos_en_definicion")

        except ProtectedError:
            error = (
                "No se puede borrar este proyecto porque "
                "tiene información relacionada protegida."
            )

    return render(
        request,
        "proyectos/borrar_proyecto_definicion.html",
        {
            "proyecto": proyecto,
            "error": error,
        }
    )


# EDITAR PROYECTO SOLICITADO

def editar_proyecto_solicitado(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="SOLICITADO"
    )

    formulario = EditarProyectoSolicitadoForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        return redirect("proyectos_solicitados")

    return render(
        request,
        "proyectos/editar_proyecto_solicitado.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# CAMBIAR PROYECTO A NEGOCIACIÓN

def negociar_proyecto(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="SOLICITADO"
    )

    formulario = NegociarProyectoForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():
        proyecto = formulario.save(commit=False)

        proyecto.estado = "NEGOCIACION"
        proyecto.save()
        formulario.save_m2m()

        return redirect("proyectos_en_negociacion")

    return render(
        request,
        "proyectos/negociar_proyecto.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# CAMBIAR PROYECTO A PROCESO

def pasar_proyecto_a_proceso(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="SOLICITADO"
    )

    formulario = PasarProyectoAProcesoForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():
        proyecto = formulario.save(commit=False)

        proyecto.estado = "PROCESO"
        proyecto.save()
        formulario.save_m2m()

        return redirect("proyectos_en_proceso")

    return render(
        request,
        "proyectos/pasar_proyecto_a_proceso.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# CAMBIAR PROYECTO A DENEGADO

def denegar_proyecto(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="SOLICITADO"
    )

    formulario = PasarProyectoADenegadoForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():
        proyecto = formulario.save(commit=False)

        proyecto.estado = "DENEGADO"
        proyecto.save()
        formulario.save_m2m()

        return redirect("proyectos_denegados")

    return render(
        request,
        "proyectos/denegar_proyecto.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# BORRAR PROYECTO SOLICITADO

def borrar_proyecto_solicitado(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="SOLICITADO"
    )

    error = None

    if request.method == "POST":
        try:
            proyecto.delete()

            return redirect("proyectos_solicitados")

        except ProtectedError:
            error = (
                "No se puede borrar este proyecto porque "
                "tiene información relacionada protegida."
            )

    return render(
        request,
        "proyectos/borrar_proyecto_solicitado.html",
        {
            "proyecto": proyecto,
            "error": error,
        }
    )


# DEVOLVER PROYECTO SOLICITADO A DEFINICIÓN

@require_POST
def volver_proyecto_a_definicion(request, id):
    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="SOLICITADO"
    )

    proyecto.estado = "DEFINICION"
    proyecto.save(update_fields=["estado"])

    return redirect("proyectos_en_definicion")


# ==========================================
# EDITAR PROYECTO EN NEGOCIACIÓN
# ==========================================

def editar_proyecto_negociacion(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="NEGOCIACION"
    )

    formulario = EditarProyectoNegociacionForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():

        formulario.save()

        return redirect("proyectos_en_negociacion")

    return render(
        request,
        "proyectos/editar_proyecto_negociacion.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )
    


# ==========================================
# PASAR DE NEGOCIACIÓN A PROCESO
# ==========================================

def pasar_negociacion_a_proceso(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="NEGOCIACION"
    )

    formulario = PasarProyectoAProcesoForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():

        proyecto = formulario.save(commit=False)

        proyecto.estado = "PROCESO"
        proyecto.save()
        formulario.save_m2m()

        return redirect("proyectos_en_proceso")

    return render(
        request,
        "proyectos/pasar_negociacion_a_proceso.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )
    

# ==========================================
# PASAR DE NEGOCIACIÓN A DENEGADO
# ==========================================

def denegar_proyecto_negociacion(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="NEGOCIACION"
    )

    formulario = PasarProyectoADenegadoForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():

        proyecto = formulario.save(commit=False)

        proyecto.estado = "DENEGADO"
        proyecto.save()
        formulario.save_m2m()

        return redirect("proyectos_denegados")

    return render(
        request,
        "proyectos/denegar_proyecto_negociacion.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# ==========================================
# BORRAR PROYECTO EN NEGOCIACIÓN
# ==========================================

def borrar_proyecto_negociacion(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="NEGOCIACION"
    )

    error = None

    if request.method == "POST":

        try:
            proyecto.delete()

            return redirect("proyectos_en_negociacion")

        except ProtectedError:
            error = (
                "No se puede borrar este proyecto porque "
                "tiene información relacionada protegida."
            )

    return render(
        request,
        "proyectos/borrar_proyecto_negociacion.html",
        {
            "proyecto": proyecto,
            "error": error,
        }
    )


# ==========================================
# VOLVER DE NEGOCIACIÓN A SOLICITADO
# ==========================================

@require_POST
def volver_negociacion_a_solicitado(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="NEGOCIACION"
    )

    proyecto.estado = "SOLICITADO"

    proyecto.save(update_fields=["estado"])

    return redirect("proyectos_solicitados")


# ==========================================
# EDITAR PROYECTO EN PROCESO
# ==========================================

def editar_proyecto_proceso(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="PROCESO"
    )

    formulario = EditarProyectoProcesoForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():

        formulario.save()

        return redirect("proyectos_en_proceso")

    return render(
        request,
        "proyectos/editar_proyecto_proceso.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )
    

# ==========================================
# FINALIZAR PROYECTO EN PROCESO
# ==========================================

def finalizar_proyecto_proceso(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="PROCESO"
    )

    formulario = FinalizarProyectoDefinicionForm(
        request.POST or None,
        instance=proyecto
    )

    if request.method == "POST" and formulario.is_valid():

        proyecto = formulario.save(commit=False)

        proyecto.estado = "FINALIZADO"
        proyecto.save()
        formulario.save_m2m()

        return redirect("proyectos_finalizados")

    return render(
        request,
        "proyectos/finalizar_proyecto_proceso.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )
    

# ==========================================
# BORRAR PROYECTO EN PROCESO
# ==========================================

def borrar_proyecto_proceso(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="PROCESO"
    )

    error = None

    if request.method == "POST":
        try:
            proyecto.delete()
            return redirect("proyectos_en_proceso")

        except ProtectedError:
            error = (
                "No se puede borrar este proyecto porque "
                "tiene información relacionada protegida."
            )

    return render(
        request,
        "proyectos/borrar_proyecto_proceso.html",
        {
            "proyecto": proyecto,
            "error": error,
        }
    )
    

# ==========================================
# VOLVER AL ESTADO ANTERIOR DESDE PROCESO
# ==========================================

def volver_estado_anterior_proceso(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="PROCESO"
    )

    if request.method == "POST":

        formulario = VolverEstadoAnteriorProcesoForm(
            request.POST
        )

        if formulario.is_valid():

            nuevo_estado = formulario.cleaned_data["estado"]

            proyecto.estado = nuevo_estado
            proyecto.save(update_fields=["estado"])

            if nuevo_estado == "DEFINICION":
                return redirect("proyectos_en_definicion")

            elif nuevo_estado == "SOLICITADO":
                return redirect("proyectos_solicitados")

            elif nuevo_estado == "NEGOCIACION":
                return redirect("proyectos_en_negociacion")

    else:
        formulario = VolverEstadoAnteriorProcesoForm()

    return render(
        request,
        "proyectos/volver_estado_anterior_proceso.html",
        {
            "proyecto": proyecto,
            "formulario": formulario,
        }
    )


# ==========================================
# REACTIVAR PROYECTO FINALIZADO
# ==========================================

def reactivar_proyecto_finalizado(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="FINALIZADO"
    )

    if request.method == "POST":

        proyecto.estado = "PROCESO"
        proyecto.save(update_fields=["estado"])

        return redirect("proyectos_en_proceso")

    return render(
        request,
        "proyectos/reactivar_proyecto_finalizado.html",
        {
            "proyecto": proyecto,
        }
    )


# ==========================================
# BORRAR PROYECTO FINALIZADO
# ==========================================

def borrar_proyecto_finalizado(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="FINALIZADO"
    )

    error = None

    if request.method == "POST":

        try:
            proyecto.delete()

            return redirect("proyectos_finalizados")

        except ProtectedError:
            error = (
                "No se puede borrar este proyecto porque "
                "tiene información relacionada protegida."
            )

    return render(
        request,
        "proyectos/borrar_proyecto_finalizado.html",
        {
            "proyecto": proyecto,
            "error": error,
        }
    )

# ==========================================
# COPIAR PROYECTO DENEGADO A DEFINICIÓN
# ==========================================


def copiar_proyecto_denegado(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="DENEGADO"
    )

    if request.method == "POST":

        formulario = CopiarProyectoDenegadoForm(
            request.POST
        )

        if formulario.is_valid():

            nuevo_proyecto = formulario.save(commit=False)

            nuevo_proyecto.estado = "DEFINICION"

            nuevo_proyecto.save()
            formulario.save_m2m()

            return redirect("proyectos_en_definicion")

    else:

        datos_iniciales = {
            campo: getattr(proyecto, campo)
            for campo in CopiarProyectoDenegadoForm.Meta.fields
        }

        formulario = CopiarProyectoDenegadoForm(
            initial=datos_iniciales
        )

    return render(
        request,
        "proyectos/copiar_proyecto_denegado.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# ==========================================
# BORRAR PROYECTO DENEGADO
# ==========================================

def borrar_proyecto_denegado(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="DENEGADO"
    )

    error = None

    if request.method == "POST":

        try:
            proyecto.delete()

            return redirect("proyectos_denegados")

        except ProtectedError:
            error = (
                "No se puede borrar este proyecto porque "
                "tiene información relacionada protegida."
            )

    return render(
        request,
        "proyectos/borrar_proyecto_denegado.html",
        {
            "proyecto": proyecto,
            "error": error,
        }
    )
    

# ==========================================
# VOLVER DE DENEGADO A UN ESTADO ANTERIOR
# ==========================================

def volver_estado_anterior_denegado(request, id):

    proyecto = get_object_or_404(
        Proyecto,
        id=id,
        estado="DENEGADO"
    )

    formulario = VolverEstadoAnteriorProcesoForm(
        request.POST or None
    )

    if request.method == "POST" and formulario.is_valid():

        nuevo_estado = formulario.cleaned_data["estado"]

        proyecto.estado = nuevo_estado
        proyecto.save(update_fields=["estado"])

        if nuevo_estado == "DEFINICION":
            return redirect("proyectos_en_definicion")

        elif nuevo_estado == "SOLICITADO":
            return redirect("proyectos_solicitados")

        elif nuevo_estado == "NEGOCIACION":
            return redirect("proyectos_en_negociacion")

    return render(
        request,
        "proyectos/volver_estado_anterior_denegado.html",
        {
            "formulario": formulario,
            "proyecto": proyecto,
        }
    )


# ==========================================
# PANEL DE ADMINISTRACIÓN DE GESPROY
# ==========================================

@staff_member_required
def panel_administracion(request):

    return render(
        request,
        "proyectos/panel_administracion.html"
    )


# ==========================================
# ADMINISTRACIÓN DE SOCIOS
# ==========================================

@staff_member_required
def gestion_socios(request):

    socios = Socio.objects.prefetch_related(
        Prefetch(
            "contactosocio_set",
            queryset=ContactoSocio.objects.order_by("id"),
            to_attr="contactos"
        )
    ).order_by("nombre_empresa")

    return render(
        request,
        "proyectos/gestion_socios.html",
        {
            "socios": socios,
        }
    )


# ==========================================
# AÑADIR SOCIO
# ==========================================

@staff_member_required
def anadir_socio(request):

    if request.method == "POST":

        formulario = CrearSocioForm(request.POST)

        if formulario.is_valid():

            formulario.save()

            return redirect("gestion_socios")

    else:

        formulario = CrearSocioForm()

    return render(
        request,
        "proyectos/anadir_socio.html",
        {
            "formulario": formulario,
        }
    )


# ==========================================
# ADMINISTRACIÓN DE TIPOS DE PROYECTO
# ==========================================

@staff_member_required
def gestion_tipos_proyecto(request):

    tipos = TipoProyecto.objects.all().order_by("nombre")

    if request.method == "POST":

        formulario = CrearTipoProyectoForm(request.POST)

        if formulario.is_valid():

            formulario.save()

            return redirect("gestion_tipos_proyecto")

    else:

        formulario = CrearTipoProyectoForm()

    return render(
        request,
        "proyectos/gestion_tipos_proyecto.html",
        {
            "tipos": tipos,
            "formulario": formulario,
        }
    )
    

# ==========================================
# ADMINISTRACIÓN DE ORGANISMOS
# ==========================================

@staff_member_required
def gestion_organismos(request):

    organismos = Organismo.objects.all().order_by("nombre")

    if request.method == "POST":

        formulario = CrearOrganismoForm(request.POST)

        if formulario.is_valid():

            formulario.save()

            return redirect("gestion_organismos")

    else:

        formulario = CrearOrganismoForm()

    return render(
        request,
        "proyectos/gestion_organismos.html",
        {
            "organismos": organismos,
            "formulario": formulario,
        }
    )
    

# ==========================================
# ADMINISTRACIÓN DE TIPOS DE PARTICIPACIÓN
# ==========================================

@staff_member_required
def gestion_tipos_participacion(request):

    tipos = TipoParticipacion.objects.all().order_by("nombre")

    if request.method == "POST":

        formulario = CrearTipoParticipacionForm(request.POST)

        if formulario.is_valid():

            formulario.save()

            return redirect("gestion_tipos_participacion")

    else:

        formulario = CrearTipoParticipacionForm()

    return render(
        request,
        "proyectos/gestion_tipos_participacion.html",
        {
            "tipos": tipos,
            "formulario": formulario,
        }
    )
    

# ==========================================
# ADMINISTRACIÓN DE ÁREAS
# ==========================================

@staff_member_required
def gestion_areas(request):

    areas = Area.objects.all().order_by("nombre")

    if request.method == "POST":

        formulario = CrearAreaForm(request.POST)

        if formulario.is_valid():

            formulario.save()

            return redirect("gestion_areas")

    else:

        formulario = CrearAreaForm()

    return render(
        request,
        "proyectos/gestion_areas.html",
        {
            "areas": areas,
            "formulario": formulario,
        }
    )


# ==========================================
# BÚSQUEDA AVANZADA DE PROYECTOS
# ==========================================

def buscar_proyectos(request):

    formulario = BuscarProyectosForm(request.GET or None)

    proyectos = None

    # Solo buscamos al pulsar el botón Buscar
    if "buscar" in request.GET and formulario.is_valid():

        datos = formulario.cleaned_data

        proyectos = Proyecto.objects.select_related(
            "organismo",
            "tipo_proyecto",
            "tipo_participacion",
            "investigador_principal__usuario"
        ).all()

        # ACRÓNIMO
        if datos.get("usar_acronimo"):
            proyectos = proyectos.filter(
                acronimo__icontains=datos["acronimo"]
            )

        # NOMBRE
        if datos.get("usar_nombre"):
            proyectos = proyectos.filter(
                nombre__icontains=datos["nombre"]
            )

        # ESTADO
        if datos.get("usar_estado"):
            proyectos = proyectos.filter(
                estado__in=datos["estado"]
            )

        # ORGANISMO
        if datos.get("usar_organismo"):
            proyectos = proyectos.filter(
                organismo=datos["organismo"]
            )

        # TIPO DE PROYECTO
        if datos.get("usar_tipo_proyecto"):
            proyectos = proyectos.filter(
                tipo_proyecto=datos["tipo_proyecto"]
            )

        # PARTICIPACIÓN
        if datos.get("usar_participacion"):
            proyectos = proyectos.filter(
                tipo_participacion=datos["participacion"]
            )

        # INVESTIGADOR
        if datos.get("usar_investigador"):

            investigador = datos["investigador"]

            proyectos_asociados = Dedicacion.objects.filter(
                investigador=investigador
            ).values("proyecto_id")

            proyectos = proyectos.filter(
                Q(investigador_principal=investigador)
                | Q(id__in=proyectos_asociados)
            )

        # SOCIO
        if datos.get("usar_socio"):

            proyectos_del_socio = (
                ParticipacionSocio.objects.filter(
                    socio=datos["socio"]
                ).values("proyecto_id")
            )

            proyectos = proyectos.filter(
                id__in=proyectos_del_socio
            )

        # ÁREAS
        if datos.get("usar_areas"):
            proyectos = proyectos.filter(
                areas=datos["areas"]
            )

        proyectos = proyectos.distinct().order_by(
            "acronimo"
        )

    return render(
        request,
        "proyectos/buscar_proyectos.html",
        {
            "formulario": formulario,
            "proyectos": proyectos,
        }
    )
    

# ==========================================
# MIS PROYECTOS
# ==========================================

@login_required
def mis_proyectos(request):

    # Investigador asociado al usuario autenticado
    investigador = Investigador.objects.filter(
        usuario=request.user
    ).first()

    # Filtro: mostrar solo proyectos como responsable
    solo_responsable = (
        request.GET.get("solo_responsable") == "1"
    )

    if investigador is None:

        proyectos = []

    else:

        # Proyectos asociados mediante dedicaciones
        proyectos_asociados = Dedicacion.objects.filter(
            investigador=investigador
        ).values("proyecto_id")

        # Proyectos donde participa o es responsable
        consulta = Proyecto.objects.filter(
            Q(investigador_principal=investigador)
            | Q(id__in=proyectos_asociados)
        )

        if solo_responsable:

            consulta = consulta.filter(
                investigador_principal=investigador
            )

        proyectos = list(
            consulta.select_related(
                "investigador_principal",
                "organismo"
            ).distinct().order_by("acronimo")
        )

        # Identificar si es responsable de cada proyecto
        for proyecto in proyectos:

            proyecto.es_responsable = (
                proyecto.investigador_principal_id
                == investigador.id
            )

    return render(
        request,
        "proyectos/mis_proyectos.html",
        {
            "proyectos": proyectos,
            "investigador": investigador,
            "solo_responsable": solo_responsable,
        }
    )
    

# ==========================================
# ADMINISTRACIÓN DE LÍNEAS DE INVESTIGACIÓN
# ==========================================

@staff_member_required
def gestion_lineas_investigacion(request):

    if request.method == "POST":

        formulario = CrearLineaInvestigacionForm(request.POST)

        if formulario.is_valid():
            formulario.save()

            return redirect("gestion_lineas_investigacion")

    else:
        formulario = CrearLineaInvestigacionForm()

    lineas = list(
        LineaInvestigacion.objects.prefetch_related(
            "asignacion_set"
        ).order_by("nombre")
    )

    # Calcular el presupuesto utilizado y disponible
    for linea in lineas:

        porcentaje_asignado = sum(
            (
                asignacion.porcentaje
                for asignacion in linea.asignacion_set.all()
            ),
            Decimal("0")
        )

        importe_asignado = (
            linea.presupuesto
            * porcentaje_asignado
            / Decimal("100")
        ).quantize(Decimal("0.01"))

        linea.porcentaje_asignado = porcentaje_asignado
        linea.importe_asignado = importe_asignado

        linea.importe_disponible = (
            linea.presupuesto - importe_asignado
        )

    return render(
        request,
        "proyectos/gestion_lineas_investigacion.html",
        {
            "lineas": lineas,
            "formulario": formulario,
        }
    )


# ==========================================
# VALIDAR PRESUPUESTO DISPONIBLE
# ==========================================

def comprobar_presupuesto_linea(
    linea,
    porcentaje,
    excluir_asignacion_id=None
):
    asignaciones = Asignacion.objects.filter(
        linea_investigacion=linea
    )

    # Al editar, descontar la asignación actual
    if excluir_asignacion_id is not None:
        asignaciones = asignaciones.exclude(
            pk=excluir_asignacion_id
        )

    porcentaje_utilizado = (
        asignaciones.aggregate(
            total=Sum("porcentaje")
        )["total"] or Decimal("0")
    )

    porcentaje_disponible = (
        Decimal("100") - porcentaje_utilizado
    )

    return porcentaje <= porcentaje_disponible, porcentaje_disponible


# ==========================================
# FINANCIACIÓN DE UN PROYECTO
# ==========================================

@staff_member_required
def financiacion_proyecto(request, proyecto_id):

    proyecto = get_object_or_404(
        Proyecto,
        pk=proyecto_id
    )

    formulario = AsignacionLineaForm()

    if request.method == "POST":

        accion = request.POST.get("accion")

        # ----------------------------------
        # AÑADIR ASIGNACIÓN
        # ----------------------------------
        if accion == "crear":

            formulario = AsignacionLineaForm(request.POST)

            if formulario.is_valid():

                linea = formulario.cleaned_data[
                    "linea_investigacion"
                ]

                porcentaje = formulario.cleaned_data[
                    "porcentaje"
                ]

                with transaction.atomic():

                    # Bloquea la línea mientras se comprueba
                    # su presupuesto (PostgreSQL).
                    linea = LineaInvestigacion.objects.select_for_update().get(
                        pk=linea.pk
                    )

                    asignacion_existente = Asignacion.objects.filter(
                        proyecto=proyecto,
                        linea_investigacion=linea
                    ).exists()

                    if asignacion_existente:

                        formulario.add_error(
                            "linea_investigacion",
                            "Esta línea ya está asignada al proyecto. "
                            "Puedes modificar su porcentaje en la tabla."
                        )

                    else:

                        permitido, disponible = comprobar_presupuesto_linea(
                            linea,
                            porcentaje
                        )

                        if not permitido:

                            formulario.add_error(
                                "porcentaje",
                                f"Esta línea solo tiene un "
                                f"{disponible}% disponible."
                            )

                        else:

                            Asignacion.objects.create(
                                proyecto=proyecto,
                                linea_investigacion=linea,
                                porcentaje=porcentaje
                            )

                            messages.success(
                                request,
                                "Línea de investigación asignada correctamente."
                            )

                            return redirect(
                                "financiacion_proyecto",
                                proyecto_id=proyecto.id
                            )

        # ----------------------------------
        # MODIFICAR PORCENTAJE
        # ----------------------------------
        elif accion == "editar":

            asignacion = get_object_or_404(
                Asignacion,
                pk=request.POST.get("asignacion_id"),
                proyecto=proyecto
            )

            formulario_edicion = EditarPorcentajeAsignacionForm(
                request.POST
            )

            if formulario_edicion.is_valid():

                nuevo_porcentaje = formulario_edicion.cleaned_data[
                    "porcentaje"
                ]

                with transaction.atomic():

                    linea = LineaInvestigacion.objects.select_for_update().get(
                        pk=asignacion.linea_investigacion_id
                    )

                    asignacion = get_object_or_404(
                        Asignacion,
                        pk=asignacion.pk,
                        proyecto=proyecto
                    )

                    permitido, disponible = comprobar_presupuesto_linea(
                        linea,
                        nuevo_porcentaje,
                        excluir_asignacion_id=asignacion.id
                    )

                    if permitido:

                        asignacion.porcentaje = nuevo_porcentaje
                        asignacion.save(
                            update_fields=["porcentaje"]
                        )

                        messages.success(
                            request,
                            "Asignación actualizada correctamente."
                        )

                    else:

                        messages.error(
                            request,
                            f"No se puede asignar ese porcentaje. "
                            f"El máximo disponible para esta asignación "
                            f"es {disponible}%."
                        )

            else:

                messages.error(
                    request,
                    "Introduce un porcentaje válido entre 0.01 y 100."
                )

            return redirect(
                "financiacion_proyecto",
                proyecto_id=proyecto.id
            )

        # ----------------------------------
        # ELIMINAR ASIGNACIÓN
        # ----------------------------------
        elif accion == "eliminar":

            asignacion = get_object_or_404(
                Asignacion,
                pk=request.POST.get("asignacion_id"),
                proyecto=proyecto
            )

            with transaction.atomic():

                LineaInvestigacion.objects.select_for_update().get(
                    pk=asignacion.linea_investigacion_id
                )

                asignacion.delete()

            messages.success(
                request,
                "Asignación eliminada correctamente."
            )

            return redirect(
                "financiacion_proyecto",
                proyecto_id=proyecto.id
            )

        else:

            messages.error(
                request,
                "Operación no reconocida."
            )

            return redirect(
                "financiacion_proyecto",
                proyecto_id=proyecto.id
            )

    # ----------------------------------
    # LISTADO Y CÁLCULOS
    # ----------------------------------
    asignaciones = list(
        Asignacion.objects.filter(
            proyecto=proyecto
        ).select_related(
            "linea_investigacion"
        ).order_by(
            "linea_investigacion__nombre"
        )
    )

    total_financiacion = Decimal("0.00")

    for asignacion in asignaciones:

        presupuesto = asignacion.linea_investigacion.presupuesto

        asignacion.importe_calculado = (
            presupuesto
            * asignacion.porcentaje
            / Decimal("100")
        ).quantize(Decimal("0.01"))

        total_financiacion += asignacion.importe_calculado

    return render(
        request,
        "proyectos/financiacion_proyecto.html",
        {
            "proyecto": proyecto,
            "asignaciones": asignaciones,
            "total_financiacion": total_financiacion,
            "formulario": formulario,
        }
    )
    

# ==========================================
# ADMINISTRACIÓN - ASIGNACIONES DE UNA LÍNEA
# ==========================================

@staff_member_required
def gestionar_asignaciones_linea(request, linea_id):

    linea = get_object_or_404(
        LineaInvestigacion,
        pk=linea_id
    )

    formulario = AsignacionProyectoForm()

    if request.method == "POST":

        accion = request.POST.get("accion")

        # ----------------------------------
        # CREAR ASIGNACIÓN
        # ----------------------------------
        if accion == "crear":

            formulario = AsignacionProyectoForm(
                request.POST
            )

            if formulario.is_valid():

                proyecto = formulario.cleaned_data["proyecto"]
                porcentaje = formulario.cleaned_data["porcentaje"]

                with transaction.atomic():

                    linea = LineaInvestigacion.objects.select_for_update().get(
                        pk=linea_id
                    )

                    existe = Asignacion.objects.filter(
                        linea_investigacion=linea,
                        proyecto=proyecto
                    ).exists()

                    if existe:

                        formulario.add_error(
                            "proyecto",
                            "Este proyecto ya tiene una asignación "
                            "de esta línea. Modifica la existente."
                        )

                    else:

                        permitido, disponible = comprobar_presupuesto_linea(
                            linea,
                            porcentaje
                        )

                        if not permitido:

                            formulario.add_error(
                                "porcentaje",
                                f"Solo queda disponible el {disponible}% "
                                "del presupuesto de esta línea."
                            )

                        else:

                            Asignacion.objects.create(
                                linea_investigacion=linea,
                                proyecto=proyecto,
                                porcentaje=porcentaje
                            )

                            messages.success(
                                request,
                                "Asignación creada correctamente."
                            )

                            return redirect(
                                "gestionar_asignaciones_linea",
                                linea_id=linea.id
                            )

        # ----------------------------------
        # EDITAR PORCENTAJE
        # ----------------------------------
        elif accion == "editar":

            formulario_edicion = EditarPorcentajeAsignacionForm(
                request.POST
            )

            if formulario_edicion.is_valid():

                porcentaje = formulario_edicion.cleaned_data[
                    "porcentaje"
                ]

                with transaction.atomic():

                    linea = LineaInvestigacion.objects.select_for_update().get(
                        pk=linea_id
                    )

                    asignacion = get_object_or_404(
                        Asignacion,
                        pk=request.POST.get("asignacion_id"),
                        linea_investigacion=linea
                    )

                    permitido, disponible = comprobar_presupuesto_linea(
                        linea,
                        porcentaje,
                        excluir_asignacion_id=asignacion.id
                    )

                    if permitido:

                        asignacion.porcentaje = porcentaje
                        asignacion.save(
                            update_fields=["porcentaje"]
                        )

                        messages.success(
                            request,
                            "Porcentaje actualizado correctamente."
                        )

                    else:

                        messages.error(
                            request,
                            f"No se puede asignar ese porcentaje. "
                            f"El máximo disponible para este proyecto "
                            f"es {disponible}%."
                        )

            else:

                messages.error(
                    request,
                    "Introduce un porcentaje válido entre 0.01 y 100."
                )

            return redirect(
                "gestionar_asignaciones_linea",
                linea_id=linea.id
            )

        # ----------------------------------
        # ELIMINAR ASIGNACIÓN
        # ----------------------------------
        elif accion == "eliminar":

            with transaction.atomic():

                linea = LineaInvestigacion.objects.select_for_update().get(
                    pk=linea_id
                )

                asignacion = get_object_or_404(
                    Asignacion,
                    pk=request.POST.get("asignacion_id"),
                    linea_investigacion=linea
                )

                asignacion.delete()

            messages.success(
                request,
                "Asignación eliminada correctamente."
            )

            return redirect(
                "gestionar_asignaciones_linea",
                linea_id=linea.id
            )

        else:

            messages.error(
                request,
                "Operación no reconocida."
            )

            return redirect(
                "gestionar_asignaciones_linea",
                linea_id=linea.id
            )

    # ----------------------------------
    # CONSULTAR ASIGNACIONES
    # ----------------------------------
    asignaciones = list(
        Asignacion.objects.filter(
            linea_investigacion=linea
        ).select_related(
            "proyecto"
        ).order_by(
            "proyecto__acronimo"
        )
    )

    porcentaje_asignado = Decimal("0")
    importe_asignado = Decimal("0")

    for asignacion in asignaciones:

        asignacion.importe_calculado = (
            linea.presupuesto
            * asignacion.porcentaje
            / Decimal("100")
        ).quantize(Decimal("0.01"))

        porcentaje_asignado += asignacion.porcentaje
        importe_asignado += asignacion.importe_calculado

    porcentaje_disponible = (
        Decimal("100") - porcentaje_asignado
    )

    importe_disponible = (
        linea.presupuesto - importe_asignado
    )

    return render(
        request,
        "proyectos/gestionar_asignaciones_linea.html",
        {
            "linea": linea,
            "formulario": formulario,
            "asignaciones": asignaciones,
            "porcentaje_asignado": porcentaje_asignado,
            "porcentaje_disponible": porcentaje_disponible,
            "importe_asignado": importe_asignado,
            "importe_disponible": importe_disponible,
        }
    )
    


# ==========================================
# LISTADO GENERAL DE PROYECTOS
# ==========================================

@login_required
def listado_proyectos(request):

    proyectos = Proyecto.objects.select_related(
        "organismo",
        "tipo_proyecto"
    )

    # VISIBILIDAD SEGÚN EL USUARIO
    if not request.user.is_staff:

        investigador = Investigador.objects.filter(
            usuario=request.user
        ).first()

        visibles = Q(
            estado__in=["PROCESO", "FINALIZADO"]
        )

        if investigador is not None:

            asociados = Dedicacion.objects.filter(
                investigador=investigador
            ).values("proyecto_id")

            visibles |= Q(
                investigador_principal=investigador
            )

            visibles |= Q(
                pk__in=asociados
            )

        proyectos = proyectos.filter(visibles)

    # BÚSQUEDA
    busqueda = request.GET.get("q", "").strip()

    if busqueda:

        proyectos = proyectos.filter(
            Q(acronimo__icontains=busqueda)
            | Q(nombre__icontains=busqueda)
            | Q(organismo__nombre__icontains=busqueda)
            | Q(tipo_proyecto__nombre__icontains=busqueda)
        )

    # FILTRAR POR ESTADO
    estados = list(
        Proyecto._meta.get_field("estado").choices
    )

    estados_validos = {
        valor for valor, etiqueta in estados
    }

    estado_actual = request.GET.get("estado", "")

    if estado_actual not in estados_validos:
        estado_actual = ""

    if estado_actual:

        proyectos = proyectos.filter(
            estado=estado_actual
        )

    # ORDENAR
    proyectos = proyectos.order_by(
        Lower("acronimo"),
        "pk"
    )

    # PAGINACIÓN
    paginador = Paginator(proyectos, 15)

    pagina = paginador.get_page(
        request.GET.get("pagina")
    )

    hoy = timezone.localdate()

    # ==========================================
    # CALCULAR TIEMPO Y HORAS
    # SOLO PARA PROYECTOS EN PROCESO
    # ==========================================

    for proyecto in pagina.object_list:

        proyecto.porcentaje_tiempo = None
        proyecto.porcentaje_trabajo = None

        if proyecto.estado != "PROCESO":
            continue

        # ----------------------------------
        # PORCENTAJE DE TIEMPO
        # ----------------------------------
        porcentaje_tiempo = 0

        if proyecto.fecha_inicio and proyecto.fecha_fin:

            inicio = proyecto.fecha_inicio
            fin = proyecto.fecha_fin

            dias_totales = (fin - inicio).days
            dias_transcurridos = (hoy - inicio).days

            if dias_totales > 0:

                porcentaje_tiempo = (
                    dias_transcurridos / dias_totales
                ) * 100

            elif hoy >= fin:

                porcentaje_tiempo = 100

        proyecto.porcentaje_tiempo = max(
            0,
            min(100, round(porcentaje_tiempo))
        )

        # ----------------------------------
        # PORCENTAJE DE HORAS TRABAJADAS
        # ----------------------------------
        horas_previstas = (
            Tarea.objects.filter(
                proyecto=proyecto
            ).aggregate(
                total=Sum("horas_estimadas")
            )["total"] or 0
        )

        horas_realizadas = (
            RegistroHoras.objects.filter(
                tarea__proyecto=proyecto
            ).aggregate(
                total=Sum("horas")
            )["total"] or 0
        )

        if horas_previstas > 0:

            porcentaje_trabajo = (
                horas_realizadas / horas_previstas
            ) * 100

            proyecto.porcentaje_trabajo = max(
                0,
                min(100, round(porcentaje_trabajo))
            )

    return render(
        request,
        "proyectos/listado_proyectos.html",
        {
            "proyectos": pagina.object_list,
            "pagina": pagina,
            "total_resultados": paginador.count,
            "busqueda": busqueda,
            "estado_actual": estado_actual,
            "estados": estados,
        }
    )
    

# ==========================================
# CALENDARIO LABORAL
# ==========================================

@login_required
def calendario_laboral(request):

    anio_actual = timezone.localdate().year

    try:
        anio = int(request.GET.get("anio", anio_actual))
    except (TypeError, ValueError):
        anio = anio_actual

    if not 2000 <= anio <= 2100:
        anio = anio_actual

    festivos = Festivo.objects.filter(
        fecha__year=anio
    ).order_by("-fecha")

    anios_disponibles = list(
        range(anio_actual - 1, anio_actual + 2)
    )

    if anio not in anios_disponibles:
        anios_disponibles.append(anio)
        anios_disponibles.sort()

    return render(
        request,
        "proyectos/calendario_laboral.html",
        {
            "festivos": festivos,
            "anio": anio,
            "anios_disponibles": anios_disponibles,
        }
    )


# ==========================================
# CREAR FESTIVO
# ==========================================

@staff_member_required
def crear_festivo(request):

    formulario = FestivoForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():

        festivo = formulario.save(commit=False)

        festivo.importado = False
        festivo.editado_manualmente = True

        festivo.save()

        messages.success(
            request,
            "Festivo creado correctamente."
        )

        return redirect(
            f"{reverse('calendario_laboral')}?anio={festivo.fecha.year}"
        )

    return render(
        request,
        "proyectos/formulario_festivo.html",
        {
            "formulario": formulario,
            "titulo": "Añadir festivo",
        }
    )


# ==========================================
# EDITAR FESTIVO
# ==========================================

@staff_member_required
def editar_festivo(request, pk):

    festivo = get_object_or_404(Festivo, pk=pk)

    formulario = FestivoForm(
        request.POST or None,
        instance=festivo
    )

    if request.method == "POST" and formulario.is_valid():

        festivo = formulario.save(commit=False)

        # Proteger los cambios manuales frente
        # a posteriores importaciones.

        festivo.editado_manualmente = True
        festivo.save()

        messages.success(
            request,
            "Festivo actualizado correctamente."
        )

        return redirect(
            f"{reverse('calendario_laboral')}?anio={festivo.fecha.year}"
        )

    return render(
        request,
        "proyectos/formulario_festivo.html",
        {
            "formulario": formulario,
            "titulo": "Editar festivo",
        }
    )


# ==========================================
# ELIMINAR FESTIVO
# ==========================================

@staff_member_required
@require_POST
def eliminar_festivo(request, pk):

    festivo = get_object_or_404(Festivo, pk=pk)

    anio = festivo.fecha.year

    festivo.delete()

    messages.success(
        request,
        "Festivo eliminado correctamente."
    )

    return redirect(
        f"{reverse('calendario_laboral')}?anio={anio}"
    )


# ==========================================
# EXTRAER FESTIVOS DEL JSON
# ==========================================

def extraer_festivos_api(datos, anio):

    """
    Localiza los registros de festivos en la
    respuesta JSON y valida sus campos.
    """

    registros = []

    def recorrer(elemento, profundidad=0):

        if profundidad > 8:
            return

        if isinstance(elemento, list):

            for item in elemento[:2000]:
                recorrer(item, profundidad + 1)

        elif isinstance(elemento, dict):

            if "date" in elemento and "name" in elemento:
                registros.append(elemento)
                return

            for valor in elemento.values():

                if isinstance(valor, (list, dict)):
                    recorrer(valor, profundidad + 1)

    recorrer(datos)

    ambitos = {
        "nacional": "nacional",
        "autonomico": "autonomico",
        "autonómico": "autonomico",
        "provincial": "provincial",
        "local": "local",
    }

    festivos = {}

    for registro in registros:

        try:
            fecha = date.fromisoformat(
                str(registro["date"])
            )
        except (ValueError, TypeError):
            continue

        if fecha.year != anio:
            continue

        nombre = str(
            registro.get("name") or ""
        ).strip()

        ambito = ambitos.get(
            str(registro.get("scope") or "").lower().strip()
        )

        if not nombre or not ambito:
            continue

        fuente = str(
            registro.get("source") or "Calendarios Nacionales"
        )[:200]

        url_fuente = str(
            registro.get("sourceUrl") or ""
        ).strip()

        # Solo permitir enlaces HTTP/HTTPS válidos.

        url_analizada = urlparse(url_fuente)

        if (
            url_analizada.scheme not in ("http", "https")
            or not url_analizada.netloc
        ):
            url_fuente = ""

        festivos[fecha] = {
            "fecha": fecha,
            "nombre": nombre[:200],
            "ambito": ambito,
            "fuente": fuente,
            "url_fuente": url_fuente[:500],
        }

    return list(festivos.values())


# ==========================================
# IMPORTAR CALENDARIO OFICIAL
# ==========================================

@staff_member_required
@require_POST
def importar_calendario_laboral(request):

    try:
        anio = int(request.POST.get("anio", ""))
    except (TypeError, ValueError):
        messages.error(
            request,
            "El año seleccionado no es válido."
        )
        return redirect("calendario_laboral")

    if not 2025 <= anio <= 2100:
        messages.error(
            request,
            "El año seleccionado no es válido."
        )
        return redirect("calendario_laboral")

    # Endpoint documentado para Santiago de Compostela.
    # Si cambia la estructura de la API,
    # habrá que actualizar esta URL.

    url = (
        "https://calendariosnacionales.com"
        f"/es/v1/{anio}/localidades/"
        "gal/a-coruna/santiago-de-compostela.json"
    )

    try:

        peticion = Request(
            url,
            headers={
                "User-Agent": "Gesproy/1.0",
                "Accept": "application/json",
            }
        )

        with urlopen(peticion, timeout=12) as respuesta:

            contenido = respuesta.read(2_000_001)

            if len(contenido) > 2_000_000:
                raise ValueError(
                    "La respuesta supera el tamaño permitido."
                )

        datos = json.loads(contenido.decode("utf-8"))

        festivos = extraer_festivos_api(datos, anio)

        if not festivos:
            raise ValueError(
                "La API no ha devuelto festivos válidos "
                "para el año seleccionado."
            )

    except (URLError, TimeoutError, ValueError) as error:

        messages.error(
            request,
            f"No se pudo importar el calendario: {error}"
        )

        return redirect(
            f"{reverse('calendario_laboral')}?anio={anio}"
        )

    creados = 0
    actualizados = 0
    conservados = 0

    with transaction.atomic():

        for datos_festivo in festivos:

            festivo_existente = Festivo.objects.filter(
                fecha=datos_festivo["fecha"]
            ).first()

            if festivo_existente is None:

                Festivo.objects.create(
                    **datos_festivo,
                    importado=True,
                    editado_manualmente=False
                )

                creados += 1
                continue

            # No sobrescribir festivos propios del centro
            # ni registros modificados por un administrador.

            if (
                not festivo_existente.importado
                or festivo_existente.editado_manualmente
            ):
                conservados += 1
                continue

            festivo_existente.nombre = datos_festivo["nombre"]
            festivo_existente.ambito = datos_festivo["ambito"]
            festivo_existente.fuente = datos_festivo["fuente"]
            festivo_existente.url_fuente = datos_festivo["url_fuente"]

            festivo_existente.save(
                update_fields=[
                    "nombre",
                    "ambito",
                    "fuente",
                    "url_fuente"
                ]
            )

            actualizados += 1

    messages.success(
        request,
        (
            f"Importación completada: "
            f"{creados} nuevos, "
            f"{actualizados} actualizados "
            f"y {conservados} cambios manuales conservados."
        )
    )

    return redirect(
        f"{reverse('calendario_laboral')}?anio={anio}"
    )








    













