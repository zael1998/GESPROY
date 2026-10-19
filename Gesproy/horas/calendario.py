
import calendar
import json

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from proyectos.models import Proyecto, Dedicacion, Festivo
from usuarios.models import Investigador

from .models import Tarea, RegistroHoras


# ==========================================
# FORMULARIO DE IMPUTACIÓN MÚLTIPLE
# ==========================================

class ImputarHorasForm(forms.Form):

    proyecto = forms.ModelChoiceField(
        queryset=Proyecto.objects.none(),
        label="Proyecto",
        empty_label="Seleccionar proyecto",
        widget=forms.Select(attrs={"class": "mh-input"})
    )

    tarea = forms.ModelChoiceField(
        queryset=Tarea.objects.none(),
        label="Tarea",
        empty_label="Seleccionar tarea",
        widget=forms.Select(attrs={"class": "mh-input"})
    )

    horas = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("24.00"),
        label="Horas por día",
        widget=forms.NumberInput(
            attrs={
                "class": "mh-input",
                "step": "0.25",
                "min": "0.01",
                "max": "24",
                "placeholder": "Ej. 2",
            }
        )
    )

    descripcion = forms.CharField(
        required=False,
        label="Descripción",
        widget=forms.Textarea(
            attrs={
                "class": "mh-input",
                "rows": 3,
                "placeholder": "¿Qué trabajo realizaste? (opcional)",
            }
        )
    )

    fechas = forms.CharField(
        widget=forms.HiddenInput()
    )

    def __init__(
        self,
        *args,
        investigador,
        proyectos,
        mes,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.investigador = investigador
        self.mes = mes

        self.fields["proyecto"].queryset = proyectos

        if self.is_bound:
            proyecto_id = self.data.get("proyecto")
        else:
            proyecto_id = self.initial.get("proyecto")

        # Solo permitir tareas de proyectos
        # en los que participa el investigador.

        try:
            proyecto_id = int(proyecto_id)
        except (TypeError, ValueError):
            proyecto_id = None

        if proyecto_id:
            self.fields["tarea"].queryset = (
                Tarea.objects.filter(
                    proyecto_id=proyecto_id,
                    proyecto__in=proyectos,
                    finalizada=False
                ).order_by("nombre")
            )

    def clean_fechas(self):

        texto = self.cleaned_data["fechas"]

        try:
            lista = json.loads(texto)
        except (TypeError, ValueError):
            raise forms.ValidationError(
                "Selecciona los días del calendario."
            )

        if not isinstance(lista, list):
            raise forms.ValidationError(
                "La selección de días no es válida."
            )

        if not 1 <= len(lista) <= 31:
            raise forms.ValidationError(
                "Selecciona entre 1 y 31 días."
            )

        try:
            if not all(
                isinstance(valor, str)
                for valor in lista
            ):
                raise ValueError()

            fechas = [
                date.fromisoformat(valor)
                for valor in lista
            ]

            if any(
                fecha.isoformat() != valor
                for fecha, valor in zip(fechas, lista)
            ):
                raise ValueError()

        except (TypeError, ValueError):
            raise forms.ValidationError(
                "Hay fechas incorrectas en la selección."
            )

        if len(set(fechas)) != len(fechas):
            raise forms.ValidationError(
                "No se puede seleccionar dos veces el mismo día."
            )

        return sorted(fechas)

    def clean(self):

        datos = super().clean()

        proyecto = datos.get("proyecto")
        tarea = datos.get("tarea")
        horas = datos.get("horas")
        fechas = datos.get("fechas")

        if not fechas:
            return datos

        hoy = timezone.localdate()

        for fecha in fechas:

            if (
                fecha.year != self.mes.year
                or fecha.month != self.mes.month
            ):
                self.add_error(
                    "fechas",
                    "Selecciona únicamente días del mes mostrado."
                )
                break

            if fecha > hoy:
                self.add_error(
                    "fechas",
                    "No puedes registrar horas en días futuros."
                )
                break

            if fecha.weekday() >= 5:
                self.add_error(
                    "fechas",
                    "No se pueden seleccionar sábados o domingos."
                )
                break

        festivos = Festivo.objects.filter(
            fecha__in=fechas
        ).values_list("fecha", flat=True)

        if festivos:
            self.add_error(
                "fechas",
                "Has seleccionado algún día festivo."
            )

        if not proyecto or not tarea or horas is None:
            return datos

        if tarea.proyecto_id != proyecto.pk:
            self.add_error(
                "tarea",
                "La tarea no pertenece al proyecto seleccionado."
            )

        if tarea.finalizada:
            self.add_error(
                "tarea",
                "No puedes imputar horas a una tarea finalizada."
            )

        for fecha in fechas:

            if fecha < tarea.fecha_inicio:
                self.add_error(
                    "fechas",
                    "Hay días anteriores al inicio de la tarea."
                )
                break

            if tarea.fecha_fin and fecha > tarea.fecha_fin:
                self.add_error(
                    "fechas",
                    "Hay días posteriores a la fecha de fin de la tarea."
                )
                break

        # Comprobar el total de horas que el usuario
        # ya tiene registradas cada día.

        registros_previos = (
            RegistroHoras.objects.filter(
                investigador=self.investigador,
                fecha__in=fechas
            )
            .values("fecha")
            .annotate(total=Sum("horas"))
        )

        totales = {
            fila["fecha"]: fila["total"]
            for fila in registros_previos
        }

        for fecha in fechas:

            horas_previas = totales.get(
                fecha,
                Decimal("0.00")
            )

            if horas_previas + horas > Decimal("24.00"):
                self.add_error(
                    "horas",
                    "La imputación supera las 24 horas "
                    f"totales del día {fecha:%d/%m/%Y}."
                )
                break

        return datos


# ==========================================
# FECHAS Y PROYECTOS DISPONIBLES
# ==========================================

def obtener_mes(request):

    valor = (
        request.POST.get("mes")
        if request.method == "POST"
        else request.GET.get("mes")
    )

    if valor:
        try:
            mes = datetime.strptime(
                valor,
                "%Y-%m"
            ).date()

            if 2000 <= mes.year <= 2099:
                return mes

        except ValueError:
            pass

    hoy = timezone.localdate()

    return hoy.replace(day=1)


def proyectos_del_investigador(investigador):

    if investigador is None:
        return Proyecto.objects.none()

    ids_dedicaciones = Dedicacion.objects.filter(
        investigador=investigador
    ).values("proyecto_id")

    return (
        Proyecto.objects.filter(
            estado="PROCESO"
        )
        .filter(
            Q(investigador_principal=investigador)
            | Q(pk__in=ids_dedicaciones)
        )
        .distinct()
        .order_by("acronimo")
    )


# ==========================================
# PÁGINA PRINCIPAL: MIS HORAS
# ==========================================

@login_required
def mis_horas(request):

    investigador = Investigador.objects.filter(
        usuario=request.user
    ).first()

    mes = obtener_mes(request)

    proyectos = proyectos_del_investigador(
        investigador
    )

    # Para entrar desde un proyecto concreto
    # y encontrarlo preseleccionado.

    
    # ==========================================
    # PRESELECCIONAR PROYECTO Y TAREA
    # ==========================================

    inicial = {}

    if request.method == "GET":

        proyecto_id = request.GET.get("proyecto")
        tarea_id = request.GET.get("tarea")

        # Comprobar que el proyecto pertenece
        # al investigador y está en proceso.

        proyecto_seleccionado = proyectos.filter(
            pk=proyecto_id
        ).first() if proyecto_id and proyecto_id.isdigit() else None

        if proyecto_seleccionado is not None:

            inicial["proyecto"] = proyecto_seleccionado.pk

            # Comprobar que la tarea existe,
            # pertenece al proyecto y está abierta.

            if tarea_id and tarea_id.isdigit():

                tarea_seleccionada = Tarea.objects.filter(
                    pk=tarea_id,
                    proyecto=proyecto_seleccionado,
                    finalizada=False
                ).first()

                if tarea_seleccionada is not None:

                    inicial["tarea"] = tarea_seleccionada.pk


    formulario = ImputarHorasForm(
        request.POST or None,
        investigador=investigador,
        proyectos=proyectos,
        mes=mes,
        initial=inicial
    )

    # --------------------------------------
    # GUARDAR HORAS
    # --------------------------------------

    if request.method == "POST":

        if investigador is None:
            raise PermissionDenied(
                "Tu usuario no tiene un perfil de investigador."
            )

        if formulario.is_valid():

            datos = formulario.cleaned_data

            registros = [
                RegistroHoras(
                    investigador=investigador,
                    tarea=datos["tarea"],
                    fecha=fecha,
                    horas=datos["horas"],
                    descripcion=datos["descripcion"]
                )
                for fecha in datos["fechas"]
            ]

            with transaction.atomic():
                RegistroHoras.objects.bulk_create(
                    registros
                )

            cantidad = len(registros)

            messages.success(
                request,
                f"Se han registrado correctamente "
                f"{cantidad} día(s) de trabajo."
            )

            url = reverse("horas:mis_horas")

            return redirect(
                f"{url}?mes={mes:%Y-%m}"
            )

    # --------------------------------------
    # REGISTROS DEL MES
    # --------------------------------------

    if investigador is not None:

        registros = list(
            RegistroHoras.objects.filter(
                investigador=investigador,
                fecha__year=mes.year,
                fecha__month=mes.month
            )
            .select_related(
                "tarea__proyecto"
            )
            .order_by("-fecha", "-pk")
        )

    else:
        registros = []

    horas_mes = sum(
        (registro.horas for registro in registros),
        Decimal("0.00")
    )

    dias_trabajados = len({
        registro.fecha
        for registro in registros
    })

    horas_por_dia = defaultdict(
        lambda: Decimal("0.00")
    )

    for registro in registros:
        horas_por_dia[registro.fecha] += registro.horas

    # --------------------------------------
    # CALENDARIO LABORAL
    # --------------------------------------

    festivos = {
        festivo.fecha: festivo.nombre
        for festivo in Festivo.objects.filter(
            fecha__year=mes.year,
            fecha__month=mes.month
        )
    }

    hoy = timezone.localdate()

    calendario = calendar.Calendar(
        firstweekday=0
    )

    semanas = []

    for semana in calendario.monthdatescalendar(
        mes.year,
        mes.month
    ):

        dias = []

        for fecha in semana:

            es_mes_actual = (
                fecha.year == mes.year
                and fecha.month == mes.month
            )

            es_festivo = fecha in festivos
            es_fin_semana = fecha.weekday() >= 5
            es_futuro = fecha > hoy

            bloqueado = (
                not es_mes_actual
                or es_festivo
                or es_fin_semana
                or es_futuro
            )

            dias.append({
                "fecha": fecha,
                "numero": fecha.day,
                "es_mes_actual": es_mes_actual,
                "es_festivo": es_festivo,
                "nombre_festivo": festivos.get(
                    fecha,
                    ""
                ),
                "es_fin_semana": es_fin_semana,
                "es_futuro": es_futuro,
                "es_hoy": fecha == hoy,
                "bloqueado": bloqueado,
                "horas": horas_por_dia.get(
                    fecha,
                    Decimal("0.00")
                ),
            })

        semanas.append(dias)

    # --------------------------------------
    # MESES ANTERIOR Y SIGUIENTE
    # --------------------------------------

    mes_anterior = (
        mes - timedelta(days=1)
    ).replace(day=1)

    if mes.month == 12:
        mes_siguiente = date(
            mes.year + 1,
            1,
            1
        )
    else:
        mes_siguiente = date(
            mes.year,
            mes.month + 1,
            1
        )

    # --------------------------------------
    # TAREAS PARA EL SELECT DINÁMICO
    # --------------------------------------

    tareas_disponibles = Tarea.objects.filter(
        proyecto__in=proyectos,
        finalizada=False
    ).order_by(
        "proyecto__acronimo",
        "nombre"
    )

    opciones_tareas = [
        {
            "id": tarea.pk,
            "proyecto_id": tarea.proyecto_id,
            "nombre": tarea.nombre,
        }
        for tarea in tareas_disponibles
    ]

    return render(
        request,
        "horas/mis_horas.html",
        {
            "investigador": investigador,
            "formulario": formulario,
            "registros": registros,
            "horas_mes": horas_mes,
            "dias_trabajados": dias_trabajados,
            "semanas": semanas,
            "mes": mes,
            "mes_iso": mes.strftime("%Y-%m"),
            "mes_anterior": mes_anterior,
            "mes_siguiente": mes_siguiente,
            "opciones_tareas": opciones_tareas,
        }
    )
