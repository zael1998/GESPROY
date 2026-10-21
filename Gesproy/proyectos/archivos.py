"""Archivos privados por proyecto para Gesproy.

Se reutiliza proyectos.Archivo sin modificar modelos ni migraciones.
Las operaciones físicas usan un almacenamiento PRIVADO, independiente del
FileField predeterminado (no llamar a archivo.ruta_subida.url ni .open).
Nunca expongas `media_privada_gesproy` con una ruta HTTP de Apache/Nginx/Django.
"""

import logging
from pathlib import Path
from uuid import uuid4

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.storage import FileSystemStorage
from django.core.files.utils import validate_file_name
from django.http import FileResponse, Http404
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import get_valid_filename, slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from usuarios.models import Investigador
from .models import Archivo, Dedicacion, Proyecto

logger = logging.getLogger(__name__)

# Carpeta fuera de `static/` y fuera del MEDIA_ROOT público habitual.
# El servidor web NO debe tener alias/ubicaciones que sirvan esta ruta.
CARPETA_PRIVADA = Path(settings.BASE_DIR) / "media_privada_gesproy"
almacen_privado = FileSystemStorage(location=str(CARPETA_PRIVADA), base_url=None)

MAX_BYTES = 20 * 1024 * 1024  # 20 MiB por fichero
EXTENSIONES = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
    ".odt", ".ods", ".odp", ".ppt", ".pptx", ".zip",
    ".png", ".jpg", ".jpeg",
})
ESTADOS_MODIFICABLES = frozenset({
    "DEFINICION", "SOLICITADO", "NEGOCIACION", "PROCESO",
})


class SubirArchivoForm(forms.Form):
    fichero = forms.FileField(
        label="Seleccionar archivo",
        widget=forms.ClearableFileInput(attrs={"class": "ap-input", "accept": ",".join(sorted(EXTENSIONES))}),
    )
    comentario = forms.CharField(
        label="Descripción (opcional)",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "ap-input", "rows": 3,
                                        "placeholder": "¿Qué contiene este archivo?"}),
    )

    def clean_fichero(self):
        fichero = self.cleaned_data["fichero"]
        nombre_original = str(fichero.name).replace("\\", "/").split("/")[-1]
        if not nombre_original or len(nombre_original) > 100:
            raise forms.ValidationError("El nombre del archivo debe tener entre 1 y 100 caracteres.")
        if Path(nombre_original).suffix.lower() not in EXTENSIONES:
            raise forms.ValidationError("Formato no permitido. Utiliza PDF, Office, imagen, texto o ZIP.")
        if fichero.size <= 0 or fichero.size > MAX_BYTES:
            raise forms.ValidationError("El archivo debe ocupar más de 0 bytes y como máximo 20 MB.")
        # Archivo original para mostrarlo, separado de su nombre físico aleatorio.
        self.nombre_original = nombre_original
        return fichero


def _es_administrador(usuario):
    return bool(usuario.is_authenticated and usuario.is_active
                and (usuario.is_staff or usuario.is_superuser))


def _investigador(usuario):
    if not usuario.is_authenticated or not usuario.is_active:
        return None
    return Investigador.objects.filter(usuario=usuario).first()


def _permisos(usuario, proyecto):
    """Solo miembros y administradores; validador NO da acceso a otro proyecto."""
    admin = _es_administrador(usuario)
    investigador = _investigador(usuario)
    principal = bool(investigador and proyecto.investigador_principal_id == investigador.pk)
    asociado = bool(investigador and Dedicacion.objects.filter(
        proyecto=proyecto, investigador=investigador
    ).exists())
    puede_ver = admin or principal or asociado
    puede_gestionar = (admin or principal) and proyecto.estado in ESTADOS_MODIFICABLES
    return puede_ver, puede_gestionar


def _exigir_acceso(usuario, proyecto):
    puede_ver, puede_gestionar = _permisos(usuario, proyecto)
    if not puede_ver:
        raise PermissionDenied("No estás asociado a este proyecto.")
    return puede_gestionar


def _directorio_proyecto(proyecto):
    """Carpeta identificable, por ejemplo: proyectos/5_CESGA-IA/.

    El acrónimo se sanea para que no contenga barras ni caracteres extraños.
    Se limita la longitud porque Archivo.ruta_subida tiene max_length=100.
    El directorio se calcula SOLO al subir: si cambia el acrónimo, los
    archivos anteriores seguirán usando las rutas ya guardadas en la BD.
    """
    acronimo = slugify(proyecto.acronimo or "")[:24].strip("-_").upper()
    if not acronimo:
        acronimo = "SIN-ACRONIMO"
    return f"proyectos/{proyecto.pk}_{acronimo}/"


def _ruta_privada(proyecto, nombre):
    """Ruta privada bajo ID_ACRONIMO con fichero de nombre no adivinable."""
    nombre_seguro = get_valid_filename(nombre)
    if not nombre_seguro:
        nombre_seguro = "archivo"
    prefijo = f"{_directorio_proyecto(proyecto)}{uuid4().hex}_"
    # El FileField existente admite 100 caracteres por defecto.
    longitud_maxima = Archivo._meta.get_field("ruta_subida").max_length
    espacio_nombre = longitud_maxima - len(prefijo)
    extension = Path(nombre_seguro).suffix
    if espacio_nombre < max(10, len(extension) + 1):
        raise ValueError("La ruta del proyecto es demasiado larga.")
    if len(nombre_seguro) > espacio_nombre:
        nombre_seguro = nombre_seguro[:espacio_nombre - len(extension)] + extension
    ruta = prefijo + nombre_seguro
    validate_file_name(ruta, allow_relative_path=True)
    return ruta


def _ruta_compatible(proyecto, ruta):
    """Admite las carpetas antiguas por ID y las nuevas por ID_ACRONIMO.

    No depende del acrónimo actual: un proyecto puede cambiar de nombre.
    """
    prefijo_antiguo = f"proyectos/{proyecto.pk}/"
    prefijo_nuevo = f"proyectos/{proyecto.pk}_"
    if ruta.startswith(prefijo_antiguo):
        return bool(ruta[len(prefijo_antiguo):])
    if ruta.startswith(prefijo_nuevo):
        resto = ruta[len(prefijo_nuevo):]
        partes = resto.split("/", 1)
        return len(partes) == 2 and bool(partes[0]) and bool(partes[1])
    return False


def _documento_del_proyecto(proyecto, archivo_id):
    """Comprueba que el archivo pertenece al proyecto y a su almacén privado."""
    doc = get_object_or_404(Archivo, pk=archivo_id, proyecto=proyecto)
    ruta = str(doc.ruta_subida.name or "")
    if not _ruta_compatible(proyecto, ruta):
        # Documentos de un sistema anterior con MEDIA_ROOT público
        # necesitarán una migración controlada antes de acceder a ellos.
        raise Http404("El archivo no está en el almacenamiento privado.")
    validate_file_name(ruta, allow_relative_path=True)
    return doc, ruta


@login_required
def archivos_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    puede_gestionar = _exigir_acceso(request.user, proyecto)

    if request.method == "POST" and not puede_gestionar:
        raise PermissionDenied("No tienes permiso para subir archivos.")

    formulario = SubirArchivoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )

    if request.method == "POST" and formulario.is_valid():
        fichero = formulario.cleaned_data["fichero"]
        archivo = Archivo(
            nombre=formulario.nombre_original,
            proyecto=proyecto,
            fecha_subida=timezone.localdate(),
            tamaño=fichero.size,
            comentario=formulario.cleaned_data["comentario"],
            visible=True,
            carpeta=None,  # Una carpeta por proyecto, sin subcarpetas.
        )
        ruta_guardada = None
        try:
            ruta_guardada = almacen_privado.save(
                _ruta_privada(proyecto, formulario.nombre_original), fichero
            )
            # Guardamos solo el nombre RELATIVO. No usamos el almacenamiento
            # público del FileField, ni exponemos ninguna URL de media.
            archivo.ruta_subida.name = ruta_guardada
            archivo.full_clean(exclude=["ruta_subida"])
            archivo.save()
        except Exception:
            if ruta_guardada:
                almacen_privado.delete(ruta_guardada)
            logger.exception("No se pudo subir un archivo al proyecto %s", proyecto.pk)
            messages.error(request, "No se pudo guardar el archivo. Revisa los permisos y el espacio en disco.")
        else:
            messages.success(request, "Archivo subido correctamente.")
            return redirect("archivos_proyecto", proyecto_id=proyecto.pk)

    # Lista archivos guardados con el formato antiguo (ID) y el nuevo
    # (ID_ACRONIMO). Mantiene la compatibilidad incluso si cambia el acrónimo.
    archivos = Archivo.objects.filter(proyecto=proyecto).filter(
        Q(ruta_subida__startswith=f"proyectos/{proyecto.pk}/")
        | Q(ruta_subida__startswith=f"proyectos/{proyecto.pk}_")
    ).order_by("-fecha_subida", "-pk")

    return render(request, "proyectos/archivos_proyecto.html", {
        "proyecto": proyecto,
        "archivos": archivos,
        "formulario": formulario,
        "puede_gestionar": puede_gestionar,
        "cantidad_archivos": archivos.count(),
    })


@login_required
@never_cache
def descargar_archivo(request, proyecto_id, archivo_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    _exigir_acceso(request.user, proyecto)
    documento, ruta = _documento_del_proyecto(proyecto, archivo_id)
    try:
        fichero = almacen_privado.open(ruta, mode="rb")
    except (FileNotFoundError, OSError):
        raise Http404("El archivo no se encuentra en el servidor.")

    respuesta = FileResponse(
        fichero,
        as_attachment=True,
        filename=documento.nombre,
        content_type="application/octet-stream",
    )
    respuesta["Cache-Control"] = "private, no-store"
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta


@login_required
@require_POST
def eliminar_archivo(request, proyecto_id, archivo_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    puede_gestionar = _exigir_acceso(request.user, proyecto)
    if not puede_gestionar:
        raise PermissionDenied("No tienes permiso para eliminar archivos.")

    documento, ruta = _documento_del_proyecto(proyecto, archivo_id)
    documento.delete()
    # Primero se elimina el registro; si fallase el sistema de ficheros,
    # queda un fichero huérfano, pero nunca una referencia rota en la interfaz.
    try:
        almacen_privado.delete(ruta)
    except OSError:
        logger.exception("No se pudo borrar físicamente el archivo %s", ruta)
        messages.warning(request, "Archivo retirado del listado, pero debes revisar el disco.")
    else:
        messages.success(request, "Archivo eliminado correctamente.")
    return redirect("archivos_proyecto", proyecto_id=proyecto.pk)