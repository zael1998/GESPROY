
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Investigador


Usuario = get_user_model()


# ==========================================
# CREAR INVESTIGADOR
# ==========================================

class CrearInvestigadorForm(forms.ModelForm):

    # CONTRASEÑA
    password1 = forms.CharField(
        label="Clave",
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
        required=True
    )

    # REPETIR CONTRASEÑA
    password2 = forms.CharField(
        label="Repetir clave",
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"}
        ),
        required=True
    )

    # ADMINISTRADOR: DESPLEGABLE SÍ / NO
    is_staff = forms.TypedChoiceField(
        label="Administrador",
        choices=[
            ("False", "No"),
            ("True", "Sí"),
        ],
        coerce=lambda valor: valor == "True",
        widget=forms.Select(),
        initial="False",
        required=True
    )

    class Meta:
        model = Usuario

        fields = [
            "last_name",
            "first_name",
            "email",
            "username",
            "is_staff",
        ]

        labels = {
            "last_name": "Apellidos",
            "first_name": "Nombre",
            "email": "Correo electrónico",
            "username": "Usuario",
            "is_staff": "Administrador",
        }

        widgets = {
            "last_name": forms.TextInput(),
            "first_name": forms.TextInput(),
            "email": forms.EmailInput(),
            "username": forms.TextInput(),
        }

    # ==========================================
    # CAMPOS OBLIGATORIOS
    # ==========================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        campos_obligatorios = [
            "last_name",
            "first_name",
            "email",
            "username",
        ]

        for campo in campos_obligatorios:
            self.fields[campo].required = True

    # ==========================================
    # VALIDAR CORREO ELECTRÓNICO
    # ==========================================

    def clean_email(self):

        email = self.cleaned_data["email"].strip()

        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe un usuario con este correo electrónico."
            )

        return email

    # ==========================================
    # VALIDAR CONTRASEÑA
    # ==========================================

    def clean_password1(self):

        password = self.cleaned_data["password1"]

        try:
            validate_password(password)
        except ValidationError as error:
            raise forms.ValidationError(error.messages)

        return password

    # ==========================================
    # COMPROBAR QUE LAS CLAVES COINCIDEN
    # ==========================================

    def clean(self):

        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error(
                "password2",
                "Las claves no coinciden."
            )

        return cleaned_data

    # ==========================================
    # GUARDAR USUARIO E INVESTIGADOR
    # ==========================================

    @transaction.atomic
    def save(self, commit=True):

        usuario = super().save(commit=False)

        # Guardar contraseña cifrada
        usuario.set_password(
            self.cleaned_data["password1"]
        )

        # Activar cuenta
        usuario.is_active = True

        # Sincronizar administrador y rol
        if usuario.is_staff:
            usuario.rol = "ADMIN"
        else:
            usuario.rol = "INVESTIGADOR"

        if commit:

            # Guardar usuario
            usuario.save()

            # Crear investigador vinculado al usuario
            Investigador.objects.create(
                usuario=usuario
            )

        return usuario
