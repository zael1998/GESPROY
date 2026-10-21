"""Corrección segura de registros de horas propios pendientes.

No modifica los flujos de validación de horas ni las vistas de tareas.
"""

from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .calendario import JORNADA_ORIENTATIVA_HORAS
from .models import CierreMensualHoras, RegistroHoras, MAX_HORAS_DIA


class EditarRegistroForm(forms.Form):
    horas = forms.DecimalField(
        label="Horas trabajadas",
        min_value=Decimal("0.01"),
        max_value=MAX_HORAS_DIA,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "mr-input", "step": "0.25", "min": "0.01", "max": "24",
            "autocomplete": "off",
        }),
    )
    descripcion = forms.CharField(
        label="Descripción del trabajo",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "mr-input", "rows": 4,
            "placeholder": "Describe el trabajo realizado (opcional)",
        }),
    )


def _registro_propio(usuario, registro_id, bloqueo=False):
    """El ID de URL nunca concede acceso a registros de otra persona."""
    consulta = RegistroHoras.objects.select_related(
        "investigador__usuario", "tarea__proyecto"
    ).filter(investigador__usuario=usuario)
    if bloqueo:
        consulta = consulta.select_for_update()
    return get_object_or_404(consulta, pk=registro_id)


def _comprobar_editable(registro, *, eliminar=False):
    if registro.validado:
        raise PermissionDenied(
            "Estas horas están validadas. Solicita su reapertura al administrador."
        )
    if registro.tarea.proyecto.estado != "PROCESO":
        raise PermissionDenied(
            "Solo se pueden corregir horas de proyectos en proceso."
        )
    if CierreMensualHoras.objects.filter(
        investigador_id=registro.investigador_id,
        proyecto_id=registro.tarea.proyecto_id,
        anio=registro.fecha.year,
        mes=registro.fecha.month,
    ).exists():
        raise PermissionDenied(
            "El mes de este proyecto está cerrado. Solicita su reapertura."
        )
    if eliminar and registro.historial_validaciones.exists():
        raise PermissionDenied(
            "Este registro se validó anteriormente y conserva historial "
            "de auditoría. Puedes editarlo tras su reapertura, pero no borrarlo."
        )


def _volver_al_mes(registro):
    return f"{reverse('horas:mis_horas')}?mes={registro.fecha:%Y-%m}"


@login_required
def editar_registro(request, registro_id):
    registro = _registro_propio(request.user, registro_id)
    _comprobar_editable(registro)

    if request.method == "POST":
        formulario = EditarRegistroForm(request.POST)
        if formulario.is_valid():
            # Volvemos a comprobarlo con bloqueo justo antes de guardar,
            # por si el validador aprobó el registro mientras se editaba.
            with transaction.atomic():
                registro = _registro_propio(request.user, registro_id, bloqueo=True)
                _comprobar_editable(registro)
                registro.horas = formulario.cleaned_data["horas"]
                registro.descripcion = formulario.cleaned_data["descripcion"]
                try:
                    registro.save(update_fields=["horas", "descripcion"])
                except ValidationError as error:
                    formulario.add_error(None, error)
                else:
                    total_dia = RegistroHoras.objects.filter(
                        investigador_id=registro.investigador_id,
                        fecha=registro.fecha,
                    ).aggregate(total=Sum("horas"))["total"] or Decimal("0.00")
                    messages.success(request, "Registro de horas actualizado.")
                    if total_dia > JORNADA_ORIENTATIVA_HORAS:
                        messages.warning(
                            request,
                            f"Atención: el {registro.fecha:%d/%m/%Y} acumulas "
                            f"{total_dia} horas entre todos tus proyectos.",
                        )
                    return redirect(_volver_al_mes(registro))
    else:
        formulario = EditarRegistroForm(initial={
            "horas": registro.horas,
            "descripcion": registro.descripcion,
        })

    return render(request, "horas/editar_registro.html", {
        "registro": registro,
        "formulario": formulario,
        "jornada_orientativa": JORNADA_ORIENTATIVA_HORAS,
        "max_horas": MAX_HORAS_DIA,
    })


@login_required
def eliminar_registro(request, registro_id):
    registro = _registro_propio(request.user, registro_id)
    _comprobar_editable(registro, eliminar=True)

    if request.method == "POST":
        with transaction.atomic():
            registro = _registro_propio(request.user, registro_id, bloqueo=True)
            _comprobar_editable(registro, eliminar=True)
            volver = _volver_al_mes(registro)
            try:
                registro.delete()
            except ValidationError as error:
                messages.error(request, "; ".join(error.messages))
            else:
                messages.success(request, "Registro de horas eliminado.")
            return redirect(volver)

    return render(request, "horas/eliminar_registro.html", {
        "registro": registro,
    })