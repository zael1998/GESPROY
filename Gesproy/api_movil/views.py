import json

from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from usuarios.models import Investigador
from proyectos.models import Proyecto, Dedicacion


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def comprobar_autenticacion(request):
    """
    Devuelve una respuesta 401 si el usuario
    no tiene una sesión autenticada.
    """

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Debes iniciar sesión."},
            status=401,
        )

    return None


def datos_usuario(usuario):
    """
    Convierte el usuario autenticado a un
    diccionario que puede enviarse como JSON.
    """

    return {
        "id": usuario.pk,
        "username": usuario.username,
        "first_name": usuario.first_name,
        "last_name": usuario.last_name,
        "rol": usuario.rol,
    }


def proyectos_del_investigador(usuario):
    """
    Obtiene los proyectos asociados al investigador.

    Aplica el mismo criterio de asociación que
    la vista mis_proyectos de Gesproy Web.
    """

    investigador = Investigador.objects.filter(
        usuario=usuario
    ).first()

    if investigador is None:
        return Proyecto.objects.none(), None

    proyectos_asociados = Dedicacion.objects.filter(
        investigador=investigador
    ).values("proyecto_id")

    proyectos = Proyecto.objects.filter(
        Q(investigador_principal=investigador)
        | Q(pk__in=proyectos_asociados)
    ).distinct()

    return proyectos, investigador


def datos_proyecto(proyecto, investigador):
    """
    Convierte un proyecto de Django a JSON.
    """

    principal = proyecto.investigador_principal

    if principal is not None:
        usuario_principal = principal.usuario

        nombre_principal = (
            usuario_principal.get_full_name().strip()
            or usuario_principal.username
        )
    else:
        nombre_principal = None

    return {
        "id": proyecto.pk,
        "nombre": proyecto.nombre,
        "acronimo": proyecto.acronimo,
        "estado": proyecto.estado,
        "fecha_inicio": (
            proyecto.fecha_inicio.isoformat()
            if proyecto.fecha_inicio
            else None
        ),
        "fecha_fin": (
            proyecto.fecha_fin.isoformat()
            if proyecto.fecha_fin
            else None
        ),
        "investigador_principal": nombre_principal,
        "es_responsable": (
            investigador is not None
            and proyecto.investigador_principal_id == investigador.pk
        ),
    }


# ==========================================
# CSRF
# ==========================================

@require_GET
@never_cache
@ensure_csrf_cookie
def obtener_csrf(request):
    """
    Prepara la protección CSRF para las
    peticiones POST enviadas desde React.
    """

    return JsonResponse({
        "csrfToken": get_token(request)
    })


# ==========================================
# LOGIN
# ==========================================

@require_POST
@csrf_protect
def iniciar_sesion(request):
    """
    Recibe usuario y contraseña en JSON y
    utiliza la autenticación existente de Django.
    """

    try:
        datos = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "El JSON enviado no es válido."},
            status=400,
        )

    if not isinstance(datos, dict):
        return JsonResponse(
            {"error": "Los datos enviados no son válidos."},
            status=400,
        )

    username = datos.get("username", "")
    password = datos.get("password", "")

    if not isinstance(username, str) or not isinstance(password, str):
        return JsonResponse(
            {"error": "Usuario o contraseña no válidos."},
            status=400,
        )

    username = username.strip()

    if not username or not password:
        return JsonResponse(
            {"error": "Introduce usuario y contraseña."},
            status=400,
        )

    usuario = authenticate(
        request,
        username=username,
        password=password,
    )

    if usuario is None:
        return JsonResponse(
            {"error": "Usuario o contraseña incorrectos."},
            status=401,
        )

    login(request, usuario)

    return JsonResponse({
        "mensaje": "Sesión iniciada correctamente.",
        "usuario": datos_usuario(usuario),
    })


# ==========================================
# LOGOUT
# ==========================================

@require_POST
@csrf_protect
def cerrar_sesion(request):

    logout(request)

    return JsonResponse({
        "mensaje": "Sesión cerrada correctamente."
    })


# ==========================================
# USUARIO AUTENTICADO
# ==========================================

@require_GET
@never_cache
def usuario_actual(request):

    error = comprobar_autenticacion(request)

    if error is not None:
        return error

    return JsonResponse({
        "usuario": datos_usuario(request.user)
    })


# ==========================================
# MIS PROYECTOS
# ==========================================

@require_GET
@never_cache
def mis_proyectos(request):

    error = comprobar_autenticacion(request)

    if error is not None:
        return error

    proyectos, investigador = proyectos_del_investigador(
        request.user
    )

    solo_responsable = (
        request.GET.get("solo_responsable") == "1"
    )

    if solo_responsable and investigador is not None:
        proyectos = proyectos.filter(
            investigador_principal=investigador
        )

    proyectos = proyectos.select_related(
        "investigador_principal__usuario"
    ).order_by("acronimo")

    resultado = [
        datos_proyecto(proyecto, investigador)
        for proyecto in proyectos
    ]

    return JsonResponse({
        "proyectos": resultado,
        "total": len(resultado),
    })


# ==========================================
# DETALLE DEL PROYECTO
# ==========================================

@require_GET
@never_cache
def detalle_proyecto(request, id):

    error = comprobar_autenticacion(request)

    if error is not None:
        return error

    proyectos, investigador = proyectos_del_investigador(
        request.user
    )

    proyecto = get_object_or_404(
        proyectos.select_related(
            "investigador_principal__usuario"
        ),
        pk=id,
    )

    return JsonResponse({
        "proyecto": datos_proyecto(
            proyecto,
            investigador,
        )
    })