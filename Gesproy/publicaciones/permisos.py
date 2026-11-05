from django.db.models import Q
from proyectos.models import Proyecto, Dedicacion
from usuarios.models import Investigador


def proyectos_permitidos(usuario):
    if not usuario.is_authenticated or not usuario.is_active:
        return Proyecto.objects.none()
    if usuario.is_staff or usuario.is_superuser:
        return Proyecto.objects.all()
    investigador_id = Investigador.objects.filter(usuario=usuario).values_list("pk", flat=True).first()
    if investigador_id is None:
        return Proyecto.objects.none()
    asociados = Dedicacion.objects.filter(investigador_id=investigador_id).values("proyecto_id")
    return Proyecto.objects.filter(Q(pk__in=asociados) | Q(investigador_principal_id=investigador_id)).distinct()


def puede_descargar(usuario, publicacion):
    if not usuario.is_authenticated or not usuario.is_active:
        return False
    if publicacion.difusion != publicacion.CONFIDENCIAL:
        return True
    if usuario.is_staff or usuario.is_superuser:
        return True
    return publicacion.proyectos.filter(pk__in=proyectos_permitidos(usuario)).exists()


def puede_editar(usuario, publicacion):
    if not usuario.is_authenticated or not usuario.is_active:
        return False
    return bool(usuario.is_staff or usuario.is_superuser or publicacion.creado_por_id == usuario.pk)