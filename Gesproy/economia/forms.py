
from django import forms

from .models import (
    CategoriaEconomica,
    PartidaEconomica,
)


# ==========================================
# FORMULARIO DE PARTIDAS ECONÓMICAS
# ==========================================

class PartidaEconomicaForm(forms.ModelForm):

    class Meta:
        model = PartidaEconomica

        fields = [
            "categoria",
            "concepto",
            "importe",
            "entidad",
            "observaciones",
        ]

        labels = {
            "categoria": "Categoría y subcategoría",
            "concepto": "Concepto",
            "importe": "Importe previsto (€)",
            "entidad": "Entidad (opcional)",
            "observaciones": "Observaciones (opcional)",
        }

        widgets = {
            "categoria": forms.Select(
                attrs={"class": "eco-input"}
            ),
            "concepto": forms.TextInput(
                attrs={"class": "eco-input"}
            ),
            "importe": forms.NumberInput(
                attrs={
                    "class": "eco-input",
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "entidad": forms.TextInput(
                attrs={"class": "eco-input"}
            ),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "eco-input",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Solo se seleccionan subcategorías.
        self.fields["categoria"].queryset = (
            CategoriaEconomica.objects.filter(
                padre__isnull=False
            )
            .select_related("padre")
            .order_by(
                "tipo",
                "padre__orden",
                "orden",
                "codigo",
            )
        )

        self.fields["categoria"].label_from_instance = (
            lambda categoria: (
                f"{categoria.padre.nombre} / "
                f"{categoria.nombre}"
            )
        )


# ==========================================
# FORMULARIO DE CATEGORÍAS ECONÓMICAS
# ==========================================

class CategoriaEconomicaForm(forms.ModelForm):

    class Meta:
        model = CategoriaEconomica

        fields = [
            "codigo",
            "nombre",
            "tipo",
            "padre",
            "orden",
        ]

        labels = {
            "codigo": "Código",
            "nombre": "Nombre",
            "tipo": "Tipo de partida",
            "padre": "Categoría principal",
            "orden": "Orden de visualización",
        }

        widgets = {
            "codigo": forms.TextInput(
                attrs={
                    "class": "eco-input",
                    "placeholder": "Ejemplo: 1.6.1",
                }
            ),
            "nombre": forms.TextInput(
                attrs={
                    "class": "eco-input",
                    "placeholder": "Nombre de la categoría",
                }
            ),
            "tipo": forms.Select(
                attrs={"class": "eco-input"}
            ),
            "padre": forms.Select(
                attrs={"class": "eco-input"}
            ),
            "orden": forms.NumberInput(
                attrs={
                    "class": "eco-input",
                    "min": 0,
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        principales = CategoriaEconomica.objects.filter(
            padre__isnull=True
        )

        if self.instance.pk:
            principales = principales.exclude(
                pk=self.instance.pk
            )

        self.fields["padre"].queryset = principales.order_by(
            "tipo",
            "orden",
            "codigo",
        )

        self.fields["padre"].required = False

        self.fields["padre"].empty_label = (
            "Ninguna: categoría principal"
        )

        self.fields["padre"].help_text = (
            "Déjalo vacío para crear una categoría principal. "
            "Selecciona una existente para crear una subcategoría."
        )

    def clean(self):

        datos = super().clean()

        padre = datos.get("padre")
        tipo = datos.get("tipo")

        # Las subcategorías tienen que pertenecer
        # al mismo tipo que su categoría principal.
        if padre and tipo and padre.tipo != tipo:

            self.add_error(
                "tipo",
                "El tipo debe coincidir con el de "
                "la categoría principal.",
            )

        if self.instance.pk:

            anterior = CategoriaEconomica.objects.get(
                pk=self.instance.pk
            )

            tiene_hijas = CategoriaEconomica.objects.filter(
                padre_id=anterior.pk
            ).exists()

            tiene_partidas = PartidaEconomica.objects.filter(
                categoria_id=anterior.pk
            ).exists()

            if tiene_hijas and padre is not None:

                self.add_error(
                    "padre",
                    "No puedes convertir en subcategoría "
                    "una categoría que contiene otras.",
                )

            if tiene_hijas and tipo != anterior.tipo:

                self.add_error(
                    "tipo",
                    "No puedes cambiar el tipo de una "
                    "categoría con subcategorías.",
                )

            if tiene_partidas:

                if tipo != anterior.tipo:

                    self.add_error(
                        "tipo",
                        "No puedes cambiar el tipo porque "
                        "existen partidas asociadas.",
                    )

                padre_id = padre.pk if padre else None

                if padre_id != anterior.padre_id:

                    self.add_error(
                        "padre",
                        "No puedes mover una categoría "
                        "que ya contiene partidas.",
                    )

        return datos
