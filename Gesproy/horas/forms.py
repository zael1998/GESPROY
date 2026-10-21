
from django import forms

from proyectos.models import Dedicacion
from usuarios.models import Investigador

from .models import Tarea


class TareaForm(forms.ModelForm):

    class Meta:
        model = Tarea

        fields = [
            "nombre",
            "descripcion",
            "fecha_inicio",
            "fecha_fin",
            "horas_estimadas",
            "tarea_padre",
            "responsable_investigador",
        ]

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "tar-input",
                    "placeholder": "Nombre de la tarea",
                }
            ),

            "descripcion": forms.Textarea(
                attrs={
                    "class": "tar-input",
                    "rows": 3,
                    "placeholder": "Descripción de la tarea (opcional)",
                }
            ),

            "fecha_inicio": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "tar-input",
                    "type": "date",
                }
            ),

            "fecha_fin": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "tar-input",
                    "type": "date",
                }
            ),

            "horas_estimadas": forms.NumberInput(
                attrs={
                    "class": "tar-input",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "tarea_padre": forms.Select(
                attrs={"class": "tar-input"}
            ),

            "responsable_investigador": forms.Select(
                attrs={"class": "tar-input"}
            ),
        }

    def __init__(self, *args, proyecto, **kwargs):
        super().__init__(*args, **kwargs)

        self.proyecto = proyecto

        # Asignar el proyecto antes de las
        # validaciones del modelo.
        self.instance.proyecto = proyecto

        # Formato compatible con input type="date".
        self.fields["fecha_inicio"].input_formats = [
            "%Y-%m-%d"
        ]

        self.fields["fecha_fin"].input_formats = [
            "%Y-%m-%d"
        ]

        # Únicamente tareas del mismo proyecto.
        tareas = Tarea.objects.filter(
            proyecto=proyecto
        ).order_by("nombre")

        if self.instance.pk:
            tareas = tareas.exclude(
                pk=self.instance.pk
            )

        self.fields["tarea_padre"].queryset = tareas

        # Investigadores asociados al proyecto.
        investigadores_ids = set(
            Dedicacion.objects.filter(
                proyecto=proyecto
            ).values_list(
                "investigador_id",
                flat=True
            )
        )

        # El investigador principal también
        # puede ser responsable de tareas.
        if proyecto.investigador_principal_id:
            investigadores_ids.add(
                proyecto.investigador_principal_id
            )

        self.fields[
            "responsable_investigador"
        ].queryset = Investigador.objects.filter(
            pk__in=investigadores_ids
        )

        # Campos opcionales.
        self.fields["tarea_padre"].required = False

        self.fields[
            "responsable_investigador"
        ].required = False

        self.fields["descripcion"].required = False
        self.fields["fecha_fin"].required = False

        # Opciones vacías de los desplegables.
        self.fields["tarea_padre"].empty_label = (
            "Tarea principal (sin subtarea)"
        )

        self.fields[
            "responsable_investigador"
        ].empty_label = "Sin investigador"

    def clean(self):
        datos = super().clean()

        inicio = datos.get("fecha_inicio")
        fin = datos.get("fecha_fin")
        padre = datos.get("tarea_padre")

        # --------------------------------------
        # VALIDACIÓN DE FECHAS
        # --------------------------------------

        if inicio and fin and fin < inicio:
            self.add_error(
                "fecha_fin",
                "La fecha final no puede ser anterior a la inicial."
            )

        # --------------------------------------
        # FECHAS DENTRO DEL PROYECTO
        # --------------------------------------

        if inicio and self.proyecto.fecha_inicio:
            if inicio < self.proyecto.fecha_inicio:
                self.add_error(
                    "fecha_inicio",
                    "La tarea no puede empezar antes que el proyecto."
                )

        if fin and self.proyecto.fecha_fin:
            if fin > self.proyecto.fecha_fin:
                self.add_error(
                    "fecha_fin",
                    "La tarea no puede terminar después del proyecto."
                )

        # --------------------------------------
        # VALIDACIÓN DE SUBTAREAS
        # --------------------------------------

        if padre:

            # Evitar dependencias circulares
            # al modificar tareas.
            actual = padre
            visitados = set()

            while actual is not None:

                if actual.pk in visitados:
                    self.add_error(
                        "tarea_padre",
                        "Se ha detectado una dependencia circular."
                    )
                    break

                if (
                    self.instance.pk
                    and actual.pk == self.instance.pk
                ):
                    self.add_error(
                        "tarea_padre",
                        "Una tarea no puede depender de una de sus subtareas."
                    )
                    break

                visitados.add(actual.pk)
                actual = actual.tarea_padre

            # La subtarea no puede comenzar
            # antes que la tarea principal.
            if inicio and inicio < padre.fecha_inicio:
                self.add_error(
                    "fecha_inicio",
                    "La subtarea no puede comenzar antes que su tarea principal."
                )

            # La subtarea no puede finalizar
            # después que la tarea principal.
            if fin and padre.fecha_fin:
                if fin > padre.fecha_fin:
                    self.add_error(
                        "fecha_fin",
                        "La subtarea no puede terminar después de su tarea principal."
                    )

        return datos
    
from .models import Tarea, ComentarioTarea

# ... Todo tu TareaForm actual permanece igual ...


class ComentarioTareaForm(forms.ModelForm):

    class Meta:
        model = ComentarioTarea

        fields = ["contenido"]

        widgets = {
            "contenido": forms.Textarea(
                attrs={
                    "class": "tar-input",
                    "rows": 4,
                    "placeholder": "Escribe tu comentario...",
                }
            ),
        }
