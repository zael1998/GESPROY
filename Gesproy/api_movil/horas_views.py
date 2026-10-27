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

    return Investigador.objects.filter(
        usuario=request.user
    ).first()


# ==========================================
# TAREAS DE UN PROYECTO
# ==========================================

@require_GET
def tareas_proyecto(request, proyecto_id):

    error = comprobar_usuario(request)

    if error is not None:
        return error

    proyectos, investigador = proyectos_asociados(
        request.user
    )

    proyecto = get_object_or_404(
        proyectos,
        pk=proyecto_id,
    )

    tareas = Tarea.objects.filter(
        proyecto=proyecto
    ).order_by(
        "fecha_inicio",
        "pk",
    )

    resultado = []

    for tarea in tareas:

        resultado.append({
            "id": tarea.pk,
            "nombre": tarea.nombre,
            "descripcion": tarea.descripcion,
            "tarea_padre_id": tarea.tarea_padre_id,
            "finalizada": tarea.finalizada,
            "fecha_inicio": tarea.fecha_inicio.isoformat(),
            "fecha_fin": (
                tarea.fecha_fin.isoformat()
                if tarea.fecha_fin
                else None
            ),
            "horas_estimadas": str(tarea.horas_estimadas),
            "puede_imputar": (
                proyecto.estado == "PROCESO"
                and not tarea.finalizada
                and investigador is not None
            ),
        })

    return JsonResponse({
        "proyecto": {
            "id": proyecto.pk,
            "nombre": proyecto.nombre,
            "acronimo": proyecto.acronimo,
            "estado": proyecto.estado,
        },
        "tareas": resultado,
    })


# ==========================================
# REGISTRAR HORAS
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

    try:
        datos = json.loads(
            request.body.decode("utf-8")
        )
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

    proyectos = proyectos_del_investigador(
        investigador
    )

    # Reutilizamos el formulario real del calendario
    # de Gesproy. Acepta una lista de fechas.
    # La app móvil registra una fecha por petición.

    datos_formulario = {
        "proyecto": datos.get("proyecto", ""),
        "tarea": datos.get("tarea", ""),
        "horas": datos.get("horas", ""),
        "descripcion": datos.get("descripcion", ""),
        "fechas": json.dumps([fecha_texto]),
    }

    try:

        with transaction.atomic():

            # Mismo bloqueo utilizado en el calendario
            # para proteger las imputaciones concurrentes.
            Investigador.objects.select_for_update().get(
                pk=investigador.pk
            )

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
            {
                "error": "; ".join(excepcion.messages)
            },
            status=400,
        )

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

    investigador = obtener_investigador(request)

    if investigador is None:
        return JsonResponse(
            {
                "registros": [],
                "total_horas": "0.00",
            }
        )

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

    registros = list(
        RegistroHoras.objects.filter(
            investigador=investigador,
            fecha__year=anio,
            fecha__month=numero_mes,
        )
        .select_related(
            "tarea__proyecto"
        )
        .order_by("-fecha", "-pk")
    )

    resultado = []

    for registro in registros:

        resultado.append({
            "id": registro.pk,
            "fecha": registro.fecha.isoformat(),
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
        })

    total = sum(
        (registro.horas for registro in registros),
        Decimal("0.00"),
    )

    return JsonResponse({
        "mes": mes,
        "total_horas": str(total),
        "registros": resultado,
    })