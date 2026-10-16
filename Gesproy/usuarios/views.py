from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect

from .forms import CrearInvestigadorForm

Usuario = get_user_model()


def es_admin(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(es_admin)
def gestion_investigadores(request):
    investigadores = Usuario.objects.all().order_by("last_name", "first_name", "username")

    return render(
        request,
        "usuarios/gestion_investigadores.html",
        {
            "investigadores": investigadores,
        }
    )


@login_required
@user_passes_test(es_admin)
def anadir_investigador(request):
    if request.method == "POST":
        formulario = CrearInvestigadorForm(request.POST)

        if formulario.is_valid():
            formulario.save()
            return redirect("gestion_investigadores")
    else:
        formulario = CrearInvestigadorForm()

    return render(
        request,
        "usuarios/anadir_investigador.html",
        {
            "formulario": formulario,
        }
    )


@login_required
@user_passes_test(es_admin)
def cambiar_estado_investigador(request, id):
    investigador = get_object_or_404(Usuario, id=id)

    if request.method == "POST":
        investigador.is_active = not investigador.is_active
        investigador.save()

    return redirect("gestion_investigadores")