import calendar

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.core.exceptions import ValidationError

from proyectos.models import Festivo


def capacidad_mensual(anio, mes):

    horas_dia = Decimal(str(getattr(settings, "GESPROY_HORAS_JORNADA", "8.00")))

    if horas_dia <= 0:
        raise ValueError("GESPROY_HORAS_JORNADA debe ser positiva.")

    festivos = set(
        Festivo.objects.filter(
            fecha__year=anio,
            fecha__month=mes,
        ).values_list("fecha", flat=True)
    )

    dias_laborables = sum(
        1
        for dia in range(1, calendar.monthrange(anio, mes)[1] + 1)
        if (fecha := date(anio, mes, dia)).weekday() < 5 and fecha not in festivos
    )

    return Decimal(dias_laborables) * horas_dia


def total_mes(investigador_id, anio, mes, excluir_pk=None):

    from .models import RegistroHoras

    registros = RegistroHoras.objects.filter(
        investigador_id=investigador_id,
        fecha__year=anio,
        fecha__month=mes,
    )

    if excluir_pk is not None:
        registros = registros.exclude(pk=excluir_pk)

    return registros.aggregate(total=Sum("horas"))["total"] or Decimal("0.00")


def control_activo():

    return bool(getattr(settings, "GESPROY_CONTROL_MENSUAL_ACTIVO", False))


def verificar_total_mensual(
    investigador_id,
    anio,
    mes,
    nuevas_horas,
    excluir_pk=None,
):

    if not control_activo():
        return

    capacidad = capacidad_mensual(anio, mes)

    total = (
        total_mes(
            investigador_id,
            anio,
            mes,
            excluir_pk,
        )
        + nuevas_horas
    )

    if total > capacidad:
        raise ValidationError(
            f"El total mensual ({total} h) supera "
            f"la capacidad orientativa ({capacidad} h)."
        )
