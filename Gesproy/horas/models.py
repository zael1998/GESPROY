from collections import defaultdict

from decimal import Decimal, InvalidOperation



from django.core.exceptions import ValidationError



from django.core.validators import MinValueValidator



from django.db import models

from django.db.models import Sum

from django.utils import timezone



# Nadie puede tener más de 24 horas registradas entre TODOS sus proyectos

# y tareas para una misma fecha. Ocho horas es solo una referencia orientativa.

MAX_HORAS_DIA = Decimal("24.00")





def _horas_validas(valor):

    try:

        horas = Decimal(str(valor))

    except (InvalidOperation, TypeError, ValueError):

        raise ValidationError("Las horas deben ser un número válido.")

    if not horas.is_finite() or not Decimal("0.00") < horas <= MAX_HORAS_DIA:

        raise ValidationError("Las horas deben ser mayores que cero y no superar 24.")

    return horas





class RegistroHorasQuerySet(models.QuerySet):



    """Impide borrar o cambiar horas ya aprobadas desde operaciones masivas."""



    def update(self, **kwargs):



        # QuerySet.update() no llama a save(): prohibimos cambios masivos

        # en campos que afectan al total diario para no saltar el control.

        protegidos = {"horas", "fecha", "investigador", "investigador_id", "tarea", "tarea_id"}

        if protegidos.intersection(kwargs):

            raise ValidationError(

                "Para modificar horas, fechas o asignaciones usa el registro "

                "individual y save(); no uses QuerySet.update()."

            )



        if self.filter(validado=True).exists():



            campos_validacion = {"validado", "validado_por", "fecha_validacion"}



            if not set(kwargs).issubset(campos_validacion):



                raise ValidationError(



                    "No se pueden modificar registros de horas validados. "



                    "Un administrador debe reabrirlos primero."



                )



        return super().update(**kwargs)



    def delete(self):



        if self.filter(validado=True).exists():



            raise ValidationError(



                "No se pueden eliminar registros validados. "



                "Un administrador debe reabrirlos primero."



            )



        return super().delete()



    def bulk_create(self, objs, *args, **kwargs):



        # El calendario puede crear varios días en una sola operación.

        # bulk_create NO llama automáticamente a save() ni full_clean().

        objs = list(objs)

        sumas_nuevas = defaultdict(lambda: Decimal("0.00"))



        for registro in objs:

            sumas_nuevas[(registro.investigador_id, registro.fecha)] += (

                _horas_validas(registro.horas)

            )



        for (investigador_id, fecha), nuevas in sumas_nuevas.items():

            if investigador_id is None or fecha is None:

                continue  # La BD comprobará los campos obligatorios.

            existentes = self.model.objects.filter(

                investigador_id=investigador_id,

                fecha=fecha,

            ).aggregate(total=Sum("horas"))["total"] or Decimal("0.00")

            if existentes + nuevas > MAX_HORAS_DIA:

                raise ValidationError(

                    f"El {fecha:%d/%m/%Y} se superan las 24 horas totales "

                    "del investigador, sumando todos sus proyectos."

                )



        for registro in objs:



            if self.model.objects.filter(



                investigador_id=registro.investigador_id,



                tarea_id=registro.tarea_id,



                fecha=registro.fecha,



                validado=True,



            ).exists():



                raise ValidationError(



                    "Ya existen horas validadas para esa tarea y fecha."



                )



            if (registro.tarea_id and registro.investigador_id and registro.fecha



                and CierreMensualHoras.objects.filter(



                    proyecto_id=registro.tarea.proyecto_id,



                    investigador_id=registro.investigador_id,



                    anio=registro.fecha.year,



                    mes=registro.fecha.month,



                ).exists()):



                raise ValidationError(



                    "El mes ya está cerrado en este proyecto. Solicita su reapertura."



                )



        return super().bulk_create(objs, *args, **kwargs)



    def bulk_update(self, objs, fields, batch_size=None):



        protegidos = {"horas", "fecha", "investigador", "investigador_id", "tarea", "tarea_id"}

        if protegidos.intersection(fields):

            raise ValidationError(

                "No se pueden modificar horas o fechas en bloque; "

                "edita los registros pendientes individualmente."

            )



        claves = [obj.pk for obj in objs if obj.pk is not None]



        if claves and self.model.objects.filter(



            pk__in=claves, validado=True



        ).exists():



            raise ValidationError(



                "No se pueden modificar registros validados en bloque."



            )



        return super().bulk_update(objs, fields, batch_size=batch_size)



# ==========================================



# REGISTROS DE HORAS



# ==========================================



class RegistroHoras(models.Model):



    fecha = models.DateField(verbose_name="Fecha de trabajo")



    horas = models.DecimalField(



        max_digits=5,



        decimal_places=2,



        validators=[MinValueValidator(Decimal("0.01"))],



        verbose_name="Horas trabajadas",



    )



    descripcion = models.TextField(



        blank=True, verbose_name="Descripción del trabajo"



    )



    investigador = models.ForeignKey(



        "usuarios.Investigador",



        on_delete=models.PROTECT,



        verbose_name="Investigador",



    )



    tarea = models.ForeignKey(



        "Tarea",



        on_delete=models.PROTECT,



        related_name="registros_horas",



        verbose_name="Tarea",



    )



    validado = models.BooleanField(



        default=False, db_index=True, verbose_name="Validado"



    )



    validado_por = models.ForeignKey(



        "usuarios.Usuario",



        on_delete=models.PROTECT,



        null=True,



        blank=True,



        related_name="registros_horas_validados",



        verbose_name="Validado por",



    )



    fecha_validacion = models.DateTimeField(



        null=True, blank=True, verbose_name="Fecha de validación"



    )



    objects = RegistroHorasQuerySet.as_manager()



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



    def save(self, *args, **kwargs):



        # Cubre ediciones normales de instancias y update_or_create.



        # Las acciones de validar/reabrir emplean update() para modificar



        # exclusivamente los campos de validación.



        if self.pk and RegistroHoras.objects.filter(



            pk=self.pk, validado=True



        ).exists():



            raise ValidationError(



                "Estas horas ya están validadas. Solo se podrán modificar "



                "si un administrador las reabre previamente."



            )



        # Evita registrar un segundo parte en un día/tarea ya cerrado.



        if RegistroHoras.objects.filter(



            investigador_id=self.investigador_id,



            tarea_id=self.tarea_id,



            fecha=self.fecha,



            validado=True,



        ).exclude(pk=self.pk).exists():



            raise ValidationError(



                "Ya existe un registro validado para esta tarea y fecha. "



                "Solicita que un administrador lo reabra."



            )



        if self.tarea_id and self.investigador_id and self.fecha:



            if CierreMensualHoras.objects.filter(



                proyecto_id=self.tarea.proyecto_id,



                investigador_id=self.investigador_id,



                anio=self.fecha.year,



                mes=self.fecha.month,



            ).exists():



                raise ValidationError(



                    "Este mes está cerrado para el proyecto. "



                    "Solicita su reapertura a un administrador."



                )



        # Protege también .objects.create() y save() fuera del calendario.

        # Si editamos un registro pendiente, excluimos sus horas antiguas.

        horas_actuales = _horas_validas(self.horas)

        if self.investigador_id and self.fecha:

            existentes = RegistroHoras.objects.filter(

                investigador_id=self.investigador_id,

                fecha=self.fecha,

            ).exclude(pk=self.pk).aggregate(total=Sum("horas"))["total"] or Decimal("0.00")

            if existentes + horas_actuales > MAX_HORAS_DIA:

                raise ValidationError(

                    f"El {self.fecha:%d/%m/%Y} se superan las 24 horas "

                    "totales del investigador, sumando todos sus proyectos."

                )



        super().save(*args, **kwargs)



    def delete(self, *args, **kwargs):



        if self.validado or RegistroHoras.objects.filter(



            pk=self.pk, validado=True



        ).exists():



            raise ValidationError(



                "No se pueden eliminar horas validadas."



            )



        return super().delete(*args, **kwargs)



class CierreMensualHoras(models.Model):



    """Cierre mensual por proyecto e investigador para impedir nuevas altas."""



    investigador = models.ForeignKey(



        "usuarios.Investigador", on_delete=models.PROTECT



    )



    proyecto = models.ForeignKey(



        "proyectos.Proyecto", on_delete=models.PROTECT



    )



    anio = models.PositiveIntegerField()



    mes = models.PositiveSmallIntegerField()



    validado_por = models.ForeignKey(



        "usuarios.Usuario", on_delete=models.PROTECT



    )



    fecha_validacion = models.DateTimeField(auto_now_add=True)



    class Meta:



        verbose_name = "Cierre mensual de horas"



        verbose_name_plural = "Cierres mensuales de horas"



        constraints = [



            models.UniqueConstraint(



                fields=["investigador", "proyecto", "anio", "mes"],



                name="cierre_horas_unico_mes_proyecto_investigador",



            )



        ]



    def __str__(self):



        return f"{self.investigador} - {self.proyecto} - {self.mes}/{self.anio}"



class HistorialValidacionHoras(models.Model):



    ACCIONES = [



        ("VALIDAR", "Validado"),



        ("REABRIR", "Reabierto por administrador"),



    ]



    registro = models.ForeignKey(



        RegistroHoras,



        on_delete=models.PROTECT,



        related_name="historial_validaciones",



    )



    accion = models.CharField(max_length=12, choices=ACCIONES)



    usuario = models.ForeignKey(



        "usuarios.Usuario", on_delete=models.PROTECT



    )



    fecha = models.DateTimeField(auto_now_add=True)



    motivo = models.TextField(blank=True)



    class Meta:



        verbose_name = "Historial de validación de horas"



        verbose_name_plural = "Historiales de validación de horas"



        ordering = ["-fecha"]



    def __str__(self):



        return f"{self.get_accion_display()} - {self.registro_id}"



# ==========================================



# TAREAS DE UN PROYECTO (CONSERVADAS)



# ==========================================



class Tarea(models.Model):



    nombre = models.CharField(



        max_length=100,



        verbose_name="Nombre",



    )



    descripcion = models.TextField(blank=True, verbose_name="Descripción")



    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")



    fecha_fin = models.DateField(



        null=True, blank=True, verbose_name="Fecha de fin"



    )



    horas_estimadas = models.DecimalField(



        max_digits=8,



        decimal_places=2,



        validators=[MinValueValidator(Decimal("0.01"))],



        verbose_name="Horas previstas",



    )



    proyecto = models.ForeignKey(



        "proyectos.Proyecto",



        on_delete=models.PROTECT,



        verbose_name="Proyecto",



    )



    tarea_padre = models.ForeignKey(



        "self",



        on_delete=models.PROTECT,



        null=True,



        blank=True,



        related_name="subtareas",



        verbose_name="Tarea principal",



    )



    responsable_investigador = models.ForeignKey(



        "usuarios.Investigador",



        on_delete=models.PROTECT,



        null=True,



        blank=True,



        verbose_name="Investigador responsable",



    )



    finalizada = models.BooleanField(default=False, verbose_name="Finalizada")



    comentario = models.TextField(



        null=True, blank=True, verbose_name="Comentario"



    )



    class Meta:



        verbose_name = "Tarea"



        verbose_name_plural = "Tareas"



        ordering = ["fecha_inicio"]



    def __str__(self):



        return f"{self.nombre} - {self.proyecto.nombre}"



    def clean(self):



        super().clean()



        errores = {}



        if (



            self.fecha_inicio



            and self.fecha_fin



            and self.fecha_fin < self.fecha_inicio



        ):



            errores["fecha_fin"] = (



                "La fecha de fin no puede ser anterior a la fecha de inicio."



            )



        if self.tarea_padre_id:



            if self.pk and self.tarea_padre_id == self.pk:



                errores["tarea_padre"] = (



                    "Una tarea no puede depender de sí misma."



                )



            else:



                padre = Tarea.objects.filter(pk=self.tarea_padre_id).first()



                if padre:



                    if (



                        self.proyecto_id



                        and padre.proyecto_id != self.proyecto_id



                    ):



                        errores["tarea_padre"] = (



                            "La tarea principal debe pertenecer al mismo proyecto."



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


# ==========================================
# COMENTARIOS INDIVIDUALES DE TAREAS
# ==========================================

class ComentarioTarea(models.Model):
    """Entrada del historial de comentarios de una tarea o subtarea."""

    tarea = models.ForeignKey(
        "Tarea",
        on_delete=models.PROTECT,
        related_name="comentarios_individuales",
        verbose_name="Tarea",
    )
    autor = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        related_name="comentarios_de_tareas",
        verbose_name="Autor",
    )
    contenido = models.TextField(verbose_name="Comentario")
    fecha_creacion = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name="Fecha de creación",
    )

    class Meta:
        verbose_name = "Comentario de tarea"
        verbose_name_plural = "Comentarios de tareas"
        ordering = ["fecha_creacion", "pk"]

    def __str__(self):
        return f"Comentario de {self.autor} en la tarea {self.tarea_id}"
