from django.db import models

class RegistroHoras(models.Model):
    fecha = models.DateField()
    horas = models.DecimalField(max_digits=5, decimal_places=2)
    descripcion = models.TextField()
    investigador = models.ForeignKey('usuarios.Investigador', on_delete=models.PROTECT)
    tarea = models.ForeignKey('Tarea', on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = "Registro de Horas"
        verbose_name_plural = "Registros de Horas"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.investigador} - {self.tarea.nombre} - {self.fecha}"
    
class Tarea(models.Model):
    nombre = models.CharField(max_length=100)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    horas_estimadas = models.DecimalField(max_digits=5, decimal_places=2)
    descripcion = models.TextField()
    tarea_padre = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    #Los responsables pueden ser tanto un investigador como un socio,
    #así que las relaciones son opcionales y se pueden dejar en blanco.
    responsable_investigador = models.ForeignKey(
        'usuarios.Investigador',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    
     
    finalizada = models.BooleanField(default=False)
    #los comentarios aparecen en las tareas?
    comentario = models.TextField(null= True, blank = True)
    proyecto = models.ForeignKey('proyectos.Proyecto', on_delete=models.PROTECT)  
    
    class Meta:
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        ordering = ['fecha_inicio']

    def __str__(self):
        return f"{self.nombre} - {self.proyecto.nombre}"
