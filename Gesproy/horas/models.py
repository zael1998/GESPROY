from collections import defaultdict

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from django.core.validators import MinValueValidator

from django.db import models

from django.db.models import Q, Sum

from django.utils import timezone

# ==========================================
# LIMITES DE HORAS
# ==========================================
# Limite para registros de un solo dia.
MAX_HORAS_DIA = Decimal("24.00")

# Limite tecnico provisional para periodos.
# NO sustituye al futuro limite mensual laboral.
MAX_HORAS_PERIODO = Decimal("744.00")

def _horas_validas(valor, *, es_periodo=False):

    try:

        horas = Decimal(str(valor))

    except (InvalidOperation, TypeError, ValueError):

        raise ValidationError(

            "Las horas deben ser un número válido."

        )

    limite = (

        MAX_HORAS_PERIODO

        if es_periodo

        else MAX_HORAS_DIA

    )

    if (

        not horas.is_finite()

        or not Decimal("0.00") < horas <= limite

    ):

        raise ValidationError(

            f"Las horas deben ser mayores que cero "

            f"y no superar {limite} "

            f"para {'un periodo' if es_periodo else 'un día'}."

        )

    return horas

# ==========================================
# PROTECCION DE OPERACIONES MASIVAS
# ==========================================
class RegistroHorasQuerySet(models.QuerySet):

    """Protege registros validados y operaciones masivas."""

    def update(self, **kwargs):

# update() no ejecuta save() ni full_clean().
        protegidos = {

            "horas",

            "fecha",

            "fecha_fin",

            "investigador",

            "investigador_id",

            "tarea",

            "tarea_id",

        }

        if protegidos.intersection(kwargs):

            raise ValidationError(

                "Para modificar horas, fechas o asignaciones "

                "usa el registro individual y save()."

            )

        if self.filter(validado=True).exists():

            campos_validacion = {

                "validado",

                "validado_por",

                "fecha_validacion",

            }

            if not set(kwargs).issubset(campos_validacion):

                raise ValidationError(

                    "No se pueden modificar registros validados. "

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

# Conservamos el funcionamiento del calendario
# existente, que registra varios dias de golpe.
#
# Los periodos deben pasar por save()
# individualmente para validar sus intervalos.
        objs = list(objs)

        if any(

            registro.fecha_fin is not None

            for registro in objs

        ):

            raise ValidationError(

                "Los registros por periodos deben "

                "guardarse individualmente mediante save()."

            )

        sumas_nuevas = defaultdict(

            lambda: Decimal("0.00")

        )

        for registro in objs:

            clave = (

                registro.investigador_id,

                registro.fecha,

            )

            sumas_nuevas[clave] += _horas_validas(

                registro.horas

            )

        for (investigador_id, fecha), nuevas in sumas_nuevas.items():

            if investigador_id is None or fecha is None:

                continue

            existentes = self.model.objects.filter(

                investigador_id=investigador_id,

                fecha=fecha,

                fecha_fin__isnull=True,

            ).aggregate(

                total=Sum("horas")

            )["total"] or Decimal("0.00")

            if existentes + nuevas > MAX_HORAS_DIA:

                raise ValidationError(

                    f"El {fecha:%d/%m/%Y} se superan "

                    "las 24 horas totales del investigador "

                    "en registros de un solo día."

                )

        for registro in objs:

# Comprueba si existe un registro validado
# de esta tarea que cubra la misma fecha.
            validados = self.model.objects.filter(

                investigador_id=registro.investigador_id,

                tarea_id=registro.tarea_id,

                validado=True,

                fecha__lte=registro.fecha,

            ).filter(

                Q(

                    fecha_fin__isnull=True,

                    fecha=registro.fecha

                )

                |

                Q(

                    fecha_fin__gte=registro.fecha

                )

            )

            if validados.exists():

                raise ValidationError(

                    "Ya existen horas validadas "

                    "para esta tarea y fecha."

                )

# Comprobacion de cierres mensuales.
            if (

                registro.tarea_id

                and registro.investigador_id

                and registro.fecha

            ):

                cerrado = CierreMensualHoras.objects.filter(

                    proyecto_id=registro.tarea.proyecto_id,

                    investigador_id=registro.investigador_id,

                    anio=registro.fecha.year,

                    mes=registro.fecha.month,

                ).exists()

                if cerrado:

                    raise ValidationError(

                        "El mes ya está cerrado en este proyecto. "

                        "Solicita su reapertura."

                    )

        # El calendario utiliza bulk_create: comprobar el lote completo.
        from .control_mensual import verificar_total_mensual

        agrupados = defaultdict(lambda: Decimal("0.00"))

        for registro in objs:

            if registro.investigador_id and registro.fecha:

                clave = (registro.investigador_id, registro.fecha.year, registro.fecha.month)

                agrupados[clave] += _horas_validas(registro.horas)

        for (investigador_id, anio, mes), horas_nuevas in agrupados.items():

            verificar_total_mensual(investigador_id, anio, mes, horas_nuevas)

        return super().bulk_create(

            objs, *args, **kwargs

        )

    def bulk_update(self, objs, fields, batch_size=None):

        protegidos = {

            "horas",

            "fecha",

            "fecha_fin",

            "investigador",

            "investigador_id",

            "tarea",

            "tarea_id",

        }

        if protegidos.intersection(fields):

            raise ValidationError(

                "No se pueden modificar horas o fechas "

                "en bloque; edita los registros pendientes "

                "individualmente."

            )

        claves = [

            obj.pk

            for obj in objs

            if obj.pk is not None

        ]

        if claves and self.model.objects.filter(

            pk__in=claves,

            validado=True

        ).exists():

            raise ValidationError(

                "No se pueden modificar registros "

                "validados en bloque."

            )

        return super().bulk_update(

            objs,

            fields,

            batch_size=batch_size

        )

# ==========================================
# REGISTROS DE HORAS
# ==========================================
class RegistroHoras(models.Model):

# Fecha puntual o inicio del periodo.
    fecha = models.DateField(

        verbose_name="Fecha de trabajo"

    )

# NUEVO:
# NULL = registro de un solo dia.
# Con valor = final de un periodo.
    fecha_fin = models.DateField(

        null=True,

        blank=True,

        verbose_name="Fecha final del periodo"

    )

    horas = models.DecimalField(

        max_digits=5,

        decimal_places=2,

        validators=[

            MinValueValidator(Decimal("0.01"))

        ],

        verbose_name="Horas trabajadas",

    )

    descripcion = models.TextField(

        blank=True,

        verbose_name="Descripción del trabajo"

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

        default=False,

        db_index=True,

        verbose_name="Validado"

    )

    validado_por = models.ForeignKey(

        "usuarios.Usuario",

        on_delete=models.PROTECT,

        null=True,

        blank=True,

        related_name="registros_horas_validados",

        verbose_name="Validado por"

    )

    fecha_validacion = models.DateTimeField(

        null=True,

        blank=True,

        verbose_name="Fecha de validación"

    )

    objects = RegistroHorasQuerySet.as_manager()

    class Meta:

        verbose_name = "Registro de Horas"

        verbose_name_plural = "Registros de Horas"

        ordering = ["-fecha"]

    def __str__(self):

        if self.fecha_fin:

            periodo = (

                f"{self.fecha} a {self.fecha_fin}"

            )

        else:

            periodo = str(self.fecha)

        return (

            f"{self.investigador} - "

            f"{self.tarea.nombre} - "

            f"{periodo}"

        )

    def clean(self):

        super().clean()

        if self.fecha and self.fecha_fin:

            if self.fecha_fin < self.fecha:

                raise ValidationError({

                    "fecha_fin":

                    "La fecha final no puede ser "

                    "anterior a la inicial."

                })

# Cada registro pertenece a un unico mes.
# Los periodos entre meses se guardan
# como varios registros independientes.
            if (

                self.fecha_fin.year != self.fecha.year

                or

                self.fecha_fin.month != self.fecha.month

            ):

                raise ValidationError({

                    "fecha_fin":

                    "Cada registro debe pertenecer "

                    "a un solo mes. Divide el periodo "

                    "en varios tramos."

                })

    def save(self, *args, **kwargs):

# Si inicio y fin coinciden, se guarda
# como un registro puntual.
        if (

            self.fecha_fin is not None

            and self.fecha_fin == self.fecha

        ):

            self.fecha_fin = None

            if kwargs.get("update_fields") is not None:

                kwargs["update_fields"] = (

                    set(kwargs["update_fields"])

                    | {"fecha_fin"}

                )

# Validacion del intervalo.
        self.clean()

        es_periodo = self.fecha_fin is not None

        horas_actuales = _horas_validas(

            self.horas,

            es_periodo=es_periodo

        )

# No modificar registros validados.
        if self.pk and RegistroHoras.objects.filter(

            pk=self.pk,

            validado=True

        ).exists():

            raise ValidationError(

                "Estas horas ya están validadas. "

                "Solo se podrán modificar si "

                "un administrador las reabre previamente."

            )

# Evitar solapamientos con registros validados
# para el mismo investigador y tarea.
        if (

            self.investigador_id

            and self.tarea_id

            and self.fecha

        ):

            final = self.fecha_fin or self.fecha

            validados = RegistroHoras.objects.filter(

                investigador_id=self.investigador_id,

                tarea_id=self.tarea_id,

                validado=True,

                fecha__lte=final,

            ).exclude(

                pk=self.pk

            ).filter(

                Q(

                    fecha_fin__isnull=True,

                    fecha__gte=self.fecha

                )

                |

                Q(

                    fecha_fin__gte=self.fecha

                )

            )

            if validados.exists():

                raise ValidationError(

                    "Ya existe un registro validado "

                    "para esta tarea que coincide "

                    "con alguna fecha del periodo."

                )

# Comprobar cierres mensuales.
        if (

            self.tarea_id

            and self.investigador_id

            and self.fecha

        ):

            cerrado = CierreMensualHoras.objects.filter(

                proyecto_id=self.tarea.proyecto_id,

                investigador_id=self.investigador_id,

                anio=self.fecha.year,

                mes=self.fecha.month,

            ).exists()

            if cerrado:

                raise ValidationError(

                    "Este mes está cerrado para el proyecto. "

                    "Solicita su reapertura a un administrador."

                )

# Para registros puntuales mantenemos
# el control diario existente.
#
# Para periodos NO aplicamos 24 horas
# a la fecha de inicio, ya que las horas
# son el total del intervalo.
        if (

            not es_periodo

            and self.investigador_id

            and self.fecha

        ):

            existentes = RegistroHoras.objects.filter(

                investigador_id=self.investigador_id,

                fecha=self.fecha,

                fecha_fin__isnull=True,

            ).exclude(

                pk=self.pk

            ).aggregate(

                total=Sum("horas")

            )["total"] or Decimal("0.00")

            if existentes + horas_actuales > MAX_HORAS_DIA:

                raise ValidationError(

                    f"El {self.fecha:%d/%m/%Y} se superan "

                    "las 24 horas registradas en ese día, "

                    "sumando todos sus proyectos."

                )

        # Control de suma mensual compartido por horas diarias y periodos.
        if self.investigador_id and self.fecha:

            from .control_mensual import verificar_total_mensual

            verificar_total_mensual(

                self.investigador_id, self.fecha.year, self.fecha.month,

                horas_actuales, excluir_pk=self.pk

            )

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):

        if (

            self.validado

            or RegistroHoras.objects.filter(

                pk=self.pk,

                validado=True

            ).exists()

        ):

            raise ValidationError(

                "No se pueden eliminar horas validadas."

            )

        return super().delete(*args, **kwargs)

# ==========================================
# CIERRES MENSUALES DE HORAS
# ==========================================
class CierreMensualHoras(models.Model):

    """Cierre mensual por proyecto e investigador."""

    investigador = models.ForeignKey(

        "usuarios.Investigador",

        on_delete=models.PROTECT

    )

    proyecto = models.ForeignKey(

        "proyectos.Proyecto",

        on_delete=models.PROTECT

    )

    anio = models.PositiveIntegerField()

    mes = models.PositiveSmallIntegerField()

    validado_por = models.ForeignKey(

        "usuarios.Usuario",

        on_delete=models.PROTECT

    )

    fecha_validacion = models.DateTimeField(

        auto_now_add=True

    )

    class Meta:

        verbose_name = "Cierre mensual de horas"

        verbose_name_plural = "Cierres mensuales de horas"

        constraints = [

            models.UniqueConstraint(

                fields=[

                    "investigador",

                    "proyecto",

                    "anio",

                    "mes"

                ],

                name="cierre_horas_unico_mes_proyecto_investigador"

            )

        ]

    def __str__(self):

        return (

            f"{self.investigador} - "

            f"{self.proyecto} - "

            f"{self.mes}/{self.anio}"

        )

# ==========================================
# HISTORIAL DE VALIDACION DE HORAS
# ==========================================
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

    accion = models.CharField(

        max_length=12,

        choices=ACCIONES

    )

    usuario = models.ForeignKey(

        "usuarios.Usuario",

        on_delete=models.PROTECT

    )

    fecha = models.DateTimeField(

        auto_now_add=True

    )

    motivo = models.TextField(

        blank=True

    )

    class Meta:

        verbose_name = "Historial de validación de horas"

        verbose_name_plural = "Historiales de validación de horas"

        ordering = ["-fecha"]

    def __str__(self):

        return (

            f"{self.get_accion_display()} - "

            f"{self.registro_id}"

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

        validators=[

            MinValueValidator(Decimal("0.01"))

        ],

        verbose_name="Horas previstas"

    )

    proyecto = models.ForeignKey(

        "proyectos.Proyecto",

        on_delete=models.PROTECT,

        verbose_name="Proyecto"

    )

    tarea_padre = models.ForeignKey(

        "self",

        on_delete=models.PROTECT,

        null=True,

        blank=True,

        related_name="subtareas",

        verbose_name="Tarea principal"

    )

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

        return (

            f"{self.nombre} - "

            f"{self.proyecto.nombre}"

        )

    def clean(self):

        super().clean()

        errores = {}

        if (

            self.fecha_inicio

            and self.fecha_fin

            and self.fecha_fin < self.fecha_inicio

        ):

            errores["fecha_fin"] = (

                "La fecha de fin no puede ser "

                "anterior a la fecha de inicio."

            )

        if self.tarea_padre_id:

            if (

                self.pk

                and self.tarea_padre_id == self.pk

            ):

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

# ==========================================
# COMENTARIOS INDIVIDUALES DE TAREAS
# ==========================================
class ComentarioTarea(models.Model):

    """Entrada del historial de comentarios de una tarea."""

    tarea = models.ForeignKey(

        "Tarea",

        on_delete=models.PROTECT,

        related_name="comentarios_individuales",

        verbose_name="Tarea"

    )

    autor = models.ForeignKey(

        "usuarios.Usuario",

        on_delete=models.PROTECT,

        related_name="comentarios_de_tareas",

        verbose_name="Autor"

    )

    contenido = models.TextField(

        verbose_name="Comentario"

    )

    fecha_creacion = models.DateTimeField(

        default=timezone.now,

        editable=False,

        verbose_name="Fecha de creación"

    )

    class Meta:

        verbose_name = "Comentario de tarea"

        verbose_name_plural = "Comentarios de tareas"

        ordering = ["fecha_creacion", "pk"]

    def __str__(self):

        return (

            f"Comentario de {self.autor} "

            f"en la tarea {self.tarea_id}"

        )
