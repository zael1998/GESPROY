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
        
class EditarProyectoDefinicionForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = [
            "acronimo",
            "nombre",
            "enlace_proyecto",
            "fecha_final_prevista",
            "areas",
            "comentario",
            
        ]
        
        labels = {
            "acronimo": "Acrónimo",
            "nombre": "Nombre del proyecto",
            "enlace_proyecto": "Enlace al proyecto",
            "fecha_final_prevista": "Fecha prevista",
            "areas": "Áreas de investigación",
            "comentario": "Comentario",
           
        }
        
        widgets = {
            'fecha_final_prevista': forms.DateInput(
                attrs={'type': 'date'},
                format='%Y-%m-%d'
            ),
            'comentario': forms.Textarea(
                attrs={'rows': 3}
            ),
        }
        
    
class SolicitarProyectoForm(forms.ModelForm):

    class Meta:
        model = Proyecto

        fields = [
            "importe_solicitado",
            "porcentaje_subvencion",
            "tipo_proyecto",
            "fecha_solicitud",
            "organismo",
            "duracion",
            "tipo_participacion",
            "fecha_prevista_resolucion",
            "comentario",
        ]

        widgets = {
            "fecha_solicitud": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "fecha_prevista_resolucion": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        campos_obligatorios = [
            "importe_solicitado",
            "porcentaje_subvencion",
            "tipo_proyecto",
            "fecha_solicitud",
            "organismo",
            "duracion",
            "tipo_participacion",
        ]

        for campo in campos_obligatorios:
            self.fields[campo].required = True
