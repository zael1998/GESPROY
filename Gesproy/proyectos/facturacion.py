"""Gestión de movimientos económicos reales de Gesproy.

Reutiliza proyectos.MovimientoEconomico, sin crear modelos nuevos.
La factura/movimiento real NO debe confundirse con el Estudio Económico.

Reglas del manual:
- PROCESO: administrador lee, crea y edita; responsable solo lee.
- FINALIZADO: administrador y responsable leen; nadie modifica.
- No se habilita un rol administrativo sin definirlo en usuarios.Usuario.
"""
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from usuarios.models import Investigador
from .models import MovimientoEconomico, Proyecto

ESTADOS_FACTURACION = ("PROCESO", "FINALIZADO")
TIPOS = {"INGRESO": "Ingreso", "GASTO": "Gasto"}
CERO = Decimal("0.00")


def _es_admin(usuario):
    return bool(
        usuario.is_authenticated
        and usuario.is_active
        and (usuario.is_staff or usuario.is_superuser)
    )


def _es_responsable(usuario, proyecto):
    if not usuario.is_authenticated or not usuario.is_active:
        return False
    if not proyecto.investigador_principal_id:
        return False
    return Investigador.objects.filter(
        pk=proyecto.investigador_principal_id,
        usuario=usuario,
    ).exists()


def _permiso_facturas(usuario, proyecto):
    """Devuelve permiso de edición tras verificar el de lectura."""
    if proyecto.estado not in ESTADOS_FACTURACION:
        raise Http404("La facturación solo está disponible en proceso o finalizado.")

    admin = _es_admin(usuario)
    if not admin and not _es_responsable(usuario, proyecto):
        raise PermissionDenied("No tienes acceso a la facturación de este proyecto.")

    return admin and proyecto.estado == "PROCESO"


def _exigir_edicion(puede_editar):
    if not puede_editar:
        raise PermissionDenied("No tienes permiso para modificar los movimientos.")


class MovimientoEconomicoForm(forms.ModelForm):
    """Formulario deliberadamente reducido a los campos actuales del modelo."""

    class Meta:
        model = MovimientoEconomico
        fields = ("concepto", "fecha", "importe")
        labels = {
            "concepto": "Concepto",
            "fecha": "Fecha del movimiento",
            "importe": "Importe (€)",
        }
        widgets = {
            "concepto": forms.TextInput(attrs={
                "class": "fac-input", "maxlength": "100",
                "placeholder": "Por ejemplo: pago de material de laboratorio",
            }),
            "fecha": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "fac-input", "type": "date"},
            ),
            "importe": forms.NumberInput(attrs={
                "class": "fac-input", "min": "0.01", "step": "0.01",
                "placeholder": "0,00",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]
        if not self.is_bound and not self.instance.pk:
            self.fields["fecha"].initial = timezone.localdate()

    def clean_importe(self):
        importe = self.cleaned_data["importe"]
        if importe is None or importe <= CERO:
            raise forms.ValidationError("El importe debe ser mayor que cero.")
        return importe


@login_required
@require_http_methods(["GET"])
def facturacion_proyectos(request):
    """Acceso directo para los administradores: elegir un proyecto."""
    if not _es_admin(request.user):
        raise PermissionDenied("Esta lista solo está disponible para administradores.")

    consulta = Proyecto.objects.filter(
        estado__in=ESTADOS_FACTURACION,
    ).order_by("acronimo", "pk")

    busqueda = request.GET.get("q", "").strip()[:100]
    if busqueda:
        consulta = consulta.filter(
            Q(acronimo__icontains=busqueda) | Q(nombre__icontains=busqueda)
        )

    pagina = Paginator(consulta, 25).get_page(request.GET.get("page"))
    ids = [p.pk for p in pagina.object_list]
    totales = {pk: {"INGRESO": CERO, "GASTO": CERO} for pk in ids}

    # Los tipos son CharField; __iexact también acepta registros antiguos
    # guardados en minúsculas, sin migrar ni editar sus datos.
    if ids:
        movimientos = MovimientoEconomico.objects.filter(
            proyecto_id__in=ids,
        ).values("proyecto_id", "tipo_movimiento", "importe")
        for mov in movimientos:
            tipo = (mov["tipo_movimiento"] or "").upper().strip()
            if tipo in TIPOS:
                totales[mov["proyecto_id"]][tipo] += mov["importe"]

    for proyecto in pagina.object_list:
        cifras = totales[proyecto.pk]
        proyecto.fact_ingresos = cifras["INGRESO"]
        proyecto.fact_gastos = cifras["GASTO"]
        proyecto.fact_saldo = cifras["INGRESO"] - cifras["GASTO"]

    return render(request, "proyectos/facturacion/proyectos.html", {
        "pagina": pagina,
        "busqueda": busqueda,
    })


@login_required
@require_http_methods(["GET"])
def facturacion_detalle(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    puede_editar = _permiso_facturas(request.user, proyecto)

    movimientos = list(
        MovimientoEconomico.objects.filter(proyecto=proyecto)
        .order_by("-fecha", "-pk")
    )
    ingresos = []
    gastos = []
    sin_clasificar = []
    for movimiento in movimientos:
        tipo = (movimiento.tipo_movimiento or "").upper().strip()
        if tipo == "INGRESO":
            ingresos.append(movimiento)
        elif tipo == "GASTO":
            gastos.append(movimiento)
        else:
            sin_clasificar.append(movimiento)

    total_ingresos = sum((m.importe for m in ingresos), CERO)
    total_gastos = sum((m.importe for m in gastos), CERO)

    return render(request, "proyectos/facturacion/detalle.html", {
        "proyecto": proyecto,
        "puede_editar": puede_editar,
        "ingresos": ingresos,
        "gastos": gastos,
        "sin_clasificar": sin_clasificar,
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "saldo": total_ingresos - total_gastos,
    })


def _formulario_movimiento(request, proyecto_id, tipo, movimiento_id=None):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    _exigir_edicion(_permiso_facturas(request.user, proyecto))
    if tipo not in TIPOS:
        raise Http404("Tipo de movimiento no válido.")

    movimiento = None
    if movimiento_id is not None:
        movimiento = get_object_or_404(
            MovimientoEconomico,
            pk=movimiento_id,
            proyecto=proyecto,
        )
        # Evita que se cambie el tipo mediante URL/POST.
        if (movimiento.tipo_movimiento or "").upper().strip() != tipo:
            raise Http404("El movimiento no pertenece a este tipo.")

    formulario = MovimientoEconomicoForm(
        request.POST if request.method == "POST" else None,
        instance=movimiento,
    )
    if request.method == "POST" and formulario.is_valid():
        dato = formulario.save(commit=False)
        dato.proyecto = proyecto
        dato.tipo_movimiento = tipo
        dato.save()
        messages.success(
            request,
            f"{TIPOS[tipo]} {'actualizado' if movimiento else 'registrado'} correctamente.",
        )
        return redirect("facturacion_detalle", proyecto_id=proyecto.pk)

    return render(request, "proyectos/facturacion/formulario.html", {
        "proyecto": proyecto,
        "formulario": formulario,
        "tipo": tipo,
        "tipo_nombre": TIPOS[tipo].lower(),
        "editando": movimiento is not None,
    })


@login_required
@require_http_methods(["GET", "POST"])
def nuevo_ingreso(request, proyecto_id):
    return _formulario_movimiento(request, proyecto_id, "INGRESO")


@login_required
@require_http_methods(["GET", "POST"])
def nuevo_gasto(request, proyecto_id):
    return _formulario_movimiento(request, proyecto_id, "GASTO")


@login_required
@require_http_methods(["GET", "POST"])
def editar_movimiento(request, proyecto_id, movimiento_id):
    movimiento = get_object_or_404(
        MovimientoEconomico,
        pk=movimiento_id,
        proyecto_id=proyecto_id,
    )
    tipo = (movimiento.tipo_movimiento or "").upper().strip()
    return _formulario_movimiento(request, proyecto_id, tipo, movimiento_id)