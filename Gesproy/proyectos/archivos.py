"""Gestor privado de documentos Gesproy (archivos y carpetas lógicas).

Reutiliza Archivo y Carpeta de proyectos.models. Las carpetas son registros
lógicos en BD: mover/renombrar NO modifica la ruta privada física.
El almacenamiento privado NO se publica mediante MEDIA_URL ni STATIC_URL.
"""

from __future__ import annotations

import io
import logging
import stat
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.utils import validate_file_name
from django.db import transaction
from django.db.models import Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.text import get_valid_filename, slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from usuarios.models import Investigador
from .models import Archivo, Carpeta, Dedicacion, Proyecto

logger = logging.getLogger(__name__)
CARPETA_PRIVADA = Path(settings.BASE_DIR) / "media_privada_gesproy"
almacen_privado = FileSystemStorage(location=str(CARPETA_PRIVADA), base_url=None)
MAX_ARCHIVO = 2 * 1024 * 1024  # 2 MiB, manual
MAX_PROYECTO = 100 * 1024 * 1024  # 100 MiB, manual
MAX_ELEMENTOS_ZIP = 250
MAX_PROFUNDIDAD = 10
EXTENSIONES = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
    ".odt", ".ods", ".odp", ".ppt", ".pptx", ".zip",
    ".png", ".jpg", ".jpeg",
})
ESTADOS_PREVIOS = frozenset({"DEFINICION", "SOLICITADO", "NEGOCIACION"})


class SubirArchivoForm(forms.Form):
    fichero = forms.FileField(
        label="Seleccionar archivo",
        widget=forms.ClearableFileInput(attrs={
            "class": "ap-input", "accept": ",".join(sorted(EXTENSIONES)),
        }),
    )
    comentario = forms.CharField(
        required=False, max_length=1000,
        widget=forms.Textarea(attrs={"class": "ap-input", "rows": 2}),
    )
    descomprimir_zip = forms.BooleanField(required=False, label="Descomprimir ZIP en carpetas")

    def clean_fichero(self):
        f = self.cleaned_data["fichero"]
        self.nombre_original = _nombre_valido(f.name, archivo=True)
        if not 0 < f.size <= MAX_ARCHIVO:
            raise forms.ValidationError("Cada fichero debe ocupar entre 1 byte y 2 MiB.")
        return f

    def clean(self):
        data = super().clean()
        if data.get("descomprimir_zip") and (
            not data.get("fichero") or Path(self.nombre_original).suffix.lower() != ".zip"
        ):
            raise forms.ValidationError("La opción de descomprimir solo se admite para ZIP.")
        return data


def _nombre_valido(valor, *, archivo=False):
    """No acepta segmentos de ruta; permite nombres legibles hasta 100 caracteres."""
    nombre = str(valor or "").strip()
    if (not nombre or len(nombre) > 100 or nombre in {".", ".."}
            or "/" in nombre or "\\" in nombre or ":" in nombre
            or any(ord(c) < 32 for c in nombre)):
        raise ValidationError("Nombre no válido (máximo 100 caracteres y sin barras).")
    if archivo and Path(nombre).suffix.lower() not in EXTENSIONES:
        raise ValidationError("Tipo de fichero no permitido.")
    return nombre


def _admin(usuario):
    return bool(usuario.is_authenticated and usuario.is_active
                and (usuario.is_staff or usuario.is_superuser))


def _investigador(usuario):
    if not usuario.is_authenticated or not usuario.is_active:
        return None
    return Investigador.objects.filter(usuario=usuario).first()


def _permisos(usuario, proyecto):
    """(ver, gestionar, privilegiado) conforme a estados y roles del manual."""
    admin = _admin(usuario)
    inv = _investigador(usuario)
    principal = bool(inv and proyecto.investigador_principal_id == inv.pk)
    asociado = bool(inv and Dedicacion.objects.filter(
        proyecto=proyecto, investigador=inv
    ).exists())
    privilegiado = admin or principal
    estado = proyecto.estado
    if estado in ESTADOS_PREVIOS:
        ver = admin or principal or asociado
        gestionar = ver
    elif estado == "PROCESO":
        ver = admin or bool(inv)  # Visibles para investigadores, asociados o no
        gestionar = privilegiado
    elif estado == "FINALIZADO":
        ver = admin or bool(inv)
        gestionar = False
    elif estado == "DENEGADO":
        ver = admin or principal or asociado
        gestionar = False
    else:
        ver = gestionar = False
    return ver, gestionar, privilegiado


def _acceso(usuario, proyecto, *, escritura=False):
    ver, gestionar, privilegiado = _permisos(usuario, proyecto)
    if not ver or (escritura and not gestionar):
        raise PermissionDenied("No tienes permiso para esta operación de documentos.")
    return gestionar, privilegiado


def _carpeta(proyecto, carpeta_id, usuario):
    """Comprueba pertenencia, visibilidad heredada y evita ciclos anómalos."""
    if not carpeta_id:
        return None
    if not str(carpeta_id).isdecimal():
        raise Http404("Identificador de carpeta incorrecto.")
    actual = get_object_or_404(Carpeta, pk=int(carpeta_id), proyecto=proyecto)
    if _permisos(usuario, proyecto)[2]:
        return actual
    visto = set()
    nodo = actual
    while nodo is not None:
        if nodo.pk in visto or nodo.proyecto_id != proyecto.pk:
            raise PermissionDenied("Estructura de carpetas inválida.")
        visto.add(nodo.pk)
        if not nodo.visible:
            raise PermissionDenied("Esta carpeta no es visible para tu usuario.")
        nodo = nodo.carpeta_padre
    return actual


def _ruta_privada(proyecto, nombre):
    acronimo = slugify(proyecto.acronimo or "")[:24].strip("-_").upper()
    base = f"proyectos/{proyecto.pk}_{acronimo or 'SIN-ACRONIMO'}/"
    prefijo = base + uuid4().hex + "_"
    max_len = Archivo._meta.get_field("ruta_subida").max_length
    limpio = get_valid_filename(nombre)
    extension = Path(limpio).suffix
    disponible = max_len - len(prefijo)
    if disponible <= len(extension) + 5:
        raise ValidationError("Ruta de archivo demasiado larga.")
    if len(limpio) > disponible:
        limpio = limpio[:disponible - len(extension)] + extension
    ruta = prefijo + limpio
    validate_file_name(ruta, allow_relative_path=True)
    return ruta


def _ruta_compatible(proyecto, ruta):
    p = f"proyectos/{proyecto.pk}/"
    q = f"proyectos/{proyecto.pk}_"
    if ruta.startswith(p):
        return bool(ruta[len(p):])
    if ruta.startswith(q):
        resto = ruta[len(q):].split("/", 1)
        return len(resto) == 2 and all(resto)
    return False


def _documento(proyecto, archivo_id, usuario):
    doc = get_object_or_404(Archivo, pk=archivo_id, proyecto=proyecto)
    _carpeta(proyecto, doc.carpeta_id, usuario)
    if not doc.visible and not _permisos(usuario, proyecto)[2]:
        raise PermissionDenied("Este documento está oculto.")
    ruta = str(doc.ruta_subida.name or "")
    if not _ruta_compatible(proyecto, ruta):
        raise Http404("Archivo antiguo pendiente de migración al almacenamiento privado.")
    validate_file_name(ruta, allow_relative_path=True)
    return doc, ruta


def _archivos_qs(proyecto):
    return Archivo.objects.filter(proyecto=proyecto).filter(
        Q(ruta_subida__startswith=f"proyectos/{proyecto.pk}/") |
        Q(ruta_subida__startswith=f"proyectos/{proyecto.pk}_")
    )


def _carpetas_descendientes(proyecto, raiz):
    """Orden descendiente (raíz primero); protege ante ciclos."""
    lista = [raiz]
    visitados = {raiz.pk}
    for nodo in lista:
        hijos = Carpeta.objects.filter(proyecto=proyecto, carpeta_padre=nodo)
        for hijo in hijos:
            if hijo.pk in visitados:
                raise ValidationError("Ciclo detectado entre carpetas.")
            visitados.add(hijo.pk)
            lista.append(hijo)
        if len(lista) > 10000:
            raise ValidationError("Demasiadas carpetas en esta operación.")
    return lista


def _destino(request, proyecto, usuario):
    valor = request.POST.get("destino", "").strip()
    if not valor:
        return None
    if not valor.isdecimal():
        raise ValidationError("Carpeta de destino inválida.")
    return _carpeta(proyecto, int(valor), usuario)


def _nombre_libre(proyecto, carpeta, nombre, *, excluir=None):
    """Desambigua solo el NUEVO fichero sin tocar los existentes."""
    raiz, sufijo = str(Path(nombre).with_suffix("")), Path(nombre).suffix
    prueba = nombre
    indice = 1
    while Archivo.objects.filter(proyecto=proyecto, carpeta=carpeta,
                                  nombre__iexact=prueba).exclude(pk=excluir).exists():
        cola = f"_{indice}{sufijo}"
        prueba = raiz[:100-len(cola)] + cola
        indice += 1
    return prueba


def _nombre_carpeta_disponible(proyecto, padre, nombre, *, excluir=None):
    return not Carpeta.objects.filter(
        proyecto=proyecto, carpeta_padre=padre, nombre__iexact=nombre,
    ).exclude(pk=excluir).exists()


def _url_listado(proyecto, carpeta):
    url = reverse("archivos_proyecto", args=[proyecto.pk])
    return f"{url}?{urlencode({'carpeta': carpeta.pk})}" if carpeta else url


def _guardar_fisico(proyecto, carpeta, nombre, contenido, comentario=""):
    """Llamar dentro de transaction.atomic. El llamador limpia ante error."""
    nombre = _nombre_libre(proyecto, carpeta, nombre)
    ruta = almacen_privado.save(_ruta_privada(proyecto, nombre), contenido)
    try:
        doc = Archivo(
            proyecto=proyecto, carpeta=carpeta, nombre=nombre,
            ruta_subida=ruta, fecha_subida=timezone.localdate(),
            tamaño=contenido.size, visible=True, comentario=comentario,
        )
        doc.full_clean()
        doc.save()
    except Exception:
        almacen_privado.delete(ruta)
        raise
    return ruta


def _leer_zip(fichero):
    """Extrae a memoria archivos acotados. Bloquea zip slip y zip bombs."""
    preparados = []
    total_extraido = 0
    try:
        fichero.seek(0)
        with ZipFile(io.BytesIO(fichero.read(MAX_ARCHIVO + 1))) as comprimido:
            for info in comprimido.infolist():
                if info.is_dir():
                    continue
                if len(preparados) >= MAX_ELEMENTOS_ZIP:
                    raise ValidationError("ZIP con más de 250 archivos.")
                nombre = info.filename
                if (nombre.startswith("/") or "\\" in nombre or "\x00" in nombre
                        or ":" in nombre or any(p in {".", "..", ""} for p in nombre.split("/"))):
                    raise ValidationError("El ZIP contiene rutas no permitidas.")
                partes = PurePosixPath(nombre).parts
                if len(partes) > MAX_PROFUNDIDAD:
                    raise ValidationError("Profundidad de carpetas ZIP excesiva.")
                partes = tuple(
                    _nombre_valido(parte, archivo=(indice == len(partes) - 1))
                    for indice, parte in enumerate(partes)
                )
                tipo = (info.external_attr >> 16) & 0o170000
                if tipo == stat.S_IFLNK:
                    raise ValidationError("No se admiten enlaces simbólicos en ZIP.")
                if info.flag_bits & 1 or info.file_size > MAX_ARCHIVO:
                    raise ValidationError("ZIP cifrado o con archivo de más de 2 MiB.")
                with comprimido.open(info) as entrada:
                    datos = entrada.read(MAX_ARCHIVO + 1)
                if not 0 < len(datos) <= MAX_ARCHIVO:
                    raise ValidationError("Archivo ZIP vacío o demasiado grande.")
                total_extraido += len(datos)
                if total_extraido > MAX_PROYECTO:
                    raise ValidationError("El ZIP descomprimido supera los 100 MiB.")
                preparados.append((partes, datos))
    except (BadZipFile, RuntimeError, OSError, EOFError) as exc:
        raise ValidationError("El ZIP no es válido o está dañado.") from exc
    if not preparados:
        raise ValidationError("El ZIP no contiene archivos compatibles.")
    return preparados


def _carpeta_zip(proyecto, actual, ruta_directorios):
    for nombre in ruta_directorios:
        sub = Carpeta.objects.filter(
            proyecto=proyecto, carpeta_padre=actual, nombre__iexact=nombre
        ).first()
        if sub is None:
            sub = Carpeta.objects.create(
                proyecto=proyecto, carpeta_padre=actual,
                nombre=nombre, comentario="", visible=True,
            )
        actual = sub
    return actual


@login_required
@never_cache
def archivos_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    puede_gestionar, privilegiado = _acceso(request.user, proyecto)
    id_actual = request.POST.get("carpeta_actual") if request.method == "POST" else request.GET.get("carpeta")
    actual = _carpeta(proyecto, id_actual, request.user)
    form = SubirArchivoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    if request.method == "POST":
        _acceso(request.user, proyecto, escritura=True)
        if form.is_valid():
            fichero = form.cleaned_data["fichero"]
            rutas_creadas = []
            try:
                archivos_zip = (_leer_zip(fichero) if form.cleaned_data["descomprimir_zip"]
                                else None)
                tamanio = (sum(len(data) for _, data in archivos_zip)
                           if archivos_zip is not None else fichero.size)
                with transaction.atomic():
                    Proyecto.objects.select_for_update().get(pk=proyecto.pk)
                    ocupado = Archivo.objects.filter(proyecto=proyecto).aggregate(
                        total=Sum("tamaño")
                    )["total"] or 0
                    if ocupado + tamanio > MAX_PROYECTO:
                        raise ValidationError("Supera los 100 MiB permitidos en este proyecto.")
                    if archivos_zip is None:
                        rutas_creadas.append(_guardar_fisico(
                            proyecto, actual, form.nombre_original, fichero,
                            form.cleaned_data["comentario"],
                        ))
                    else:
                        for partes, data in archivos_zip:
                            destino = _carpeta_zip(proyecto, actual, partes[:-1])
                            if not privilegiado:
                                _carpeta(proyecto, destino.pk, request.user)
                            rutas_creadas.append(_guardar_fisico(
                                proyecto, destino, partes[-1], ContentFile(data),
                            ))
            except ValidationError as exc:
                for ruta in rutas_creadas:
                    almacen_privado.delete(ruta)
                form.add_error(None, exc)
            except Exception:
                for ruta in rutas_creadas:
                    almacen_privado.delete(ruta)
                logger.exception("Error al guardar documentos de proyecto %s", proyecto.pk)
                form.add_error(None, "No se pudieron guardar los archivos.")
            else:
                messages.success(request, "Documento(s) guardado(s) correctamente.")
                return redirect(_url_listado(proyecto, actual))

    # La lista de carpetas y rutas se filtra también en el servidor.
    carpetas_hijas = list(Carpeta.objects.filter(
        proyecto=proyecto, carpeta_padre=actual,
    ).order_by("nombre", "pk"))
    carpetas_hijas = [c for c in carpetas_hijas if privilegiado or c.visible]
    archivos = _archivos_qs(proyecto).filter(carpeta=actual).order_by("nombre", "pk")
    if not privilegiado:
        archivos = archivos.filter(visible=True)
    opciones = []
    for carpeta in Carpeta.objects.filter(proyecto=proyecto).order_by("nombre", "pk"):
        if not privilegiado:
            try:
                _carpeta(proyecto, carpeta.pk, request.user)
            except PermissionDenied:
                continue
        # Etiqueta de la ruta completa para distinguir carpetas homónimas.
        cadena = []
        parte = carpeta
        recorrido = set()
        while parte is not None:
            if parte.pk in recorrido or parte.proyecto_id != proyecto.pk:
                raise PermissionDenied("Estructura de carpetas inválida.")
            recorrido.add(parte.pk)
            cadena.append(parte.nombre)
            parte = parte.carpeta_padre
        carpeta.etiqueta = " / ".join(reversed(cadena))
        opciones.append(carpeta)
    # Breadcrumbs de raíz a carpeta actual.
    migas = []
    nodo = actual
    while nodo is not None:
        migas.append(nodo)
        nodo = nodo.carpeta_padre
        if len(migas) > 1000:
            raise PermissionDenied("Jerarquía de carpetas inválida.")
    migas.reverse()
    ocupado = Archivo.objects.filter(proyecto=proyecto).aggregate(total=Sum("tamaño"))["total"] or 0
    return render(request, "proyectos/archivos_proyecto.html", {
        "proyecto": proyecto,
        "archivos": archivos,
        "carpetas": carpetas_hijas,
        "opciones_destino": opciones,
        "actual": actual,
        "migas": migas,
        "padre": actual.carpeta_padre if actual else None,
        "formulario": form,
        "puede_gestionar": puede_gestionar,
        "privilegiado": privilegiado,
        "cantidad_archivos": archivos.count(),
        "ocupado": ocupado,
        "limite_proyecto": MAX_PROYECTO,
    })


@login_required
@never_cache
def descargar_archivo(request, proyecto_id, archivo_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    _acceso(request.user, proyecto)
    documento, ruta = _documento(proyecto, archivo_id, request.user)
    try:
        fichero = almacen_privado.open(ruta, mode="rb")
    except (OSError, FileNotFoundError):
        raise Http404("No existe el documento en el disco privado.")
    respuesta = FileResponse(fichero, as_attachment=True, filename=documento.nombre,
                             content_type="application/octet-stream")
    respuesta["Cache-Control"] = "private, no-store"
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta


@login_required
@require_POST
@transaction.atomic
def eliminar_archivo(request, proyecto_id, archivo_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    _acceso(request.user, proyecto, escritura=True)
    documento, ruta = _documento(proyecto, archivo_id, request.user)
    ubicacion = documento.carpeta
    documento.delete()
    def borrar_fichero():
        try:
            almacen_privado.delete(ruta)
        except OSError:
            logger.exception("No se pudo borrar el archivo %s", ruta)
    transaction.on_commit(borrar_fichero)
    messages.success(request, "Documento eliminado.")
    return redirect(_url_listado(proyecto, ubicacion))


@login_required
@require_POST
def _gestionar_archivo_impl(request, proyecto_id, archivo_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    _acceso(request.user, proyecto, escritura=True)
    accion = request.POST.get("accion")
    with transaction.atomic():
        Proyecto.objects.select_for_update().get(pk=proyecto.pk)
        archivo, ruta = _documento(proyecto, archivo_id, request.user)
        actual = archivo.carpeta
        if accion == "renombrar":
            nombre = request.POST.get("nombre", "")
            if not Path(nombre).suffix:
                nombre += Path(archivo.nombre).suffix
            nombre = _nombre_valido(nombre, archivo=True)
            if Path(nombre).suffix.lower() != Path(archivo.nombre).suffix.lower():
                raise ValidationError("No se permite cambiar la extensión del archivo.")
            if Archivo.objects.filter(proyecto=proyecto, carpeta=actual, nombre__iexact=nombre).exclude(pk=archivo.pk).exists():
                messages.error(request, "Ya existe otro documento con ese nombre.")
            else:
                archivo.nombre = nombre
                archivo.save(update_fields=["nombre"])
                messages.success(request, "Documento renombrado.")
        elif accion == "comentario":
            comentario = request.POST.get("comentario", "").strip()
            if len(comentario) > 5000:
                messages.error(request, "Comentario demasiado largo.")
            else:
                archivo.comentario = comentario
                archivo.save(update_fields=["comentario"])
                messages.success(request, "Comentario actualizado.")
        elif accion == "mover":
            destino = _destino(request, proyecto, request.user)
            if Archivo.objects.filter(proyecto=proyecto, carpeta=destino, nombre__iexact=archivo.nombre).exclude(pk=archivo.pk).exists():
                messages.error(request, "Ya existe un documento con ese nombre en destino.")
            else:
                archivo.carpeta = destino
                archivo.save(update_fields=["carpeta"])
                messages.success(request, "Documento movido.")
        elif accion == "visibilidad":
            if not _permisos(request.user, proyecto)[2]:
                raise PermissionDenied("Solo administrador o responsable puede ocultar archivos.")
            archivo.visible = not archivo.visible
            archivo.save(update_fields=["visible"])
            messages.success(request, "Visibilidad actualizada.")
        else:
            raise Http404("Operación no reconocida.")
    return redirect(_url_listado(proyecto, actual))


@login_required
@require_POST
def _gestionar_carpeta_impl(request, proyecto_id, carpeta_id=None):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    _acceso(request.user, proyecto, escritura=True)
    accion = request.POST.get("accion")
    with transaction.atomic():
        Proyecto.objects.select_for_update().get(pk=proyecto.pk)
        actual = _carpeta(proyecto, carpeta_id, request.user) if carpeta_id else None
        ubicacion = actual.carpeta_padre if actual else _carpeta(
            proyecto, request.POST.get("carpeta_actual"), request.user
        )
        if accion == "crear":
            nombre = _nombre_valido(request.POST.get("nombre", ""))
            if not _nombre_carpeta_disponible(proyecto, ubicacion, nombre):
                messages.error(request, "Ya existe una carpeta con ese nombre.")
            else:
                Carpeta.objects.create(
                    proyecto=proyecto, carpeta_padre=ubicacion,
                    nombre=nombre, comentario="", visible=True,
                )
                messages.success(request, "Carpeta creada.")
        elif actual is None:
            raise Http404("Carpeta no encontrada.")
        elif accion == "renombrar":
            nombre = _nombre_valido(request.POST.get("nombre", ""))
            if not _nombre_carpeta_disponible(proyecto, actual.carpeta_padre, nombre, excluir=actual.pk):
                messages.error(request, "Ya existe otra carpeta con ese nombre.")
            else:
                actual.nombre = nombre
                actual.save(update_fields=["nombre"])
                messages.success(request, "Carpeta renombrada.")
        elif accion == "comentario":
            comentario = request.POST.get("comentario", "").strip()
            if len(comentario) > 5000:
                messages.error(request, "Comentario demasiado largo.")
            else:
                actual.comentario = comentario
                actual.save(update_fields=["comentario"])
                messages.success(request, "Comentario actualizado.")
        elif accion == "mover":
            destino = _destino(request, proyecto, request.user)
            descendientes = _carpetas_descendientes(proyecto, actual)
            if destino is not None and destino.pk in {n.pk for n in descendientes}:
                messages.error(request, "No puedes mover una carpeta dentro de sí misma.")
            elif not _nombre_carpeta_disponible(proyecto, destino, actual.nombre, excluir=actual.pk):
                messages.error(request, "Ya existe una carpeta con ese nombre en destino.")
            else:
                actual.carpeta_padre = destino
                actual.save(update_fields=["carpeta_padre"])
                messages.success(request, "Carpeta movida.")
        elif accion == "visibilidad":
            if not _permisos(request.user, proyecto)[2]:
                raise PermissionDenied("Solo administrador o responsable puede ocultar carpetas.")
            actual.visible = not actual.visible
            actual.save(update_fields=["visible"])
            messages.success(request, "Visibilidad de la carpeta actualizada.")
        elif accion == "eliminar":
            if request.POST.get("confirmar") != "SI":
                messages.error(request, "Confirma la eliminación de la carpeta.")
            else:
                descendientes = _carpetas_descendientes(proyecto, actual)
                # Los usuarios sin privilegios no pueden eliminar contenido oculto.
                if not _permisos(request.user, proyecto)[2]:
                    if any(not c.visible for c in descendientes):
                        raise PermissionDenied("No puedes eliminar carpetas ocultas.")
                    if Archivo.objects.filter(
                        proyecto=proyecto, carpeta__in=descendientes, visible=False
                    ).exists():
                        raise PermissionDenied("Esta carpeta contiene documentos ocultos.")
                rutas = []
                for c in reversed(descendientes):
                    docs = list(Archivo.objects.filter(proyecto=proyecto, carpeta=c))
                    for doc in docs:
                        _, ruta = _documento(proyecto, doc.pk, request.user)
                        rutas.append(ruta)
                        doc.delete()
                    c.delete()
                def limpiar():
                    for ruta in rutas:
                        try:
                            almacen_privado.delete(ruta)
                        except OSError:
                            logger.exception("Error al borrar archivo privado %s", ruta)
                transaction.on_commit(limpiar)
                messages.success(request, "Carpeta y contenido eliminados.")
        else:
            raise Http404("Operación no reconocida.")
    return redirect(_url_listado(proyecto, ubicacion))


# Capturar los errores de validación sin convertirlos en errores HTTP 500.
@login_required
@require_POST
def gestionar_archivo(request, proyecto_id, archivo_id):
    try:
        return _gestionar_archivo_impl(request, proyecto_id, archivo_id)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("archivos_proyecto", proyecto_id=proyecto_id)


@login_required
@require_POST
def gestionar_carpeta(request, proyecto_id, carpeta_id=None):
    try:
        return _gestionar_carpeta_impl(request, proyecto_id, carpeta_id)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("archivos_proyecto", proyecto_id=proyecto_id)