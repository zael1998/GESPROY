"""Validación e informe de horas para Gesproy.

Una dedicación relaciona (proyecto, investigador, validador).
El validador ve únicamente los registros de los investigadores a su cargo.
Los administradores pueden consultar informes y reabrir horas, pero NUNCA validar.
"""

from collections import OrderedDict
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from proyectos.models import Dedicacion, Proyecto
from usuarios.models import Investigador
from .calendario import mis_horas as _mis_horas_original
from .models import CierreMensualHoras, HistorialValidacionHoras, RegistroHoras


def _investigador_de_usuario(usuario):
    return Investigador.objects.filter(usuario=usuario).first()


def _es_validador(usuario):
    """Solo usuarios NO administradores habilitados expresamente.

    La comprobación se usa en la vista, en los POST y en la navegación.
    Nunca basta con ocultar botones en HTML.
    """
    if not usuario.is_authenticated or usuario.is_staff:
        return False
    if getattr(usuario, "rol", None) == "ADMIN":
        return False
    return Investigador.objects.filter(
        usuario=usuario,
        usuario__is_active=True,
        puede_validar_horas=True,
    ).exists()


def _asignaciones_del_validador(investigador):
    """Subconsulta con el par proyecto/investigador de cada registro.

    Se respetan las fechas de la dedicación correspondiente al trabajador.
    """
    return (
        Dedicacion.objects.filter(
            proyecto_id=OuterRef("tarea__proyecto_id"),
            investigador_id=OuterRef("investigador_id"),
            validador_id=investigador.pk,
            fecha_inicio__lte=OuterRef("fecha"),
        )
        .filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=OuterRef("fecha"))
        )
    )


def _registros_para_validar(usuario):
    """NUNCA confiar en los IDs que llegan desde el navegador."""
    consulta = RegistroHoras.objects.all()
    actual = _investigador_de_usuario(usuario)

    # Ni los administradores ni los investigadores normales pueden aprobar.
    # Incluso si alguien activa accidentalmente su bandera en la BD,
    # el rol de administrador queda excluido.
    if not _es_validador(usuario) or actual is None:
        return consulta.none()

    return consulta.filter(Exists(_asignaciones_del_validador(actual))).exclude(
        investigador_id=actual.pk
    )


def _registros_para_informe(usuario):
    consulta = RegistroHoras.objects.all()
    actual = _investigador_de_usuario(usuario)
    if usuario.is_staff:
        return consulta
    if actual is None:
        return consulta.none()
    if _es_validador(usuario):
        return consulta.filter(
            Q(investigador_id=actual.pk)
            | Q(Exists(_asignaciones_del_validador(actual)))
        )
    return consulta.filter(investigador_id=actual.pk)


def _nombre(investigador):
    usuario = investigador.usuario
    return usuario.get_full_name().strip() or usuario.username


def _fecha_desde_cadena(raw):
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


@login_required
def mis_horas_seguro(request):
    """Conserva el calendario original y da errores claros al cerrar partes.

    La transacción evita registrar solo parte de los días si uno está cerrado.
    """
    if request.method != "POST":
        return _mis_horas_original(request)
    try:
        with transaction.atomic():
            return _mis_horas_original(request)
    except ValidationError as error:
        messages.error(request, "No se han guardado las horas: " + "; ".join(error.messages))
        return redirect("horas:mis_horas")


@login_required
def inicio_horas(request):
    actual = _investigador_de_usuario(request.user)
    puede_validar = _es_validador(request.user)
    return render(
        request,
        "horas/inicio_horas.html",
        {"puede_validar": puede_validar},
    )


@login_required
def validar_horas(request):
    actual = _investigador_de_usuario(request.user)
    puede_validar = _es_validador(request.user)
    if not puede_validar:
        raise PermissionDenied("No tienes permiso para validar horas.")

    pendientes_qs = _registros_para_validar(request.user).filter(validado=False)

    proyecto_id = request.GET.get("proyecto", "")
    if proyecto_id.isdecimal():
        pendientes_qs = pendientes_qs.filter(tarea__proyecto_id=int(proyecto_id))

    # Las opciones se generan a partir del conjunto permitido, nunca de todas
    # las personas y proyectos del centro para un validador normal.
    opciones_qs = _registros_para_validar(request.user)
    proyectos = Proyecto.objects.filter(
        pk__in=opciones_qs.values("tarea__proyecto_id")
    ).order_by("acronimo")

    numero_total = pendientes_qs.count()
    registros = list(
        pendientes_qs.select_related(
            "investigador__usuario", "tarea__proyecto", "tarea"
        ).order_by(
            "investigador__usuario__last_name",
            "investigador__usuario__first_name",
            "-fecha",
            "pk",
        )[:2500]
    )

    grupos = OrderedDict()
    for registro in registros:
        clave = (
            registro.investigador_id,
            registro.fecha.year,
            registro.fecha.month,
        )
        if clave not in grupos:
            grupos[clave] = {
                "investigador": registro.investigador,
                "nombre": _nombre(registro.investigador),
                "anio": registro.fecha.year,
                "mes": registro.fecha.month,
                "mes_fecha": registro.fecha.replace(day=1),
                "registros": [],
                "total": Decimal("0.00"),
                "cantidad": 0,
            }
        grupo = grupos[clave]
        grupo["registros"].append(registro)
        grupo["total"] += registro.horas
        grupo["cantidad"] += 1

    return render(request, "horas/validar_horas.html", {
        "grupos": list(grupos.values()),
        "proyectos": proyectos,
        "proyecto_id": proyecto_id,
        "numero_total": numero_total,
        "limitado": numero_total > len(registros),
        "puede_validar": True,
    })


@login_required
@require_POST
def accion_validar(request):
    """Solo POST + CSRF; control real de permisos en cada registro."""
    accion = request.POST.get("accion")

    # EXCEPCIÓN: el administrador puede REABRIR horas (no validarlas).
    # Todas las demás acciones exigen un validador expresamente designado.
    if accion == "reabrir":
        if not request.user.is_staff:
            raise PermissionDenied("Solo un administrador puede reabrir horas.")
    elif not _es_validador(request.user):
        raise PermissionDenied(
            "Solo los validadores autorizados pueden validar horas."
        )

    permitido = _registros_para_validar(request.user)

    if accion == "individual":
        registro_id = request.POST.get("registro_id", "")
        if not registro_id.isdecimal():
            messages.error(request, "Identificador de registro inválido.")
            return redirect("horas:validar_horas")

        with transaction.atomic():
            registro = get_object_or_404(
                permitido.select_for_update().filter(validado=False),
                pk=int(registro_id),
            )
            ahora = timezone.now()
            afectados = RegistroHoras.objects.filter(
                pk=registro.pk, validado=False
            ).update(
                validado=True,
                validado_por=request.user,
                fecha_validacion=ahora,
            )
            if afectados:
                HistorialValidacionHoras.objects.create(
                    registro=registro,
                    accion="VALIDAR",
                    usuario=request.user,
                )
        messages.success(request, "Horas validadas correctamente.")

    elif accion == "mes":
        investigador_raw = request.POST.get("investigador_id", "")
        anio_raw = request.POST.get("anio", "")
        mes_raw = request.POST.get("mes", "")
        if not all(x.isdecimal() for x in (investigador_raw, anio_raw, mes_raw)):
            messages.error(request, "Datos de mes incorrectos.")
            return redirect("horas:validar_horas")

        anio, mes = int(anio_raw), int(mes_raw)
        if not (2000 <= anio <= 2200 and 1 <= mes <= 12):
            messages.error(request, "Mes o año inválido.")
            return redirect("horas:validar_horas")

        proyecto_raw = request.POST.get("proyecto_id", "")
        consulta = permitido.filter(
            investigador_id=int(investigador_raw),
            fecha__year=anio,
            fecha__month=mes,
            validado=False,
        )
        if proyecto_raw.isdecimal():
            consulta = consulta.filter(tarea__proyecto_id=int(proyecto_raw))

        with transaction.atomic():
            registros = list(
                consulta.select_for_update().select_related("tarea").order_by("pk")
            )
            if not registros:
                messages.warning(request, "No hay registros pendientes para ese mes.")
                return redirect("horas:validar_horas")

            ids = [registro.pk for registro in registros]
            ahora = timezone.now()
            actualizados = RegistroHoras.objects.filter(
                pk__in=ids, validado=False
            ).update(
                validado=True,
                validado_por=request.user,
                fecha_validacion=ahora,
            )
            HistorialValidacionHoras.objects.bulk_create([
                HistorialValidacionHoras(
                    registro=registro,
                    accion="VALIDAR",
                    usuario=request.user,
                )
                for registro in registros
            ])
            # El mes queda cerrado para los proyectos involucrados.
            # Así no se pueden añadir nuevas horas al mismo mes tras aprobarlo.
            proyectos_afectados = {registro.tarea.proyecto_id for registro in registros}
            for proyecto_id in proyectos_afectados:
                CierreMensualHoras.objects.get_or_create(
                    proyecto_id=proyecto_id,
                    investigador_id=int(investigador_raw),
                    anio=anio,
                    mes=mes,
                    defaults={"validado_por": request.user},
                )
        messages.success(request, f"Se han validado {actualizados} registros y cerrado el mes en sus proyectos.")

    elif accion == "reabrir":
        if not request.user.is_staff:
            raise PermissionDenied("Solo un administrador puede reabrir horas.")
        registro_raw = request.POST.get("registro_id", "")
        motivo = request.POST.get("motivo", "").strip()
        if not registro_raw.isdecimal() or not motivo:
            messages.error(request, "Debes indicar el registro y el motivo.")
            return redirect("horas:informe_horas")

        with transaction.atomic():
            registro = get_object_or_404(
                RegistroHoras.objects.select_for_update(),
                pk=int(registro_raw), validado=True,
            )
            RegistroHoras.objects.filter(pk=registro.pk).update(
                validado=False,
                validado_por=None,
                fecha_validacion=None,
            )
            # Al reabrir un registro, también se abre el mes correspondiente
            # para permitir que el autor lo corrija o añada horas de ese mes.
            CierreMensualHoras.objects.filter(
                investigador_id=registro.investigador_id,
                proyecto_id=registro.tarea.proyecto_id,
                anio=registro.fecha.year,
                mes=registro.fecha.month,
            ).delete()
            HistorialValidacionHoras.objects.create(
                registro=registro,
                accion="REABRIR",
                usuario=request.user,
                motivo=motivo,
            )
        messages.success(request, "El registro se ha reabierto.")
        return redirect("horas:informe_horas")

    else:
        messages.error(request, "Acción no permitida.")

    return redirect("horas:validar_horas")


def _claves_agrupacion(registro, dimension):
    if dimension == "investigador":
        return (_nombre(registro.investigador), f"I-{registro.investigador_id}")
    if dimension == "tarea":
        return (
            registro.tarea.nombre,
            f"T-{registro.tarea_id}",
        )
    return (
        registro.tarea.proyecto.acronimo,
        f"P-{registro.tarea.proyecto_id}",
    )


@login_required
def informe_horas(request):
    hoy = timezone.localdate()
    desde_str = request.GET.get("desde", f"{hoy.year}-01-01")
    hasta_str = request.GET.get("hasta", hoy.isoformat())
    desde = _fecha_desde_cadena(desde_str)
    hasta = _fecha_desde_cadena(hasta_str)

    qs_permitidos = _registros_para_informe(request.user)
    proyectos = Proyecto.objects.filter(
        pk__in=qs_permitidos.values("tarea__proyecto_id")
    ).order_by("acronimo")
    investigadores = Investigador.objects.filter(
        pk__in=qs_permitidos.values("investigador_id")
    ).select_related("usuario").order_by(
        "usuario__last_name", "usuario__first_name", "usuario__username"
    )

    proyecto_id = request.GET.get("proyecto", "")
    investigador_id = request.GET.get("investigador", "")
    estado = request.GET.get("validacion", "todas")
    agrupar = request.GET.get("agrupar", "proyecto")
    dentro = request.GET.get("dentro", "tarea")
    orden = request.GET.get("orden", "horas")
    detalle = request.GET.get("detalle", "registros")

    if agrupar not in {"proyecto", "investigador", "tarea"}:
        agrupar = "proyecto"
    if dentro not in {"proyecto", "investigador", "tarea"}:
        dentro = "tarea"
    if orden not in {"horas", "nombre", "recientes"}:
        orden = "horas"
    if detalle not in {"registros", "resumen"}:
        detalle = "registros"
    if estado not in {"todas", "validadas", "pendientes"}:
        estado = "todas"

    consulta = qs_permitidos
    if desde is not None:
        consulta = consulta.filter(fecha__gte=desde)
    if hasta is not None:
        consulta = consulta.filter(fecha__lte=hasta)
    if proyecto_id.isdecimal():
        consulta = consulta.filter(tarea__proyecto_id=int(proyecto_id))
    if investigador_id.isdecimal():
        consulta = consulta.filter(investigador_id=int(investigador_id))
    if estado == "validadas":
        consulta = consulta.filter(validado=True)
    elif estado == "pendientes":
        consulta = consulta.filter(validado=False)

    filtros_invalidos = (desde is None or hasta is None or desde > hasta)
    if filtros_invalidos:
        consulta = consulta.none()

    total_registros = consulta.count()
    total_horas = consulta.aggregate(total=Sum("horas"))["total"] or Decimal("0.00")
    registros = list(consulta.select_related(
        "tarea__proyecto", "investigador__usuario", "validado_por"
    ).order_by("-fecha", "pk")[:5000])

    diccionario = OrderedDict()
    for registro in registros:
        nombre_grupo, clave_grupo = _claves_agrupacion(registro, agrupar)
        nombre_subgrupo, clave_subgrupo = _claves_agrupacion(registro, dentro)

        if clave_grupo not in diccionario:
            diccionario[clave_grupo] = {
                "nombre": nombre_grupo,
                "total": Decimal("0.00"),
                "cantidad": 0,
                "ultima_fecha": registro.fecha,
                "subgrupos": OrderedDict(),
            }
        grupo = diccionario[clave_grupo]
        grupo["total"] += registro.horas
        grupo["cantidad"] += 1
        grupo["ultima_fecha"] = max(grupo["ultima_fecha"], registro.fecha)

        if clave_subgrupo not in grupo["subgrupos"]:
            grupo["subgrupos"][clave_subgrupo] = {
                "nombre": nombre_subgrupo,
                "total": Decimal("0.00"),
                "cantidad": 0,
                "ultima_fecha": registro.fecha,
                "registros": [],
            }
        subgrupo = grupo["subgrupos"][clave_subgrupo]
        subgrupo["total"] += registro.horas
        subgrupo["cantidad"] += 1
        subgrupo["ultima_fecha"] = max(subgrupo["ultima_fecha"], registro.fecha)
        subgrupo["registros"].append(registro)

    def ordenar_lista(lista):
        if orden == "nombre":
            return sorted(lista, key=lambda g: g["nombre"].casefold())
        if orden == "recientes":
            return sorted(lista, key=lambda g: g["ultima_fecha"], reverse=True)
        return sorted(lista, key=lambda g: g["total"], reverse=True)

    grupos = []
    for grupo in ordenar_lista(list(diccionario.values())):
        grupo["subgrupos"] = ordenar_lista(list(grupo["subgrupos"].values()))
        grupos.append(grupo)

    puede_validar = _es_validador(request.user)

    return render(request, "horas/informe_horas.html", {
        "grupos": grupos,
        "proyectos": proyectos,
        "investigadores": investigadores,
        "proyecto_id": proyecto_id,
        "investigador_id": investigador_id,
        "desde": desde_str,
        "hasta": hasta_str,
        "validacion": estado,
        "agrupar": agrupar,
        "dentro": dentro,
        "orden": orden,
        "detalle": detalle,
        "total_horas": total_horas,
        "total_registros": total_registros,
        "limitado": total_registros > len(registros),
        "filtros_invalidos": filtros_invalidos,
        "puede_validar": puede_validar,
        "puede_reabrir": request.user.is_staff,
        "fecha_impresion": timezone.localtime(),
    })