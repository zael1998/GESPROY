from django.db import models

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
    presupuesto = models.DecimalField(max_digits=10, decimal_places=2)
    
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
        related_name='proyectos_por_area'
    )
    investigador_principal = models.ForeignKey(
        'usuarios.Investigador',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    nombre = models.CharField(max_length=100)
    acronimo = models.CharField(max_length=20)
    fecha_solicitud = models.DateField(null = True, blank = True)
    fecha_prevista_resolucion = models.DateField(null=True, blank=True)
    fecha_resolucion = models.DateField(null=True, blank=True)
    fecha_denegacion = models.DateField(null=True, blank=True)
    causa_denegacion = models.TextField(null=True, blank=True)
    importe_solicitado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    importe_concedido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    centro_concedente = models.CharField(max_length=100, null=True, blank=True)
    porcentaje_subvencion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    duracion = models.PositiveIntegerField(null=True, blank=True)
    comentario = models.TextField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=[
        ("DEFINICION", "En definición"),
        ("SOLICITADO", "Solicitado"),
        ("NEGOCIACION", "En negociación"),
        ("PROCESO", "En proceso"),
        ("FINALIZADO", "Finalizado"),
        ("DENEGADO", "Denegado")
    ])
    #En el manual aparece en concreto fecha de solicitud, fecha prevista de resolución,
    #fecha de resolución, fecha de inicio y fecha de finalizacón. Preguntar cuantas quiere
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    pagado = models.BooleanField(default=False)
    organismo = models.ForeignKey(Organismo, on_delete=models.PROTECT)
    tipo_proyecto = models.ForeignKey(TipoProyecto, on_delete=models.PROTECT)
    tipo_participacion = models.ForeignKey(TipoParticipacion, on_delete=models.PROTECT)

    def __str__(self):

        return self.nombre

class Asignacion(models.Model):
    linea_investigacion = models.ForeignKey(LineaInvestigacion, on_delete=models.PROTECT)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    
    class Meta:
        verbose_name = "Asignación"
        verbose_name_plural = "Asignaciones"

    def __str__(self):

        return f"{self.linea_investigacion.nombre} - {self.proyecto.nombre}"

class Dedicacion(models.Model):
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    #Pueden ser un investigador y socio ser responsables de los proyectos?
    #Pueden ser responsables mas de un investigador o mas de un socio?
    #Pueden ser responsables diferentes los de una tarea y los de un proyecto?

    investigador = models.ForeignKey('usuarios.Investigador', on_delete=models.PROTECT)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = "Dedicación"
        verbose_name_plural = "Dedicaciones"

    def __str__(self):

        return f"{self.investigador} - {self.proyecto.nombre}"

class Carpeta(models.Model):
    nombre = models.CharField(max_length=100)
    carpeta_padre = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)

    def __str__(self):

        return self.nombre

class Archivo(models.Model):
    nombre = models.CharField(max_length=100)
    ruta_subida = models.FileField(upload_to='archivos/')
    fecha_subida = models.DateField()
    tamaño = models.PositiveIntegerField()
    comentario = models.TextField()
    visible = models.BooleanField(default=True)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)
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
    proyecto = models.OneToOneField(Proyecto, on_delete=models.PROTECT)

    def __str__(self):

        return f"Estudio económico - {self.proyecto.nombre}"
    #¿Cómo quiere que representemos en el modelo el estudio económico y las facturas/ingresos/gastos de un proyecto?
    #Yo supuse que luego habria un movimiento económico que puede ser un ingreso o un gasto,
    # y que cada proyecto tiene un estudio económico asociado.
class MovimientoEconomico(models.Model):
    concepto = models.CharField(max_length=100)
    tipo_movimiento = models.CharField(max_length=20)
    fecha = models.DateField()
    importe = models.DecimalField(max_digits=10, decimal_places=2)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)
    
    class Meta:
        verbose_name= "Movimiento económico"
        verbose_name_plural = "Movimientos económicos"

    def __str__(self):

        return self.concepto

class Socio(models.Model):
    nombre_empresa = models.CharField(max_length=100)
   
    def __str__(self):

        return self.nombre_empresa
    #me tome la libertad de crear algunos campos que no aparecen en el manual como tal pero 
    #me parece que son los que se suelen usar en modelos así
class ContactoSocio(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=20)
    socio = models.ForeignKey(Socio, on_delete=models.PROTECT)
    
    def __str__(self):

        return self.nombre

class ParticipacionSocio(models.Model):    
    porcentaje_participacion = models.DecimalField(max_digits=5, decimal_places=2)
    importe = models.DecimalField(max_digits=10, decimal_places=2)
    socio = models.ForeignKey(Socio, on_delete=models.PROTECT)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = "Participación de Socio"
        verbose_name_plural = "Participaciones de Socios"

    def __str__(self):

        return f"{self.socio.nombre_empresa} - {self.proyecto.nombre}"