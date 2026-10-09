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
            "acronimo",
            "nombre",
            "organismo",
            "tipo_proyecto",
            "porcentaje_subvencion",
            "importe_solicitado",
            "importe_solicitado_cesga",
            "fecha_solicitud",
            "fecha_prevista_resolucion",
            "tipo_participacion",
            "duracion",
            "porcentaje_exito",
            "comentario",
        ]

        labels = {
            "acronimo": "Acrónimo",
            "nombre": "Nombre",
            "organismo": "Organismo",
            "tipo_proyecto": "Tipo Proyecto",
            "porcentaje_subvencion": "Porcentaje",
            "importe_solicitado": "Cantidad Total",
            "importe_solicitado_cesga": "Cantidad CESGA",
            "fecha_solicitud": "Fecha Solicitud",
            "fecha_prevista_resolucion": "Fecha Resolución",
            "tipo_participacion": "Participación",
            "duracion": "Duración",
            "porcentaje_exito": "Porcentaje Éxito",
            "comentario": "Comentario",
        }

        widgets = {
            "fecha_solicitud": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "fecha_prevista_resolucion": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "comentario": forms.Textarea(
                attrs={"rows": 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        campos_obligatorios = [
            "acronimo",
            "nombre",
            "organismo",
            "tipo_proyecto",
            "porcentaje_subvencion",
            "importe_solicitado",
            "fecha_solicitud",
            "tipo_participacion",
            "duracion",
        ]

        for campo in campos_obligatorios:
            self.fields[campo].required = True

class FinalizarProyectoDefinicionForm(forms.ModelForm):

    fecha_fin = forms.DateField(
        required=True,
        label="Fecha Fin",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d"
        )
    )

    class Meta:
        model = Proyecto

        fields = [
            "fecha_fin",
            "comentario",
        ]

        labels = {
            "comentario": "Comentario",
        }

        widgets = {
            "comentario": forms.Textarea(
                attrs={"rows": 3}
            ),
        }

