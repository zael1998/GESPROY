"""Cuenta personal: solo administradores modifican sus propios datos y clave.

Los investigadores no se pueden autoeditar. Su ficha y contraseña las
administra una persona autorizada desde Gestión de usuarios.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .models import Usuario


class EditarPerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "cuenta-input", "autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"class": "cuenta-input", "autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"class": "cuenta-input", "autocomplete": "email"}),
        }

    def clean_first_name(self):
        valor = self.cleaned_data["first_name"].strip()
        if not valor:
            raise forms.ValidationError("Introduce tu nombre.")
        return valor

    def clean_last_name(self):
        valor = self.cleaned_data["last_name"].strip()
        if not valor:
            raise forms.ValidationError("Introduce tus apellidos.")
        return valor


def _exigir_administrador(usuario):
    if not (usuario.is_authenticated and usuario.is_active and
            (usuario.is_staff or usuario.is_superuser)):
        raise PermissionDenied(
            "Tus datos personales y tu contraseña los gestiona un administrador."
        )


@login_required
def editar_perfil(request):
    """El admin puede editar sus propios datos, pero no cambiar su rol aquí."""
    _exigir_administrador(request.user)
    formulario = EditarPerfilForm(request.POST or None, instance=request.user)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Tus datos personales se han actualizado.")
        return redirect("mi_perfil")

    return render(request, "usuarios/editar_perfil.html", {
        "formulario": formulario,
    })


@login_required
def cambiar_clave(request):
    """Solo admins pueden cambiar su propia contraseña con la actual."""
    _exigir_administrador(request.user)
    formulario = PasswordChangeForm(
        user=request.user,
        data=request.POST if request.method == "POST" else None,
    )
    for campo in formulario.fields.values():
        campo.widget.attrs.update({"class": "cuenta-input"})

    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        update_session_auth_hash(request, usuario)
        messages.success(request, "La contraseña se ha actualizado correctamente.")
        return redirect("mi_cambiar_clave")

    return render(request, "usuarios/cambiar_clave.html", {
        "formulario": formulario,
    })