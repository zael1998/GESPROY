"""Gestión de cuentas de Gesproy.

Niveles efectivos:
- superadministrador técnico: usuario.is_superuser
- administrador funcional: usuario.is_staff, sin is_superuser
- investigador: no es staff ni superuser

El campo Usuario.rol de Gesproy se sincroniza siempre en las acciones
administrativas de este módulo. Jamás se toma el rol enviado por POST
como autorización para modificar usuarios privilegiados.
"""

import logging

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from proyectos.models import Dedicacion
from .models import Investigador, Usuario

logger = logging.getLogger(__name__)

ROLES = (("INVESTIGADOR", "Investigador"), ("ADMIN", "Administrador"))


def _exigir_administrador(usuario):
    if not (usuario.is_authenticated and usuario.is_active and
            (usuario.is_staff or usuario.is_superuser)):
        raise PermissionDenied("Solo los administradores pueden gestionar usuarios.")


def _puede_gestionar_objetivo(actor, objetivo):
    """Solo un superadmin modifica administradores; ninguna cuenta técnica aquí."""
    if objetivo.is_superuser:
        return False  # Las cuentas técnicas se gestionan desde /admin/ o consola.
    if actor.is_superuser:
        return True
    return not (objetivo.is_staff or objetivo.rol == "ADMIN")


def _exigir_gestion_objetivo(actor, objetivo):
    if not _puede_gestionar_objetivo(actor, objetivo):
        raise PermissionDenied("No tienes permiso para administrar esta cuenta.")


def _estilizar_formulario(formulario):
    for campo in formulario.fields.values():
        clases = campo.widget.attrs.get("class", "")
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs["class"] = f"{clases} gu-check".strip()
        else:
            campo.widget.attrs["class"] = f"{clases} gu-input".strip()


class CrearUsuarioForm(UserCreationForm):
    rol_cuenta = forms.ChoiceField(choices=ROLES, label="Rol de la cuenta")

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "first_name", "last_name", "email")
        labels = {
            "username": "Nombre de usuario",
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
        }

    def __init__(self, *args, es_superadmin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["rol_cuenta"].choices = (
            ROLES if es_superadmin else ROLES[:1]
        )
        self.fields["rol_cuenta"].initial = "INVESTIGADOR"
        _estilizar_formulario(self)


class EditarUsuarioForm(forms.ModelForm):
    rol_cuenta = forms.ChoiceField(choices=ROLES, label="Rol de la cuenta")

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email", "is_active")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
            "is_active": "Cuenta activa (puede iniciar sesión)",
        }

    def __init__(self, *args, es_superadmin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["rol_cuenta"].choices = (
            ROLES if es_superadmin else ROLES[:1]
        )
        self.fields["rol_cuenta"].initial = (
            "ADMIN" if self.instance.is_staff else "INVESTIGADOR"
        )
        _estilizar_formulario(self)


@login_required
@require_http_methods(["GET"])
def gestion_usuarios(request):
    _exigir_administrador(request.user)

    busqueda = request.GET.get("q", "").strip()[:100]
    cuentas = Usuario.objects.all().order_by("last_name", "first_name", "username", "pk")
    if busqueda:
        cuentas = cuentas.filter(
            Q(username__icontains=busqueda)
            | Q(first_name__icontains=busqueda)
            | Q(last_name__icontains=busqueda)
            | Q(email__icontains=busqueda)
        )

    paginador = Paginator(cuentas, 20)
    pagina = paginador.get_page(request.GET.get("page", 1))
    for cuenta in pagina:
        cuenta.puede_administrarse = _puede_gestionar_objetivo(request.user, cuenta)

    return render(request, "usuarios/gestion_usuarios.html", {
        "pagina": pagina,
        "busqueda": busqueda,
    })


@login_required
@require_http_methods(["GET", "POST"])
def crear_usuario(request):
    _exigir_administrador(request.user)
    formulario = CrearUsuarioForm(
        request.POST or None,
        es_superadmin=request.user.is_superuser,
    )

    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            usuario = formulario.save(commit=False)
            rol = formulario.cleaned_data["rol_cuenta"]
            # Seguridad: un admin normal nunca crea otros administradores.
            if rol == "ADMIN" and not request.user.is_superuser:
                raise PermissionDenied("Solo el superadministrador puede nombrar administradores.")
            usuario.rol = rol
            usuario.is_staff = rol == "ADMIN"
            usuario.is_superuser = False  # Solo se crea una cuenta técnica por consola.
            usuario.is_active = True
            usuario.save()
            Investigador.objects.get_or_create(usuario=usuario)

        logger.warning("GESPROY: %s creó la cuenta %s con rol %s", request.user.pk, usuario.pk, rol)
        messages.success(request, "Cuenta creada correctamente.")
        return redirect("gestion_usuarios")

    return render(request, "usuarios/formulario_usuario.html", {
        "formulario": formulario,
        "es_creacion": True,
        "titulo": "Crear usuario",
    })


@login_required
@require_http_methods(["GET", "POST"])
def editar_usuario(request, usuario_id):
    _exigir_administrador(request.user)
    objetivo = get_object_or_404(Usuario, pk=usuario_id)
    _exigir_gestion_objetivo(request.user, objetivo)

    formulario = EditarUsuarioForm(
        request.POST or None,
        instance=objetivo,
        es_superadmin=request.user.is_superuser,
    )

    if request.method == "POST" and formulario.is_valid():
        rol_nuevo = formulario.cleaned_data["rol_cuenta"]
        # Volver a validar la autorización antes de guardar.
        _exigir_gestion_objetivo(request.user, objetivo)
        if rol_nuevo == "ADMIN" and not request.user.is_superuser:
            raise PermissionDenied("No puedes conceder el rol de administrador.")
        if objetivo.pk == request.user.pk and not formulario.cleaned_data["is_active"]:
            formulario.add_error("is_active", "No puedes desactivar tu propia cuenta.")

        # No dejar asignaciones a un validador que deja de poder validar.
        pasa_a_admin = rol_nuevo == "ADMIN"
        desactiva = not formulario.cleaned_data["is_active"]
        if (pasa_a_admin or desactiva) and Dedicacion.objects.filter(
            validador__usuario=objetivo
        ).exists():
            formulario.add_error(
                "rol_cuenta" if pasa_a_admin else "is_active",
                "Esta persona todavía tiene validaciones asignadas. "
                "Cambia primero el validador de esas dedicaciones.",
            )

        if not formulario.errors:
            with transaction.atomic():
                objetivo = formulario.save(commit=False)
                rol_anterior = "ADMIN" if objetivo.is_staff else "INVESTIGADOR"
                objetivo.rol = rol_nuevo
                objetivo.is_staff = rol_nuevo == "ADMIN"
                objetivo.is_superuser = False
                objetivo.save()
                investigador, _ = Investigador.objects.get_or_create(usuario=objetivo)
                if rol_nuevo == "ADMIN" and investigador.puede_validar_horas:
                    investigador.puede_validar_horas = False
                    investigador.save(update_fields=["puede_validar_horas"])

            logger.warning(
                "GESPROY: %s modificó usuario %s, rol %s -> %s, activo=%s",
                request.user.pk, objetivo.pk, rol_anterior, rol_nuevo, objetivo.is_active,
            )
            messages.success(request, "Usuario actualizado correctamente.")
            return redirect("gestion_usuarios")

    return render(request, "usuarios/formulario_usuario.html", {
        "formulario": formulario,
        "es_creacion": False,
        "titulo": "Editar usuario",
        "objetivo": objetivo,
    })


@login_required
@require_http_methods(["GET", "POST"])
def cambiar_clave_usuario(request, usuario_id):
    """Restablece clave de otra cuenta, sin necesidad de conocer la anterior."""
    _exigir_administrador(request.user)
    objetivo = get_object_or_404(Usuario, pk=usuario_id)
    _exigir_gestion_objetivo(request.user, objetivo)

    formulario = SetPasswordForm(objetivo, request.POST or None)
    _estilizar_formulario(formulario)

    if request.method == "POST" and formulario.is_valid():
        _exigir_gestion_objetivo(request.user, objetivo)
        formulario.save()
        logger.warning(
            "GESPROY: %s restableció contraseña de usuario %s",
            request.user.pk, objetivo.pk,
        )
        messages.success(request, "Contraseña restablecida correctamente.")
        return redirect("gestion_usuarios")

    return render(request, "usuarios/cambiar_clave_usuario.html", {
        "formulario": formulario,
        "objetivo": objetivo,
    })