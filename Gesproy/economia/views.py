
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.views.decorators.http import require_POST

from proyectos.models import Dedicacion, Proyecto
from usuarios.models import Investigador

from .forms import (
    CategoriaEconomicaForm,
    PartidaEconomicaForm,
)

from .models import (
    CategoriaEconomica,
    EstudioEconomico,
    PartidaEconomica,
)


# ==========================================
# CONSTANTES
# ==========================================

FASES = EstudioEconomico.FASES

FASES_VALIDAS = {
    codigo for codigo, _nombre in FASES
}

ESTADOS_INICIALES = {
    "DEFINICION",
    "SOLICITADO",
    "NEGOCIACION",
}


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def obtener_investigador_id(usuario):

    if not usuario.is_authenticated:
        return None

    return Investigador.objects.filter(
        usuario=usuario
    ).values_list(
        "pk", flat=True
    ).first()


def es_investigador_asociado(usuario, proyecto):

    investigador_id = obtener_investigador_id(
        usuario
    )

    if investigador_id is None:
        return False

    if (
        proyecto.investigador_principal_id
        == investigador_id
    ):
        return True

    return Dedicacion.objects.filter(
        proyecto=proyecto,
        investigador_id=investigador_id,
    ).exists()


# ==========================================
# PERMISOS
# ==========================================

def puede_ver_estudio(usuario, proyecto):

    if not usuario.is_authenticated:
        return False

    if usuario.is_staff:
        return True

    # Durante ejecución y tras finalizar,
    # consulta permitida al investigador principal.
    if proyecto.estado in (
        "PROCESO",
        "FINALIZADO",
    ):
        return (
            proyecto.investigador_principal_id
            == obtener_investigador_id(usuario)
        )

    return es_investigador_asociado(
        usuario,
        proyecto,
    )


def puede_editar_estudio(usuario, proyecto):

    if not usuario.is_authenticated:
        return False

    if proyecto.estado in (
        "FINALIZADO",
        "DENEGADO",
    ):
        return False

    if proyecto.estado == "PROCESO":
        return usuario.is_staff

    if proyecto.estado in ESTADOS_INICIALES:
        return (
            usuario.is_staff
            or es_investigador_asociado(
                usuario,
                proyecto,
            )
        )

    return False


def verificar_lectura(usuario, proyecto):

    if not puede_ver_estudio(
        usuario,
        proyecto,
    ):
        raise PermissionDenied(
            "No tienes permiso para consultar "
            "el estudio económico."
        )


def verificar_edicion(
    usuario,
    proyecto,
    estudio=None,
):

    if not puede_editar_estudio(
        usuario,
        proyecto,
    ):
        raise PermissionDenied(
            "No tienes permiso para modificar "
            "el estudio económico."
        )

    if (
        estudio is not None
        and estudio.estado != "BORRADOR"
    ):
        raise PermissionDenied(
            "El estudio está cerrado. "
            "Debes crear una nueva versión."
        )


def fase_habilitada(proyecto, fase):

    permitidas = {
        "DEFINICION": {"INICIO"},
        "SOLICITADO": {"INICIO"},
        "NEGOCIACION": {
            "INICIO",
            "NEGOCIACION",
        },
        "PROCESO": FASES_VALIDAS,
    }

    return fase in permitidas.get(
        proyecto.estado,
        set(),
    )


def volver_estudio(proyecto_id, fase):

    url = reverse(
        "economia:estudio",
        args=[proyecto_id],
    )

    return redirect(
        f"{url}?fase={fase}"
    )


# ==========================================
# 1. VISUALIZAR ESTUDIO ECONÓMICO
# ==========================================

@login_required
def estudio_proyecto(request, proyecto_id):

    proyecto = get_object_or_404(
        Proyecto,
        pk=proyecto_id,
    )

    verificar_lectura(
        request.user,
        proyecto,
    )

    fase = request.GET.get(
        "fase",
        "REPLANTEO"
        if proyecto.estado == "PROCESO"
        else "INICIO",
    )

    if fase not in FASES_VALIDAS:
        raise Http404(
            "La fase económica no existe."
        )

    # Última versión de cada fase.
    versiones = {}

    for codigo, _nombre in FASES:

        versiones[codigo] = (
            EstudioEconomico.objects.filter(
                proyecto=proyecto,
                fase=codigo,
            )
            .order_by("-version")
            .first()
        )

    estudio = versiones[fase]

    grupos = []

    total_costes = Decimal("0.00")
    total_ingresos = Decimal("0.00")

    if estudio:

        partidas = list(
            estudio.partidas.select_related(
                "categoria__padre"
            ).all()
        )

        categorias_principales = (
            CategoriaEconomica.objects.filter(
                padre__isnull=True
            ).order_by(
                "tipo",
                "orden",
                "codigo",
            )
        )

        # Agrupar partidas por categoría principal.
        for principal in categorias_principales:

            lista = [
                partida
                for partida in partidas
                if (
                    partida.categoria.padre_id
                    == principal.pk
                )
            ]

            subtotal = sum(
                (
                    partida.importe
                    for partida in lista
                ),
                Decimal("0.00"),
            )

            grupos.append({
                "categoria": principal,
                "partidas": lista,
                "subtotal": subtotal,
            })

            if principal.tipo == "COSTE":
                total_costes += subtotal
            else:
                total_ingresos += subtotal

    # Presupuestos ya almacenados en Proyecto.
    presupuesto_total = (
        proyecto.importe_concedido
        if proyecto.importe_concedido is not None
        else proyecto.importe_solicitado
    )

    presupuesto_cesga = (
        proyecto.importe_concedido_cesga
        if proyecto.importe_concedido_cesga is not None
        else proyecto.importe_solicitado_cesga
    )

    opciones_fase = [
        {
            "codigo": codigo,
            "nombre": nombre,
            "ultima": versiones[codigo],
        }
        for codigo, nombre in FASES
    ]

    permiso_edicion = puede_editar_estudio(
        request.user,
        proyecto,
    )

    contexto = {
        "proyecto": proyecto,
        "fase": fase,
        "estudio": estudio,
        "opciones_fase": opciones_fase,
        "grupos": grupos,
        "total_costes": total_costes,
        "total_ingresos": total_ingresos,
        "saldo": total_ingresos - total_costes,
        "presupuesto_total": presupuesto_total,
        "presupuesto_cesga": presupuesto_cesga,
        "puede_editar": permiso_edicion,
        "fase_habilitada": fase_habilitada(
            proyecto,
            fase,
        ),
        "puede_editar_partidas": (
            permiso_edicion
            and estudio is not None
            and estudio.estado == "BORRADOR"
        ),
    }

    return render(
        request,
        "economia/estudio.html",
        contexto,
    )


# ==========================================
# 2. CREAR ESTUDIO / NUEVA VERSIÓN
# ==========================================

@login_required
@require_POST
@transaction.atomic
def crear_estudio(request, proyecto_id):

    proyecto = get_object_or_404(
        Proyecto.objects.select_for_update(),
        pk=proyecto_id,
    )

    verificar_edicion(
        request.user,
        proyecto,
    )

    fase = request.POST.get("fase", "")

    if (
        fase not in FASES_VALIDAS
        or not fase_habilitada(proyecto, fase)
    ):
        raise PermissionDenied(
            "No puedes crear un estudio "
            "para esa fase."
        )

    anterior = (
        EstudioEconomico.objects.filter(
            proyecto=proyecto,
            fase=fase,
        )
        .order_by("-version")
        .first()
    )

    # Impedir múltiples borradores simultáneos.
    if (
        anterior
        and anterior.estado == "BORRADOR"
    ):
        messages.info(
            request,
            "Ya existe un borrador "
            "para esta fase.",
        )

        return volver_estudio(
            proyecto.pk,
            fase,
        )

    nuevo = EstudioEconomico.objects.create(
        proyecto=proyecto,
        fase=fase,
        version=(
            anterior.version + 1
            if anterior else 1
        ),
        responsable=request.user,
    )

    # Copiar partidas de una versión anterior.
    if request.POST.get("copiar") == "1":

        origen = anterior

        if origen is None:

            fases_origen = {
                "NEGOCIACION": ["INICIO"],
                "REPLANTEO": [
                    "NEGOCIACION",
                    "INICIO",
                ],
            }.get(fase, [])

            for codigo in fases_origen:

                origen = (
                    EstudioEconomico.objects.filter(
                        proyecto=proyecto,
                        fase=codigo,
                    )
                    .order_by("-version")
                    .first()
                )

                if origen:
                    break

        if origen:

            nuevas_partidas = [
                PartidaEconomica(
                    estudio=nuevo,
                    categoria=partida.categoria,
                    concepto=partida.concepto,
                    importe=partida.importe,
                    entidad=partida.entidad,
                    observaciones=partida.observaciones,
                )
                for partida in origen.partidas.all()
            ]

            PartidaEconomica.objects.bulk_create(
                nuevas_partidas
            )

    messages.success(
        request,
        "Estudio económico creado correctamente.",
    )

    return volver_estudio(
        proyecto.pk,
        fase,
    )


# ==========================================
# 3. CREAR / EDITAR PARTIDA
# ==========================================

@login_required
@transaction.atomic
def formulario_partida(
    request,
    proyecto_id,
    estudio_id,
    partida_id=None,
):

    proyecto = get_object_or_404(
        Proyecto,
        pk=proyecto_id,
    )

    estudio = get_object_or_404(
        EstudioEconomico.objects.select_for_update(),
        pk=estudio_id,
        proyecto=proyecto,
    )

    verificar_edicion(
        request.user,
        proyecto,
        estudio,
    )

    partida = None

    if partida_id is not None:
        partida = get_object_or_404(
            PartidaEconomica,
            pk=partida_id,
            estudio=estudio,
        )

    formulario = PartidaEconomicaForm(
        request.POST or None,
        instance=partida,
    )

    if (
        request.method == "POST"
        and formulario.is_valid()
    ):

        partida = formulario.save(
            commit=False
        )

        partida.estudio = estudio
        partida.save()

        messages.success(
            request,
            "Partida guardada correctamente.",
        )

        return volver_estudio(
            proyecto.pk,
            estudio.fase,
        )

    return render(
        request,
        "economia/partida_form.html",
        {
            "proyecto": proyecto,
            "estudio": estudio,
            "formulario": formulario,
            "es_edicion": (
                partida_id is not None
            ),
        },
    )


# ==========================================
# 4. ELIMINAR PARTIDA
# ==========================================

@login_required
@require_POST
@transaction.atomic
def eliminar_partida(
    request,
    proyecto_id,
    estudio_id,
    partida_id,
):

    proyecto = get_object_or_404(
        Proyecto,
        pk=proyecto_id,
    )

    estudio = get_object_or_404(
        EstudioEconomico.objects.select_for_update(),
        pk=estudio_id,
        proyecto=proyecto,
    )

    verificar_edicion(
        request.user,
        proyecto,
        estudio,
    )

    partida = get_object_or_404(
        PartidaEconomica,
        pk=partida_id,
        estudio=estudio,
    )

    partida.delete()

    messages.success(
        request,
        "Partida eliminada correctamente.",
    )

    return volver_estudio(
        proyecto.pk,
        estudio.fase,
    )


# ==========================================
# 5. CERRAR ESTUDIO
# ==========================================

@login_required
@require_POST
@transaction.atomic
def cerrar_estudio(
    request,
    proyecto_id,
    estudio_id,
):

    proyecto = get_object_or_404(
        Proyecto,
        pk=proyecto_id,
    )

    estudio = get_object_or_404(
        EstudioEconomico.objects.select_for_update(),
        pk=estudio_id,
        proyecto=proyecto,
    )

    verificar_edicion(
        request.user,
        proyecto,
        estudio,
    )

    estudio.estado = "CERRADO"

    estudio.save(
        update_fields=["estado"]
    )

    messages.success(
        request,
        "Estudio cerrado. Para modificarlo "
        "deberás crear una nueva versión.",
    )

    return volver_estudio(
        proyecto.pk,
        estudio.fase,
    )


# ==========================================
# ADMINISTRACIÓN DE CATEGORÍAS
# ==========================================

def exigir_administrador(request):

    if not request.user.is_staff:
        raise PermissionDenied(
            "Solo los administradores pueden "
            "gestionar las categorías económicas."
        )


# ==========================================
# 6. LISTADO DE CATEGORÍAS
# ==========================================

@login_required
def gestionar_categorias(request):

    exigir_administrador(request)

    categorias = (
        CategoriaEconomica.objects.filter(
            padre__isnull=True
        )
        .prefetch_related("subcategorias")
        .order_by(
            "tipo",
            "orden",
            "codigo",
        )
    )

    return render(
        request,
        "economia/categorias_lista.html",
        {
            "categorias": categorias,
        },
    )


# ==========================================
# 7. CREAR CATEGORÍA
# ==========================================

@login_required
def crear_categoria(request):

    exigir_administrador(request)

    inicial = {
        "tipo": "COSTE",
        "orden": 0,
    }

    padre_id = request.GET.get("padre")

    if padre_id and padre_id.isdecimal():

        padre = CategoriaEconomica.objects.filter(
            pk=padre_id,
            padre__isnull=True,
        ).first()

        if padre:
            inicial["padre"] = padre
            inicial["tipo"] = padre.tipo

    formulario = CategoriaEconomicaForm(
        request.POST or None,
        initial=inicial,
    )

    if (
        request.method == "POST"
        and formulario.is_valid()
    ):

        formulario.save()

        messages.success(
            request,
            "Categoría creada correctamente.",
        )

        return redirect(
            "economia:gestionar_categorias"
        )

    return render(
        request,
        "economia/categoria_form.html",
        {
            "formulario": formulario,
            "titulo": "Nueva categoría económica",
            "es_edicion": False,
        },
    )


# ==========================================
# 8. EDITAR CATEGORÍA
# ==========================================

@login_required
def editar_categoria(
    request,
    categoria_id,
):

    exigir_administrador(request)

    categoria = get_object_or_404(
        CategoriaEconomica,
        pk=categoria_id,
    )

    formulario = CategoriaEconomicaForm(
        request.POST or None,
        instance=categoria,
    )

    if (
        request.method == "POST"
        and formulario.is_valid()
    ):

        formulario.save()

        messages.success(
            request,
            "Categoría actualizada correctamente.",
        )

        return redirect(
            "economia:gestionar_categorias"
        )

    return render(
        request,
        "economia/categoria_form.html",
        {
            "formulario": formulario,
            "titulo": "Editar categoría económica",
            "es_edicion": True,
            "categoria": categoria,
        },
    )


# ==========================================
# 9. ELIMINAR CATEGORÍA
# ==========================================

@login_required
@require_POST
def eliminar_categoria(
    request,
    categoria_id,
):

    exigir_administrador(request)

    categoria = get_object_or_404(
        CategoriaEconomica,
        pk=categoria_id,
    )

    tiene_subcategorias = (
        CategoriaEconomica.objects.filter(
            padre=categoria
        ).exists()
    )

    if tiene_subcategorias:

        messages.error(
            request,
            "No puedes eliminar esta categoría "
            "porque contiene subcategorías.",
        )

        return redirect(
            "economia:gestionar_categorias"
        )

    tiene_partidas = (
        PartidaEconomica.objects.filter(
            categoria=categoria
        ).exists()
    )

    if tiene_partidas:

        messages.error(
            request,
            "No puedes eliminar esta categoría "
            "porque tiene partidas asociadas.",
        )

        return redirect(
            "economia:gestionar_categorias"
        )

    try:

        categoria.delete()

        messages.success(
            request,
            "Categoría eliminada correctamente.",
        )

    except ProtectedError:

        messages.error(
            request,
            "No se puede eliminar la categoría "
            "porque existen datos relacionados.",
        )

    return redirect(
        "economia:gestionar_categorias"
    )


# ==========================================
# 10. COMPARATIVA DE ESTUDIOS ECONÓMICOS
# ==========================================

@login_required
def comparativa_estudios(request, proyecto_id):

    proyecto = get_object_or_404(
        Proyecto,
        pk=proyecto_id,
    )

    # Mismos permisos de lectura que el estudio.
    verificar_lectura(
        request.user,
        proyecto,
    )

    fases = [
        "INICIO",
        "NEGOCIACION",
        "REPLANTEO",
    ]

    cero = Decimal("0.00")

    # ======================================
    # ÚLTIMA VERSIÓN DE CADA FASE
    # ======================================

    versiones = {}

    importes = {
        fase: {} for fase in fases
    }

    totales = {
        fase: {
            "COSTE": cero,
            "INGRESO": cero,
        }
        for fase in fases
    }

    categorias_utilizadas = {}

    for fase in fases:

        estudio = (
            EstudioEconomico.objects.filter(
                proyecto=proyecto,
                fase=fase,
            )
            .order_by("-version")
            .first()
        )

        versiones[fase] = estudio

        if estudio is None:
            continue

        partidas = estudio.partidas.select_related(
            "categoria__padre"
        )

        for partida in partidas:

            categoria = partida.categoria

            categorias_utilizadas[
                categoria.pk
            ] = categoria

            # Sumar importes de la misma subcategoría.
            importe_anterior = importes[fase].get(
                categoria.pk,
                cero,
            )

            importes[fase][categoria.pk] = (
                importe_anterior + partida.importe
            )

            # Total general de costes o ingresos.
            totales[fase][categoria.tipo] += (
                partida.importe
            )

    # ======================================
    # DIFERENCIAS ENTRE FASES
    # ======================================

    def calcular_diferencia(anterior, nuevo):

        if anterior is None or nuevo is None:
            return {
                "disponible": False,
                "importe": None,
                "porcentaje": None,
            }

        diferencia = nuevo - anterior

        # Si la cantidad inicial es cero,
        # el porcentaje de variación no se define.
        porcentaje = None

        if anterior != 0:

            porcentaje = (
                diferencia / abs(anterior)
            ) * Decimal("100")

        return {
            "disponible": True,
            "importe": diferencia,
            "porcentaje": porcentaje,
        }

    # ======================================
    # CONSTRUIR UNA FILA DE LA TABLA
    # ======================================

    def crear_fila(
        nombre,
        categoria_id=None,
        tipo_total=None,
        es_saldo=False,
    ):

        valores = {}

        for fase in fases:

            # Una fase sin estudio no equivale
            # a tener un presupuesto de cero euros.
            if versiones[fase] is None:

                valores[fase] = None

            elif es_saldo:

                valores[fase] = (
                    totales[fase]["INGRESO"]
                    - totales[fase]["COSTE"]
                )

            elif tipo_total is not None:

                valores[fase] = totales[fase][
                    tipo_total
                ]

            else:

                valores[fase] = importes[fase].get(
                    categoria_id,
                    cero,
                )

        return {
            "nombre": nombre,
            "inicio": valores["INICIO"],
            "negociacion": valores["NEGOCIACION"],
            "replanteo": valores["REPLANTEO"],
            "diferencia_inicio_negociacion": (
                calcular_diferencia(
                    valores["INICIO"],
                    valores["NEGOCIACION"],
                )
            ),
            "diferencia_negociacion_replanteo": (
                calcular_diferencia(
                    valores["NEGOCIACION"],
                    valores["REPLANTEO"],
                )
            ),
        }

    # ======================================
    # ORDENAR LAS CATEGORÍAS
    # ======================================

    categorias_ordenadas = sorted(
        categorias_utilizadas.values(),
        key=lambda categoria: (
            0 if categoria.tipo == "COSTE" else 1,
            (
                categoria.padre.orden
                if categoria.padre_id
                else categoria.orden
            ),
            (
                categoria.padre.codigo
                if categoria.padre_id
                else categoria.codigo
            ),
            categoria.orden,
            categoria.codigo,
        ),
    )

    filas_costes = []
    filas_ingresos = []

    for categoria in categorias_ordenadas:

        if categoria.padre_id:

            nombre = (
                f"{categoria.padre.nombre} / "
                f"{categoria.nombre}"
            )

        else:

            nombre = categoria.nombre

        fila = crear_fila(
            nombre=nombre,
            categoria_id=categoria.pk,
        )

        if categoria.tipo == "COSTE":

            filas_costes.append(fila)

        else:

            filas_ingresos.append(fila)

    # ======================================
    # TOTALES GENERALES
    # ======================================

    filas_totales = [
        crear_fila(
            "Total de costes previstos",
            tipo_total="COSTE",
        ),
        crear_fila(
            "Total de ingresos previstos",
            tipo_total="INGRESO",
        ),
        crear_fila(
            "Saldo previsto",
            es_saldo=True,
        ),
    ]

    grupos = [
        {
            "titulo": "Costes previstos",
            "filas": filas_costes,
        },
        {
            "titulo": "Ingresos previstos",
            "filas": filas_ingresos,
        },
    ]

    return render(
        request,
        "economia/comparativa.html",
        {
            "proyecto": proyecto,
            "versiones": versiones,
            "grupos": grupos,
            "filas_totales": filas_totales,
            "hay_estudios": any(
                versiones.values()
            ),
        },
    )

