
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


# ==========================================
# REGISTROS DE HORAS
# ==========================================

class RegistroHoras(models.Model):

    fecha = models.DateField(
        verbose_name="Fecha de trabajo"
    )

    horas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Horas trabajadas"
    )

    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción del trabajo"
    )

    investigador = models.ForeignKey(
        "usuarios.Investigador",
        on_delete=models.PROTECT,
        verbose_name="Investigador"
    )

    tarea = models.ForeignKey(
        "Tarea",
        on_delete=models.PROTECT,
        related_name="registros_horas",
        verbose_name="Tarea"
    )

    class Meta:
        verbose_name = "Registro de Horas"
        verbose_name_plural = "Registros de Horas"
        ordering = ["-fecha"]

    def __str__(self):
        return (
            f"{self.investigador} - "
            f"{self.tarea.nombre} - "
            f"{self.fecha}"
        )


# ==========================================
# TAREAS DE UN PROYECTO
# ==========================================

class Tarea(models.Model):

    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )

    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )

    fecha_inicio = models.DateField(
        verbose_name="Fecha de inicio"
    )

    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de fin"
    )

    horas_estimadas = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Horas previstas"
    )

    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        on_delete=models.PROTECT,
        verbose_name="Proyecto"
    )

    # Una tarea puede depender de otra tarea.
    # Si no tiene tarea padre, es una tarea principal.

    tarea_padre = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subtareas",
        verbose_name="Tarea principal"
    )

    # RESPONSABLE INVESTIGADOR

    responsable_investigador = models.ForeignKey(
        "usuarios.Investigador",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Investigador responsable"
    )

   

    finalizada = models.BooleanField(
        default=False,
        verbose_name="Finalizada"
    )

    # Conservamos el campo que ya tenías.

    comentario = models.TextField(
        null=True,
        blank=True,
        verbose_name="Comentario"
    )

    class Meta:
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        ordering = ["fecha_inicio"]

    def __str__(self):
        return f"{self.nombre} - {self.proyecto.nombre}"

    # ==========================================
    # VALIDACIONES BÁSICAS
    # ==========================================

    def clean(self):
        super().clean()

        errores = {}

        # La fecha final no puede ser anterior
        # a la fecha inicial.

        if (
            self.fecha_inicio
            and self.fecha_fin
            and self.fecha_fin < self.fecha_inicio
        ):
            errores["fecha_fin"] = (
                "La fecha de fin no puede ser "
                "anterior a la fecha de inicio."
            )

        # Solo puede haber un tipo de responsable:
        # investigador O socio.

        

        # Comprobaciones de subtareas.

        if self.tarea_padre_id:

            if self.pk and self.tarea_padre_id == self.pk:

                errores["tarea_padre"] = (
                    "Una tarea no puede depender de sí misma."
                )

            else:

                padre = Tarea.objects.filter(
                    pk=self.tarea_padre_id
                ).first()

                if padre:

                    if (
                        self.proyecto_id
                        and padre.proyecto_id != self.proyecto_id
                    ):
                        errores["tarea_padre"] = (
                            "La tarea principal debe pertenecer "
                            "al mismo proyecto."
                        )

                    if (
                        self.fecha_inicio
                        and padre.fecha_inicio
                        and self.fecha_inicio < padre.fecha_inicio
                    ):
                        errores["fecha_inicio"] = (
                            "La subtarea no puede comenzar antes "
                            "que su tarea principal."
                        )

                    if (
                        self.fecha_fin
                        and padre.fecha_fin
                        and self.fecha_fin > padre.fecha_fin
                    ):
                        errores["fecha_fin"] = (
                            "La subtarea no puede terminar después "
                            "que su tarea principal."
                        )

        if errores:
            raise ValidationError(errores)
