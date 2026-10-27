import json

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from horas.models import (
    RegistroHoras,
    CierreMensualHoras,
    HistorialValidacionHoras,
)
from usuarios.models import Investigador


# ==========================================
# FORMULARIO DE EDICIÓN
# ==========================================

class EditarHorasAPIForm(forms.Form):

    horas = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_value=Decimal("24"),
        max_digits=5,
        decimal_places=2,
    )

    descripcion = forms.CharField(
        required=False,
    )


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def buscar_registro(usuario, registro_id, bloqueo=False):

    consulta = RegistroHoras.objects.filter(
        investigador__usuario=usuario
    ).select_related(
        "tarea__proyecto"
    )

    if bloqueo:
        consulta = consulta.select_for_update()

    return consulta.filter(
        pk=registro_id
    ).first()


def motivo_bloqueo(registro, eliminar=False):

    if registro.validado:
        return (
            "Este registro ya está validado. "
            "Solicita su reapertura."
        )

    proyecto = registro.tarea.proyecto

    if proyecto.estado != "PROCESO":
        return (
            "Solo puedes modificar registros "
            "de proyectos en proceso."
        )

    mes_cerrado = CierreMensualHoras.objects.filter(
        investigador_id=registro.investigador_id,
        proyecto_id=proyecto.pk,
        anio=registro.fecha.year,
        mes=registro.fecha.month,
    ).exists()

    if mes_cerrado:
        return (
            "Este mes está cerrado. "
            "Solicita su reapertura."
        )

    if eliminar:

        tiene_historial = (
            HistorialValidacionHoras.objects.filter(
                registro=registro
            ).exists()
        )

        if tiene_historial:
            return (
                "Este registro conserva historial de "
                "validación y no puede eliminarse."
            )

    return None


def datos_registro(registro):

    return {
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
    }


# ==========================================
# CONSULTAR, EDITAR O ELIMINAR
# ==========================================

@require_http_methods(["GET", "PATCH", "DELETE"])
@csrf_protect
def gestionar_registro(request, registro_id):

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Debes iniciar sesión."},
            status=401,
        )

    # ======================================
    # CONSULTAR REGISTRO
    # ======================================

    if request.method == "GET":

        registro = buscar_registro(
            request.user,
            registro_id,
        )

        if registro is None:
            return JsonResponse(
                {"error": "Registro no encontrado."},
                status=404,
            )

        puede_editar = motivo_bloqueo(registro) is None

        puede_eliminar = (
            motivo_bloqueo(registro, eliminar=True)
            is None
        )

        return JsonResponse({
            "registro": datos_registro(registro),
            "puede_editar": puede_editar,
            "puede_eliminar": puede_eliminar,
        })

    # ======================================
    # EDITAR O ELIMINAR
    # ======================================

    with transaction.atomic():

        investigador = Investigador.objects.select_for_update().filter(
            usuario=request.user
        ).first()

        if investigador is None:
            return JsonResponse(
                {"error": "No tienes perfil de investigador."},
                status=403,
            )

        registro = buscar_registro(
            request.user,
            registro_id,
            bloqueo=True,
        )

        if registro is None:
            return JsonResponse(
                {"error": "Registro no encontrado."},
                status=404,
            )

        eliminar = request.method == "DELETE"

        bloqueo = motivo_bloqueo(
            registro,
            eliminar=eliminar,
        )

        if bloqueo is not None:
            return JsonResponse(
                {"error": bloqueo},
                status=403,
            )

        # ==================================
        # ELIMINAR
        # ==================================

        if eliminar:

            try:
                registro.delete()

            except ValidationError as error:
                return JsonResponse(
                    {
                        "error": "; ".join(error.messages)
                    },
                    status=400,
                )

            return JsonResponse({
                "mensaje": "Registro eliminado correctamente."
            })

        # ==================================
        # EDITAR
        # ==================================

        try:
            datos = json.loads(
                request.body.decode("utf-8")
            )

        except (ValueError, UnicodeDecodeError):
            return JsonResponse(
                {"error": "El JSON enviado no es válido."},
                status=400,
            )

        if not isinstance(datos, dict):
            return JsonResponse(
                {"error": "Los datos no son válidos."},
                status=400,
            )

        formulario = EditarHorasAPIForm(datos)

        if not formulario.is_valid():
            return JsonResponse(
                {
                    "error": "Revisa los datos.",
                    "campos": formulario.errors.get_json_data(),
                },
                status=400,
            )

        nuevas_horas = formulario.cleaned_data["horas"]

        # Sumamos todas las horas de ese día,
        # excluyendo el registro que estamos editando.

        otras_horas = RegistroHoras.objects.filter(
            investigador=investigador,
            fecha=registro.fecha,
        ).exclude(
            pk=registro.pk
        ).aggregate(
            total=Sum("horas")
        )["total"] or Decimal("0.00")

        total_dia = otras_horas + nuevas_horas

        if total_dia > Decimal("24.00"):
            return JsonResponse(
                {
                    "error": (
                        "La suma de horas del día supera "
                        "el límite de 24 horas."
                    )
                },
                status=400,
            )

        registro.horas = nuevas_horas
        registro.descripcion = (
            formulario.cleaned_data["descripcion"]
        )

        try:
            registro.save(
                update_fields=[
                    "horas",
                    "descripcion",
                ]
            )

        except ValidationError as error:
            return JsonResponse(
                {
                    "error": "; ".join(error.messages)
                },
                status=400,
            )

        return JsonResponse({
            "mensaje": "Registro actualizado correctamente.",
            "registro": datos_registro(registro),
        })