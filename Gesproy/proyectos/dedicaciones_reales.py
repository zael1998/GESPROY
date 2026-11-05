"""Dedicación real mensual, sin distribuir las horas de los periodos."""
from decimal import Decimal
from django.db.models import Sum
from horas.models import RegistroHoras
from horas.control_mensual import capacidad_mensual

DOS_DECIMALES = Decimal("0.01")


def dedicacion_real_mensual(*, investigador_id, proyecto_id, anio, mes, capacidad=None):
    """Obtiene todas las horas del mes, incluidas las imputaciones por periodo.

    Los periodos registrados no cruzan meses en Gesproy, por lo que cada
    registro se puede atribuir íntegramente al mes de su fecha inicial.
    La capacidad es teórica; no descuenta ausencias ni jornadas individuales.
    """
    horas = (
        RegistroHoras.objects.filter(
            investigador_id=investigador_id,
            tarea__proyecto_id=proyecto_id,
            fecha__year=anio,
            fecha__month=mes,
        ).aggregate(total=Sum("horas"))["total"] or Decimal("0.00")
    )
    if capacidad is None:
        capacidad = capacidad_mensual(anio, mes)

    porcentaje = (
        ((horas * Decimal("100")) / capacidad).quantize(DOS_DECIMALES)
        if capacidad > 0 else None
    )
    return {
        "anio": anio,
        "mes": mes,
        "horas_proyecto": horas,
        "capacidad_teorica": capacidad,
        "porcentaje_real_orientativo": porcentaje,
        "aviso": "Capacidad orientativa: sin vacaciones, ausencias ni jornadas individuales.",
    }