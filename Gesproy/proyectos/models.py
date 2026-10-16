
from django.db import models
from django.utils import timezone

class Organismo(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class TipoProyecto(models.Model):
    nombre = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Tipo de Proyecto"
        verbose_name_plural = "Tipos de Proyecto"

    def __str__(self):
        return self.nombre


class TipoParticipacion(models.Model):
    nombre = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Tipo de Participación"
        verbose_name_plural = "Tipos de Participación"

    def __str__(self):
        return self.nombre


class LineaInvestigacion(models.Model):
    nombre = models.CharField(max_length=100)

    presupuesto = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    class Meta:
        verbose_name = "Línea de Investigación"
        verbose_name_plural = "Líneas de Investigación"

    def __str__(self):
        return self.nombre


class Area(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Proyecto(models.Model):

    areas = models.ManyToManyField(
        Area,
        related_name='proyectos_por_area',
        blank=True
    )

    investigador_principal = models.ForeignKey(
        'usuarios.Investigador',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    nombre = models.CharField(max_length=100)

    acronimo = models.CharField(max_length=20)

    enlace_proyecto = models.URLField(
        null=True,
        blank=True,
        max_length=500
    )

    fecha_solicitud = models.DateField(
        null=True,
        blank=True
    )

    fecha_prevista_resolucion = models.DateField(
        null=True,
        blank=True
    )

    fecha_resolucion = models.DateField(
        null=True,
        blank=True
    )

    fecha_denegacion = models.DateField(
        null=True,
        blank=True
    )

    causa_denegacion = models.TextField(
        null=True,
        blank=True
    )

    importe_solicitado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    importe_solicitado_cesga = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null = True,
        blank = True
    )

    importe_concedido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    importe_concedido_cesga = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        null = True,
        blank = True
    )

    centro_concedente = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    porcentaje_subvencion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    porcentaje_exito = models.DecimalField(
    max_digits=5,
    decimal_places=2,
    null=True,
    blank=True
)

    duracion = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    comentario = models.TextField(
        null=True,
        blank=True
    )

    estado = models.CharField(
        max_length=20,
        choices=[
            ("DEFINICION", "En definición"),
            ("SOLICITADO", "Solicitado"),
            ("NEGOCIACION", "En negociación"),
            ("PROCESO", "En proceso"),
            ("FINALIZADO", "Finalizado"),
            ("DENEGADO", "Denegado")
        ],
        default="DEFINICION"
    )

    #En el manual aparece en concreto fecha de solicitud, fecha prevista de resolución,
    #fecha de resolución, fecha de inicio y fecha de finalizacón. Preguntar cuantas quiere

    fecha_inicio = models.DateField(
        null=True,
        blank=True
    )

    fecha_fin = models.DateField(
        null=True,
        blank=True
    )

    fecha_final_prevista = models.DateField(
        null=True,
        blank=True
    )

    pagado = models.BooleanField(default=False)

    organismo = models.ForeignKey(
        Organismo,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    tipo_proyecto = models.ForeignKey(
        TipoProyecto,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    tipo_participacion = models.ForeignKey(
        TipoParticipacion,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.nombre



class Asignacion(models.Model):

    linea_investigacion = models.ForeignKey(
        LineaInvestigacion,
        on_delete=models.PROTECT
    )

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.PROTECT
    )

    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    class Meta:
        verbose_name = "Asignación"
        verbose_name_plural = "Asignaciones"

        constraints = [
            models.UniqueConstraint(
                fields=["proyecto", "linea_investigacion"],
                name="asignacion_proyecto_linea_unica"
            )
        ]

    def __str__(self):
        return f"{self.linea_investigacion.nombre} - {self.proyecto.nombre}"



class Dedicacion(models.Model):

    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    fecha_inicio = models.DateField()

    fecha_fin = models.DateField(
        null=True,
        blank=True
    )

    investigador = models.ForeignKey(
        'usuarios.Investigador',
        on_delete=models.PROTECT
    )

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.PROTECT
    )
    validador = models.ForeignKey(
        "usuarios.Investigador",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dedicaciones_como_validador",
        verbose_name="Validador"
    )

    class Meta:
        verbose_name = "Dedicación"
        verbose_name_plural = "Dedicaciones"

    def __str__(self):
        return f"{self.investigador} - {self.proyecto.nombre}"


class Carpeta(models.Model):

    nombre = models.CharField(max_length=100)

    carpeta_padre = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.PROTECT
    )

    def __str__(self):
        return self.nombre


class Archivo(models.Model):

    nombre = models.CharField(max_length=100)

    ruta_subida = models.FileField(
        upload_to='archivos/'
    )

    fecha_subida = models.DateField()

    tamaño = models.PositiveIntegerField()

    comentario = models.TextField()

    visible = models.BooleanField(default=True)

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.PROTECT
    )

    #La carpeta es opcional, ya que un archivo puede estar en la raíz del proyecto o dentro de una carpeta específica.

    carpeta = models.ForeignKey(
        Carpeta,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.nombre


class EstudioEconomico(models.Model):

    proyecto = models.OneToOneField(
        Proyecto,
        on_delete=models.PROTECT
    )

    def __str__(self):
        return f"Estudio económico - {self.proyecto.nombre}"

    #¿Cómo quiere que representemos en el modelo el estudio económico y las facturas/ingresos/gastos de un proyecto?
    #Yo supuse que luego habria un movimiento económico que puede ser un ingreso o un gasto,
    #y que cada proyecto tiene un estudio económico asociado.


class MovimientoEconomico(models.Model):

    concepto = models.CharField(max_length=100)

    tipo_movimiento = models.CharField(max_length=20)

    fecha = models.DateField()

    importe = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = "Movimiento económico"
        verbose_name_plural = "Movimientos económicos"

    def __str__(self):
        return self.concepto


# ==========================================
# SOCIOS
# ==========================================

class Socio(models.Model):

    nombre_empresa = models.CharField(
        max_length=100
    )

    direccion = models.TextField(
        blank=True
    )

    def __str__(self):
        return self.nombre_empresa


# ==========================================
# CONTACTOS DE SOCIOS
# ==========================================

class ContactoSocio(models.Model):

    nombre = models.CharField(
        max_length=100
    )

    apellido = models.CharField(
        max_length=100
    )

    email = models.EmailField()

    # Teléfono principal
    telefono = models.CharField(
        max_length=20,
        blank=True
    )

    # Teléfono secundario
    telefono2 = models.CharField(
        max_length=20,
        blank=True
    )

    fax = models.CharField(
        max_length=20,
        blank=True
    )

    socio = models.ForeignKey(
        Socio,
        on_delete=models.PROTECT
    )

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"


class ParticipacionSocio(models.Model):

    porcentaje_participacion = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    importe = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    
    investigador_responsable = models.ForeignKey(
        "usuarios.Investigador",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="participaciones_socios_responsable",
        verbose_name="Investigador responsable"
    )

    socio = models.ForeignKey(
        Socio,
        on_delete=models.PROTECT
    )

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = "Participación de Socio"
        verbose_name_plural = "Participaciones de Socios"

    def __str__(self):
        return f"{self.socio.nombre_empresa} - {self.proyecto.nombre}"
    

# ==========================================
# HISTORIAL DE DENEGACIONES DE PROYECTOS
# ==========================================

class DenegacionProyecto(models.Model):

    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        on_delete=models.CASCADE,
        related_name="denegaciones",
        verbose_name="Proyecto"
    )

    fecha = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de denegación"
    )

    causa = models.TextField(
        verbose_name="Causa de la denegación"
    )

    class Meta:
        verbose_name = "Denegación de proyecto"
        verbose_name_plural = "Denegaciones de proyectos"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.proyecto.acronimo} - {self.fecha:%d/%m/%Y}"
    

# ==========================================
# CALENDARIO LABORAL
# ==========================================

class Festivo(models.Model):

    AMBITOS = [
        ("nacional", "Nacional"),
        ("autonomico", "Autonómico"),
        ("provincial", "Provincial"),
        ("local", "Local"),
        ("centro", "Del centro"),
    ]

    fecha = models.DateField(
        unique=True,
        verbose_name="Fecha"
    )

    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del festivo"
    )

    ambito = models.CharField(
        max_length=20,
        choices=AMBITOS,
        default="centro",
        verbose_name="Ámbito"
    )

    fuente = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Fuente"
    )

    url_fuente = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Enlace a la fuente"
    )

    importado = models.BooleanField(
        default=False
    )

    editado_manualmente = models.BooleanField(
        default=False
    )

    class Meta:
        verbose_name = "Festivo"
        verbose_name_plural = "Festivos"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} - {self.nombre}"


