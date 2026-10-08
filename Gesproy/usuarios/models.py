from django.db import models

from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):

    rol = models.CharField(
        max_length=20,
        choices=[
            ('INVESTIGADOR', 'Investigador'),
            ('ADMIN', 'Administrador')
        ]
    )


class Investigador(models.Model):

    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = "Investigador"
        verbose_name_plural = "Investigadores"

    def __str__(self):
        return f"{self.usuario.first_name} {self.usuario.last_name}"