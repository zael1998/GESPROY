
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# ==========================================
# CATEGORÍAS ECONÓMICAS
# ==========================================

class CategoriaEconomica(models.Model):

    TIPOS = [
        ("COSTE", "Coste"),
        ("INGRESO", "Ingreso"),
    ]

    codigo = models.CharField(
        max_length=15,
        unique=True,
    )

    nombre = models.CharField(
        max_length=120,
    )

    tipo = models.CharField(
        max_length=10,
        choices=TIPOS,
    )

    padre = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subcategorias",
    )

    orden = models.PositiveSmallIntegerField(
        default=0,
    )

    class Meta:
        ordering = ["tipo", "orden", "codigo"]
        verbose_name = "Categoría económica"
        verbose_name_plural = "Categorías económicas"

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


# ==========================================
# ESTUDIOS ECONÓMICOS
# ==========================================

class EstudioEconomico(models.Model):

    FASES = [
        ("INICIO", "Inicio"),
        ("NEGOCIACION", "Negociación"),
        ("REPLANTEO", "Replanteo"),
    ]

    ESTADOS = [
        ("BORRADOR", "Borrador"),
        ("CERRADO", "Cerrado"),
    ]

    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        on_delete=models.PROTECT,
        related_name="estudios_economicos",
    )

    fase = models.CharField(
        max_length=12,
        choices=FASES,
    )

    version = models.PositiveIntegerField(
        default=1,
    )

    estado = models.CharField(
        max_length=10,
        choices=ESTADOS,
        default="BORRADOR",
    )

    fecha = models.DateField(
        default=timezone.localdate,
    )

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="estudios_economicos_creados",
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["proyecto_id", "fase", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["proyecto", "fase", "version"],
                name="estudio_economico_fase_version_unicos",
            ),
        ]

    def __str__(self):
        return (
            f"{self.proyecto} · "
            f"{self.get_fase_display()} "
            f"v{self.version}"
        )


# ==========================================
# PARTIDAS ECONÓMICAS
# ==========================================

class PartidaEconomica(models.Model):

    estudio = models.ForeignKey(
        EstudioEconomico,
        on_delete=models.CASCADE,
        related_name="partidas",
    )

    categoria = models.ForeignKey(
        CategoriaEconomica,
        on_delete=models.PROTECT,
    )

    concepto = models.CharField(
        max_length=200,
    )

    importe = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    entidad = models.CharField(
        max_length=120,
        blank=True,
    )

    observaciones = models.TextField(
        blank=True,
    )

    class Meta:
        ordering = ["categoria__orden", "pk"]

    def __str__(self):
        return f"{self.concepto} · {self.importe} €"
