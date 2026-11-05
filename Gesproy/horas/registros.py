"""

Edición y eliminación segura de registros de horas.

Admite:

- Registros de un solo día.

- Registros por periodos dentro de un mismo mes.

No permite modificar registros validados ni meses cerrados.

Conserva el historial de auditoría.

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

from django.utils import timezone

from .calendario import JORNADA_ORIENTATIVA_HORAS

from .models import (

    CierreMensualHoras,

    RegistroHoras,

    MAX_HORAS_DIA,

    MAX_HORAS_PERIODO,

)

# ==========================================
# FORMULARIO DE EDICIÓN
# ==========================================
class EditarRegistroForm(forms.Form):

    fecha = forms.DateField(

        label="Fecha de inicio",

        widget=forms.DateInput(

            format="%Y-%m-%d",

            attrs={

                "class": "mr-input",

                "type": "date",

            }

        ),

        input_formats=["%Y-%m-%d"],

    )

    fecha_fin = forms.DateField(

        label="Fecha de finalización",

        required=False,

        widget=forms.DateInput(

            format="%Y-%m-%d",

            attrs={

                "class": "mr-input",

                "type": "date",

            }

        ),

        input_formats=["%Y-%m-%d"],

    )

    horas = forms.DecimalField(

        label="Horas trabajadas",

        min_value=Decimal("0.01"),

        max_value=MAX_HORAS_PERIODO,

        max_digits=5,

        decimal_places=2,

        widget=forms.NumberInput(

            attrs={

                "class": "mr-input",

                "step": "0.01",

                "min": "0.01",

                "autocomplete": "off",

            }

        ),

    )

    descripcion = forms.CharField(

        label="Descripción del trabajo",

        required=False,

        widget=forms.Textarea(

            attrs={

                "class": "mr-input",

                "rows": 4,

                "placeholder": (

                    "Describe el trabajo realizado (opcional)"

                ),

            }

        ),

    )

    def __init__(self, *args, registro, **kwargs):

        super().__init__(*args, **kwargs)

        self.registro = registro

# El tipo de registro determina el máximo aplicable.
        self.es_periodo = registro.fecha_fin is not None

        self.fields["horas"].max_value = (

            MAX_HORAS_PERIODO

            if self.es_periodo

            else MAX_HORAS_DIA

        )

        self.fields["horas"].widget.attrs["max"] = str(

            self.fields["horas"].max_value

        )

# Mantenemos el tipo original:
# un día no puede transformarse aquí en periodo,
# ni un periodo en registro diario.
        if not self.es_periodo:

            del self.fields["fecha_fin"]

    def clean(self):

        datos = super().clean()

        inicio = datos.get("fecha")

        fin = datos.get("fecha_fin") if self.es_periodo else None

        horas = datos.get("horas")

        if not inicio:

            return datos

        if self.es_periodo and not fin:

            self.add_error(

                "fecha_fin",

                "Indica la fecha final del periodo."

            )

            return datos

        if not self.es_periodo:

            fin = inicio

        if fin < inicio:

            self.add_error(

                "fecha_fin",

                "La fecha final no puede ser anterior a la inicial."

            )

            return datos

        if self.es_periodo and fin == inicio:

            self.add_error(

                "fecha_fin",

                "Para un periodo utiliza dos fechas diferentes."

            )

        if (

            inicio.year != fin.year

            or inicio.month != fin.month

        ):

            if self.es_periodo:

                self.add_error(

                    "fecha_fin",

                    "Un periodo no puede abarcar dos meses. "

                    "Registra cada mes por separado."

                )

        if fin > timezone.localdate():

            self.add_error(

                "fecha",

                "No puedes imputar horas en fechas futuras."

            )

        tarea = self.registro.tarea

        proyecto = tarea.proyecto

        if inicio < tarea.fecha_inicio:

            self.add_error(

                "fecha",

                "La fecha es anterior al inicio de la tarea."

            )

        if tarea.fecha_fin and fin > tarea.fecha_fin:

            if self.es_periodo:

                self.add_error(

                    "fecha_fin",

                    "El periodo termina después de la tarea."

                )

            else:

                self.add_error(

                    "fecha",

                    "La fecha es posterior al fin de la tarea."

                )

        if proyecto.fecha_inicio and inicio < proyecto.fecha_inicio:

            self.add_error(

                "fecha",

                "La fecha es anterior al inicio del proyecto."

            )

        if proyecto.fecha_fin and fin > proyecto.fecha_fin:

            if self.es_periodo:

                self.add_error(

                    "fecha_fin",

                    "El periodo termina después del proyecto."

                )

            else:

                self.add_error(

                    "fecha",

                    "La fecha es posterior al fin del proyecto."

                )

# No permitimos trasladar el registro a otro mes:
# los meses tienen cierres y validaciones propios.
        if (

            inicio.year != self.registro.fecha.year

            or inicio.month != self.registro.fecha.month

        ):

            self.add_error(

                "fecha",

                "No puedes trasladar un registro a otro mes "

                "desde esta pantalla."

            )

        if horas is not None:

            limite = (

                MAX_HORAS_PERIODO

                if self.es_periodo

                else MAX_HORAS_DIA

            )

            if horas > limite:

                self.add_error(

                    "horas",

                    f"El máximo permitido en este formulario es "

                    f"{limite} horas."

                )

        return datos

# ==========================================
# OBTENER REGISTRO PROPIO
# ==========================================
def _registro_propio(usuario, registro_id, bloqueo=False):

    """

    Un investigador solo puede gestionar sus propios registros.

    """

    consulta = RegistroHoras.objects.select_related(

        "investigador__usuario",

        "tarea__proyecto",

    ).filter(

        investigador__usuario=usuario

    )

    if bloqueo:

        consulta = consulta.select_for_update()

    return get_object_or_404(

        consulta,

        pk=registro_id

    )

# ==========================================
# COMPROBAR PERMISOS
# ==========================================
def _comprobar_editable(registro, *, eliminar=False):

    if registro.validado:

        raise PermissionDenied(

            "Estas horas están validadas. "

            "Solicita su reapertura al administrador."

        )

    if registro.tarea.proyecto.estado != "PROCESO":

        raise PermissionDenied(

            "Solo se pueden corregir horas "

            "de proyectos en proceso."

        )

    if CierreMensualHoras.objects.filter(

        investigador_id=registro.investigador_id,

        proyecto_id=registro.tarea.proyecto_id,

        anio=registro.fecha.year,

        mes=registro.fecha.month,

    ).exists():

        raise PermissionDenied(

            "El mes de este proyecto está cerrado. "

            "Solicita su reapertura."

        )

    if eliminar and registro.historial_validaciones.exists():

        raise PermissionDenied(

            "Este registro se validó anteriormente "

            "y conserva historial de auditoría. "

            "Puedes editarlo tras su reapertura, "

            "pero no borrarlo."

        )

def _volver_al_mes(registro):

    return (

        f"{reverse('horas:mis_horas')}"

        f"?mes={registro.fecha:%Y-%m}"

    )

# ==========================================
# EDITAR REGISTRO
# ==========================================
@login_required

def editar_registro(request, registro_id):

    registro = _registro_propio(

        request.user,

        registro_id

    )

    _comprobar_editable(registro)

    if request.method == "POST":

        formulario = EditarRegistroForm(

            request.POST,

            registro=registro

        )

        if formulario.is_valid():

            try:

                with transaction.atomic():

# Volver a leer y bloquear el registro
# antes de modificarlo.
                    registro = _registro_propio(

                        request.user,

                        registro_id,

                        bloqueo=True

                    )

                    _comprobar_editable(registro)

                    datos = formulario.cleaned_data

# La misma pantalla no cambia el tipo
# diario/periodo del registro.
                    if (

                        (registro.fecha_fin is not None)

                        != formulario.es_periodo

                    ):

                        raise ValidationError(

                            "El tipo de registro ha cambiado. "

                            "Recarga la página."

                        )

                    registro.fecha = datos["fecha"]

                    if formulario.es_periodo:

                        registro.fecha_fin = datos["fecha_fin"]

                    else:

                        registro.fecha_fin = None

                    registro.horas = datos["horas"]

                    registro.descripcion = datos["descripcion"]

# save() ejecuta las protecciones
# definidas en models.py.
                    registro.save(

                        update_fields=[

                            "fecha",

                            "fecha_fin",

                            "horas",

                            "descripcion",

                        ]

                    )

# Solo tiene sentido calcular una
# jornada diaria para registros puntuales.
                    total_dia = None

                    if registro.fecha_fin is None:

                        total_dia = (

                            RegistroHoras.objects.filter(

                                investigador_id=registro.investigador_id,

                                fecha=registro.fecha,

                                fecha_fin__isnull=True,

                            ).aggregate(

                                total=Sum("horas")

                            )["total"] or Decimal("0.00")

                        )

                    destino = _volver_al_mes(registro)

            except ValidationError as error:

                formulario.add_error(

                    None,

                    error

                )

            else:

                messages.success(

                    request,

                    "Registro de horas actualizado correctamente."

                )

                if (

                    total_dia is not None

                    and total_dia > JORNADA_ORIENTATIVA_HORAS

                ):

                    messages.warning(

                        request,

                        f"Atención: el {registro.fecha:%d/%m/%Y} "

                        f"acumulas {total_dia} horas "

                        "entre tus proyectos."

                    )

                return redirect(destino)

    else:

        formulario = EditarRegistroForm(

            registro=registro,

            initial={

                "fecha": registro.fecha,

                "fecha_fin": registro.fecha_fin,

                "horas": registro.horas,

                "descripcion": registro.descripcion,

            }

        )

    return render(

        request,

        "horas/editar_registro.html",

        {

            "registro": registro,

            "formulario": formulario,

            "es_periodo": registro.fecha_fin is not None,

            "jornada_orientativa": JORNADA_ORIENTATIVA_HORAS,

            "max_horas": (

                MAX_HORAS_PERIODO

                if registro.fecha_fin is not None

                else MAX_HORAS_DIA

            ),

        }

    )

# ==========================================
# ELIMINAR REGISTRO
# ==========================================
@login_required

def eliminar_registro(request, registro_id):

    registro = _registro_propio(

        request.user,

        registro_id

    )

    _comprobar_editable(

        registro,

        eliminar=True

    )

    if request.method == "POST":

        try:

            with transaction.atomic():

                registro = _registro_propio(

                    request.user,

                    registro_id,

                    bloqueo=True

                )

                _comprobar_editable(

                    registro,

                    eliminar=True

                )

                volver = _volver_al_mes(registro)

# Tanto un día como un periodo son
# un único objeto RegistroHoras.
                registro.delete()

        except ValidationError as error:

            messages.error(

                request,

                "; ".join(error.messages)

            )

            return redirect(

                _volver_al_mes(registro)

            )

        else:

            messages.success(

                request,

                "Registro de horas eliminado correctamente."

            )

            return redirect(volver)

    return render(

        request,

        "horas/eliminar_registro.html",

        {

            "registro": registro,

            "es_periodo": registro.fecha_fin is not None,

        }

    )
