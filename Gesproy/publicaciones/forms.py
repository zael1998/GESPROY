from django import forms
from .models import Publicacion
from .permisos import proyectos_permitidos


class PublicacionForm(forms.ModelForm):
    class Meta:
        model = Publicacion
        fields = ["archivo", "titulo", "autores", "referencia", "anio", "proyectos", "difusion"]
        widgets = {
            "autores": forms.Textarea(attrs={"rows": 2}),
            "referencia": forms.Textarea(attrs={"rows": 2}),
            "anio": forms.NumberInput(attrs={"min": 1900, "max": 2100}),
            "proyectos": forms.SelectMultiple(attrs={"size": 6}),
        }

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proyectos"].queryset = proyectos_permitidos(usuario).order_by("acronimo", "pk")
        self.fields["proyectos"].required = True
        self.fields["archivo"].required = self.instance.pk is None
        self.fields["archivo"].help_text = "Máximo 25 MB. PDF, Office, imágenes, texto o ZIP."

    def clean_proyectos(self):
        proyectos = self.cleaned_data["proyectos"]
        if not proyectos.exists():
            raise forms.ValidationError("Selecciona al menos un proyecto.")
        return proyectos