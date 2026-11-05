from decimal import Decimal

from django import forms

from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.core.exceptions import PermissionDenied, ValidationError

from django.db import transaction

from django.forms import formset_factory

from django.shortcuts import redirect, render

from django.utils import timezone

from proyectos.models import Proyecto

from usuarios.models import Investigador

from .calendario import proyectos_del_investigador

from .models import RegistroHoras, Tarea

# ==========================================
# FORMULARIO DE FECHAS COMUNES
# ==========================================
class PeriodoComunForm(forms.Form):

    fecha = forms.DateField(

        label="Fecha de inicio",

        widget=forms.DateInput(

            format="%Y-%m-%d",

            attrs={"type": "date"}

        ),

        input_formats=["%Y-%m-%d"],

    )

    fecha_fin = forms.DateField(

        label="Fecha de finalización",

        required=False,

        widget=forms.DateInput(

            format="%Y-%m-%d",

            attrs={"type": "date"}

        ),

        input_formats=["%Y-%m-%d"],

    )

    def clean(self):

        datos = super().clean()

        inicio = datos.get("fecha")

        fin = datos.get("fecha_fin")

        if inicio is None:

            return datos

        # Una fecha final vacía equivale a un solo día.
        if fin is None:

            fin = inicio

        if fin < inicio:

            self.add_error(

                "fecha_fin",

                "La fecha final no puede ser anterior a la inicial."

            )

            return datos

        hoy = timezone.localdate()

        if inicio > hoy or fin > hoy:

            self.add_error(

                "fecha",

                "No puedes registrar horas en fechas futuras."

            )

        if (

            inicio.year != fin.year

            or inicio.month != fin.month

        ):

            self.add_error(

                "fecha_fin",

                "No puedes registrar un periodo que abarque "

                "dos meses distintos. Divide la imputación."

            )

        return datos

# ==========================================
# FORMULARIO DE UNA IMPUTACIÓN
# ==========================================
class RegistroPeriodoForm(forms.Form):

    proyecto = forms.ModelChoiceField(

        queryset=Proyecto.objects.none(),

        label="Proyecto",

        empty_label="Seleccionar proyecto",

    )

    tarea = forms.ModelChoiceField(

        queryset=Tarea.objects.none(),

        label="Tarea",

        empty_label="Seleccionar tarea",

    )

    horas = forms.DecimalField(

        label="Horas totales",

        min_value=Decimal("0.01"),

        max_value=Decimal("744.00"),

        max_digits=5,

        decimal_places=2,

        widget=forms.NumberInput(

            attrs={

                "step": "0.01",

                "min": "0.01",

                "max": "744",

                "placeholder": "Ej. 6.50",

            }

        ),

    )

    descripcion = forms.CharField(

        required=False,

        label="Descripción",

        widget=forms.Textarea(

            attrs={

                "rows": 2,

                "placeholder": "Trabajo realizado (opcional)",

            }

        ),

    )

    def __init__(

        self,

        *args,

        proyectos,

        inicio=None,

        fin=None,

        **kwargs

    ):

        super().__init__(*args, **kwargs)

        self.inicio = inicio

        self.fin = fin

        self.fields["proyecto"].queryset = proyectos

        tareas = (

            Tarea.objects.filter(

                proyecto__in=proyectos,

                finalizada=False,

            )

            .select_related("proyecto")

            .order_by("proyecto__acronimo", "nombre")

        )

        # Todas las tareas pertenecen a proyectos
        # autorizados para este investigador.
        self.fields["tarea"].queryset = tareas

        self.fields["tarea"].label_from_instance = (

            lambda tarea: (

                f"{tarea.proyecto.acronimo} - {tarea.nombre}"

            )

        )

    def clean(self):

        datos = super().clean()

        proyecto = datos.get("proyecto")

        tarea = datos.get("tarea")

        if not proyecto or not tarea:

            return datos

        if tarea.proyecto_id != proyecto.pk:

            self.add_error(

                "tarea",

                "La tarea no pertenece al proyecto seleccionado."

            )

        if proyecto.estado != "PROCESO":

            self.add_error(

                "proyecto",

                "Solo se admiten proyectos en proceso."

            )

        if tarea.finalizada:

            self.add_error(

                "tarea",

                "No puedes imputar horas a una tarea finalizada."

            )

        inicio = self.inicio

        fin = self.fin

        # Si las fechas comunes no son válidas,
        # sus errores los muestra PeriodoComunForm.
        if inicio is None or fin is None:

            return datos

        if tarea.fecha_inicio and inicio < tarea.fecha_inicio:

            self.add_error(

                "tarea",

                "El periodo empieza antes del inicio de esta tarea."

            )

        if tarea.fecha_fin and fin > tarea.fecha_fin:

            self.add_error(

                "tarea",

                "El periodo termina después del fin de esta tarea."

            )

        if proyecto.fecha_inicio and inicio < proyecto.fecha_inicio:

            self.add_error(

                "proyecto",

                "El periodo empieza antes del inicio del proyecto."

            )

        if proyecto.fecha_fin and fin > proyecto.fecha_fin:

            self.add_error(

                "proyecto",

                "El periodo termina después del fin del proyecto."

            )

        return datos

# ==========================================
# VARIAS IMPUTACIONES PARA EL MISMO PERIODO
# ==========================================
RegistroPeriodoFormSet = formset_factory(

    RegistroPeriodoForm,

    extra=4,

    min_num=1,

    max_num=4,

    validate_min=True,

    validate_max=True,

)

# ==========================================
# VISTA: REGISTRAR PERIODOS
# ==========================================
@login_required

def registrar_periodos(request):

    investigador = Investigador.objects.filter(

        usuario=request.user

    ).first()

    if investigador is None:

        raise PermissionDenied(

            "Tu usuario no tiene un perfil de investigador."

        )

    proyectos = proyectos_del_investigador(investigador)

    if request.method == "POST":

        periodo_form = PeriodoComunForm(request.POST)

        # Validamos primero las fechas compartidas.
        periodo_valido = periodo_form.is_valid()

        if periodo_valido:

            inicio = periodo_form.cleaned_data["fecha"]

            fin = (

                periodo_form.cleaned_data.get("fecha_fin")

                or inicio

            )

        else:

            inicio = None

            fin = None

        formularios = RegistroPeriodoFormSet(

            request.POST,

            prefix="registros",

            form_kwargs={

                "proyectos": proyectos,

                "inicio": inicio,

                "fin": fin,

            },

        )

        imputaciones_validas = formularios.is_valid()

        if periodo_valido and imputaciones_validas:

            datos_validos = [

                formulario.cleaned_data

                for formulario in formularios.forms

                if formulario.has_changed()

                and formulario.cleaned_data

            ]

            try:

                with transaction.atomic():

                    # Serializamos las imputaciones de
                    # este investigador dentro de esta vista.
                    Investigador.objects.select_for_update().get(

                        pk=investigador.pk

                    )

                    for datos in datos_validos:

                        registro = RegistroHoras(

                            investigador=investigador,

                            tarea=datos["tarea"],

                            fecha=inicio,

                            fecha_fin=(

                                fin if fin > inicio else None

                            ),

                            horas=datos["horas"],

                            descripcion=datos.get(

                                "descripcion", ""

                            ),

                        )

                        # El modelo comprueba validaciones
                        # previas, cierres y restricciones.
                        registro.save()

            except ValidationError as error:

                messages.error(

                    request,

                    "No se han guardado las imputaciones: "

                    + "; ".join(error.messages)

                )

            else:

                messages.success(

                    request,

                    f"Se han registrado correctamente "

                    f"{len(datos_validos)} imputaciones "

                    f"del {inicio:%d/%m/%Y} "

                    f"al {fin:%d/%m/%Y}."

                )

                return redirect("horas:registrar_periodos")

    else:

        periodo_form = PeriodoComunForm()

        formularios = RegistroPeriodoFormSet(

            prefix="registros",

            form_kwargs={

                "proyectos": proyectos,

            },

        )

    return render(

        request,

        "horas/registrar_periodos.html",

        {

            "periodo_form": periodo_form,

            "formularios": formularios,

        }

    )
