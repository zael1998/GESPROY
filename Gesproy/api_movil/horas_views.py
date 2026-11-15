import json
import re

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from usuarios.models import Investigador
from horas.models import Tarea, RegistroHoras

from horas.calendario import (
    ImputarHorasForm,
    proyectos_del_investigador,
)

from horas.capacidad import (
    capacidad_mensual,
    control_activo,
)

from .views import proyectos_del_investigador as proyectos_asociados


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================


def comprobar_usuario(request):

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Debes iniciar sesión."},
            status=401,
        )

    return None


def obtener_investigador(request):

    return Investigador.objects.filter(usuario=request.user).first()


# ==========================================
# TAREAS DE UN PROYECTO
# ==========================================


@require_GET
def tareas_proyecto(request, proyecto_id):

    error = comprobar_usuario(request)

    if error is not None:
        return error

    proyectos, investigador = proyectos_asociados(request.user)

    proyecto = get_object_or_404(
        proyectos,
        pk=proyecto_id,
    )

    tareas = Tarea.objects.filter(proyecto=proyecto).order_by(
        "fecha_inicio",
        "pk",
    )

    resultado = []

    for tarea in tareas:
        resultado.append(
            {
                "id": tarea.pk,
                "nombre": tarea.nombre,
                "descripcion": tarea.descripcion,
                "tarea_padre_id": tarea.tarea_padre_id,
                "finalizada": tarea.finalizada,
                "fecha_inicio": (
                    tarea.fecha_inicio.isoformat() if tarea.fecha_inicio else None
                ),
                "fecha_fin": (tarea.fecha_fin.isoformat() if tarea.fecha_fin else None),
                "horas_estimadas": str(tarea.horas_estimadas),
                "puede_imputar": (
                    proyecto.estado == "PROCESO"
                    and not tarea.finalizada
                    and investigador is not None
                ),
            }
        )

    return JsonResponse(
        {
            "proyecto": {
                "id": proyecto.pk,
                "nombre": proyecto.nombre,
                "acronimo": proyecto.acronimo,
                "estado": proyecto.estado,
            },
            "tareas": resultado,
        }
    )


# ==========================================
# REGISTRAR HORAS INDIVIDUALES
# ==========================================


@require_POST
@csrf_protect
def registrar_horas(request):

    error = comprobar_usuario(request)

    if error is not None:
        return error

    investigador = obtener_investigador(request)

    if investigador is None:
        return JsonResponse(
            {"error": "No tienes perfil de investigador."},
            status=403,
        )

    # Leer los datos enviados desde React.

    try:
        datos = json.loads(request.body.decode("utf-8"))

    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "El JSON no es válido."},
            status=400,
        )

    if not isinstance(datos, dict):
        return JsonResponse(
            {"error": "Los datos enviados no son válidos."},
            status=400,
        )

    # ======================================
    # VALIDAR FECHA
    # ======================================

    fecha_texto = datos.get("fecha")

    if not isinstance(fecha_texto, str):
        return JsonResponse(
            {"error": "Debes seleccionar una fecha."},
            status=400,
        )

    try:
        fecha = date.fromisoformat(fecha_texto)

    except ValueError:
        return JsonResponse(
            {"error": "La fecha no es válida."},
            status=400,
        )

    if fecha.isoformat() != fecha_texto:
        return JsonResponse(
            {"error": "La fecha debe tener formato AAAA-MM-DD."},
            status=400,
        )

    # ======================================
    # PROYECTOS DEL INVESTIGADOR
    # ======================================

    proyectos = proyectos_del_investigador(investigador)

    # Reutilizamos el formulario del calendario
    # de Gesproy Web.

    datos_formulario = {
        "proyecto": datos.get("proyecto", ""),
        "tarea": datos.get("tarea", ""),
        "horas": datos.get("horas", ""),
        "descripcion": datos.get("descripcion", ""),
        "fechas": json.dumps([fecha_texto]),
    }

    # ======================================
    # GUARDAR REGISTRO
    # ======================================

    try:
        with transaction.atomic():
            Investigador.objects.select_for_update().get(pk=investigador.pk)

            formulario = ImputarHorasForm(
                datos_formulario,
                investigador=investigador,
                proyectos=proyectos,
                mes=fecha.replace(day=1),
            )

            if not formulario.is_valid():
                return JsonResponse(
                    {
                        "error": "Comprueba los datos del registro.",
                        "campos": formulario.errors.get_json_data(),
                    },
                    status=400,
                )

            valores = formulario.cleaned_data

            registro = RegistroHoras.objects.create(
                investigador=investigador,
                tarea=valores["tarea"],
                fecha=fecha,
                horas=valores["horas"],
                descripcion=valores["descripcion"],
            )

    except ValidationError as excepcion:
        return JsonResponse(
            {"error": "; ".join(excepcion.messages)},
            status=400,
        )

    # ======================================
    # AVISO DE JORNADA
    # ======================================

    aviso = None

    if formulario.excesos_jornada:
        aviso = (
            "Las horas se han guardado, pero has "
            "superado la jornada orientativa del día."
        )

    return JsonResponse(
        {
            "mensaje": "Horas registradas correctamente.",
            "registro_id": registro.pk,
            "aviso": aviso,
        },
        status=201,
    )


# ==========================================
# HISTORIAL DE HORAS
# ==========================================


@require_GET
def mis_horas(request):

    error = comprobar_usuario(request)

    if error is not None:
        return error

    # ======================================
    # VALIDAR MES
    # ======================================

    mes = request.GET.get(
        "mes",
        timezone.localdate().strftime("%Y-%m"),
    )

    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
        return JsonResponse(
            {"error": "Mes no válido."},
            status=400,
        )

    anio, numero_mes = map(int, mes.split("-"))

    if not 2000 <= anio <= 2099:
        return JsonResponse(
            {"error": "Año no válido."},
            status=400,
        )

    # ======================================
    # OBTENER INVESTIGADOR
    # ======================================

    investigador = obtener_investigador(request)

    if investigador is None:
        return JsonResponse(
            {
                "mes": mes,
                "registros": [],
                "total_horas": "0.00",
                "capacidad_mensual": None,
                "horas_disponibles": None,
                "control_mensual_activo": False,
                "aviso_capacidad": ("No tienes perfil de investigador."),
            }
        )

    # ======================================
    # CONSULTAR REGISTROS
    # ======================================

    registros = list(
        RegistroHoras.objects.filter(
            investigador=investigador,
            fecha__year=anio,
            fecha__month=numero_mes,
        )
        .select_related("tarea__proyecto")
        .order_by(
            "-fecha",
            "-pk",
        )
    )

    resultado = []

    for registro in registros:
        fecha_fin = getattr(
            registro,
            "fecha_fin",
            None,
        )

        resultado.append(
            {
                "id": registro.pk,
                "fecha": registro.fecha.isoformat(),
                "fecha_fin": (fecha_fin.isoformat() if fecha_fin else None),
                "horas": str(registro.horas),
                "descripcion": registro.descripcion,
                "validado": registro.validado,
                "tarea": {
                    "id": registro.tarea.pk,
                    "nombre": registro.tarea.nombre,
                },
                "proyecto": {
                    "id": registro.tarea.proyecto.pk,
                    "acronimo": registro.tarea.proyecto.acronimo,
                },
            }
        )

    # ======================================
    # TOTAL DE HORAS REGISTRADAS
    # ======================================

    total = sum(
        (registro.horas for registro in registros),
        Decimal("0.00"),
    )

    # ======================================
    # CAPACIDAD MENSUAL
    # ======================================

    capacidad = capacidad_mensual(
        anio,
        numero_mes,
    )

    disponibles = max(
        Decimal("0.00"),
        capacidad - total,
    )

    # ======================================
    # AVISO DE CAPACIDAD
    # ======================================

    if total > capacidad:
        aviso_capacidad = "Has superado la capacidad mensual orientativa."

    else:
        aviso_capacidad = "Capacidad orientativa sin descontar vacaciones ni ausencias."

    # ======================================
    # RESPUESTA JSON
    # ======================================

    return JsonResponse(
        {
            "mes": mes,
            "total_horas": str(total),
            "capacidad_mensual": str(capacidad),
            "horas_disponibles": str(disponibles),
            "control_mensual_activo": control_activo(),
            "aviso_capacidad": aviso_capacidad,
            "registros": resultado,
        }
    )
