from django import forms
from .models import Proyecto


class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = [
            'acronimo',
            'nombre',
            'areas',
            'investigador_principal',
            'comentario',
        ]