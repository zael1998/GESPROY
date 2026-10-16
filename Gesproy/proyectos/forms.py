
from django import forms
from .models import Proyecto, Socio, ContactoSocio, TipoProyecto, Organismo, TipoParticipacion, Area, LineaInvestigacion, Festivo
from usuarios.models import Investigador
from django.db import transaction
from decimal import Decimal



# ==========================================
# CREAR PROYECTO
# ==========================================

class ProyectoForm(forms.ModelForm):

    class Meta:
        model = Proyecto

        fields = [
            "acronimo",
            "nombre",
            "areas",
            "investigador_principal",
            "fecha_final_prevista",
            "comentario",
        ]

        widgets = {
            "fecha_final_prevista": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
        }


# ==========================================
# EDITAR PROYECTO EN DEFINICIÓN
# ==========================================

class EditarProyectoDefinicionForm(forms.ModelForm):

    class Meta:
        model = Proyecto

        fields = [
            "acronimo",
            "nombre",
            "enlace_proyecto",
            "fecha_final_prevista",
            "areas",
            "comentario",
        ]

        labels = {
            "acronimo": "Acrónimo",
            "nombre": "Nombre del proyecto",
            "enlace_proyecto": "Enlace al proyecto",
            "fecha_final_prevista": "Fecha prevista",
            "areas": "Áreas de investigación",
            "comentario": "Comentario",
        }

        widgets = {
            "fecha_final_prevista": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "comentario": forms.Textarea(
                attrs={"rows": 3}
            ),
        }


# ==========================================
# CAMBIAR DE DEFINICIÓN A SOLICITADO
# ==========================================

class SolicitarProyectoForm(forms.ModelForm):

    class Meta:
        model = Proyecto

        fields = [
            "acronimo",
            "nombre",
            "organismo",
            "tipo_proyecto",
            "porcentaje_subvencion",
            "importe_solicitado",
            "importe_solicitado_cesga",
            "fecha_solicitud",
            "fecha_prevista_resolucion",
            "tipo_participacion",
            "duracion",
            "porcentaje_exito",
            "comentario",
        ]

        labels = {
            "acronimo": "Acrónimo",
            "nombre": "Nombre",
            "organismo": "Organismo",
            "tipo_proyecto": "Tipo Proyecto",
            "porcentaje_subvencion": "Porcentaje",
            "importe_solicitado": "Cantidad Total",
            "importe_solicitado_cesga": "Cantidad CESGA",
            "fecha_solicitud": "Fecha Solicitud",
            "fecha_prevista_resolucion": "Fecha Resolución",
            "tipo_participacion": "Participación",
            "duracion": "Duración",
            "porcentaje_exito": "Porcentaje Éxito",
            "comentario": "Comentario",
        }

        widgets = {
            "fecha_solicitud": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "fecha_prevista_resolucion": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "comentario": forms.Textarea(
                attrs={"rows": 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        campos_obligatorios = [
            "acronimo",
            "nombre",
            "organismo",
            "tipo_proyecto",
            "porcentaje_subvencion",
            "importe_solicitado",
            "fecha_solicitud",
            "tipo_participacion",
            "duracion",
        ]

        for campo in campos_obligatorios:
            self.fields[campo].required = True


# ==========================================
# CAMBIAR DE DEFINICIÓN A FINALIZADO
# ==========================================

class FinalizarProyectoDefinicionForm(forms.ModelForm):

    fecha_fin = forms.DateField(
        required=True,
        label="Fecha Fin",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d"
        )
    )

    class Meta:
        model = Proyecto

        fields = [
            "fecha_fin",
            "comentario",
        ]

        labels = {
            "comentario": "Comentario",
        }

        widgets = {
            "comentario": forms.Textarea(
                attrs={"rows": 3}
            ),
        }


# ==========================================
# EDITAR PROYECTO SOLICITADO
# ==========================================

class EditarProyectoSolicitadoForm(SolicitarProyectoForm):

    class Meta(SolicitarProyectoForm.Meta):

        # Reutilizamos todos los campos menos porcentaje_exito
        fields = [
            campo
            for campo in SolicitarProyectoForm.Meta.fields
            if campo != "porcentaje_exito"
        ]

        # Añadimos enlace_proyecto en tercera posición
        fields.insert(2, "enlace_proyecto")

        labels = {
            **SolicitarProyectoForm.Meta.labels,
            "enlace_proyecto": "Enlace al proyecto",
        }


# ==========================================
# CAMBIAR DE SOLICITADO A NEGOCIACIÓN
# ==========================================

class NegociarProyectoForm(SolicitarProyectoForm):

    class Meta(SolicitarProyectoForm.Meta):

        # Reutilizamos los campos excepto los excluidos
        fields = [
            campo
            for campo in SolicitarProyectoForm.Meta.fields
            if campo not in [
                "porcentaje_exito",
                "fecha_prevista_resolucion",
            ]
        ]

        # Añadimos los campos específicos de negociación
        fields.extend([
            "fecha_resolucion",
            "importe_concedido",
            "importe_concedido_cesga",
        ])

        labels = {
            **SolicitarProyectoForm.Meta.labels,
            "fecha_resolucion": "Fecha Resolución",
            "importe_concedido": "Importe Total",
            "importe_concedido_cesga": "Importe CESGA",
        }

        widgets = {
            **SolicitarProyectoForm.Meta.widgets,
            "fecha_resolucion": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        campos_obligatorios = [
            "fecha_resolucion",
            "importe_concedido",
            "importe_concedido_cesga",
        ]

        for campo in campos_obligatorios:
            self.fields[campo].required = True


# ==========================================
# CAMBIAR PROYECTO A PROCESO
# ==========================================

class PasarProyectoAProcesoForm(NegociarProyectoForm):

    class Meta(NegociarProyectoForm.Meta):

        fields = [
            *NegociarProyectoForm.Meta.fields,
            "fecha_inicio",
        ]

        labels = {
            **NegociarProyectoForm.Meta.labels,
            "fecha_inicio": "Fecha de inicio",
        }

        widgets = {
            **NegociarProyectoForm.Meta.widgets,
            "fecha_inicio": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["fecha_inicio"].required = True


# ==========================================
# CAMBIAR PROYECTO A DENEGADO
# ==========================================

class PasarProyectoADenegadoForm(SolicitarProyectoForm):

    class Meta(SolicitarProyectoForm.Meta):

        fields = [
            campo
            for campo in SolicitarProyectoForm.Meta.fields
            if campo not in [
                "porcentaje_exito",
                "fecha_prevista_resolucion",
            ]
        ]

        fields.extend([
            "fecha_resolucion",
            "causa_denegacion",
        ])

        labels = {
            **SolicitarProyectoForm.Meta.labels,
            "fecha_resolucion": "Fecha de resolución",
            "causa_denegacion": "Causa de denegación",
        }

        widgets = {
            **SolicitarProyectoForm.Meta.widgets,
            "fecha_resolucion": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "causa_denegacion": forms.Textarea(
                attrs={"rows": 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["fecha_resolucion"].required = True
        self.fields["causa_denegacion"].required = True


# ==========================================
# EDITAR PROYECTO EN NEGOCIACIÓN
# ==========================================

class EditarProyectoNegociacionForm(NegociarProyectoForm):

    class Meta(NegociarProyectoForm.Meta):

        # Reutilizamos los campos de negociación
        fields = [
            *NegociarProyectoForm.Meta.fields,
        ]

        # Añadimos el enlace al proyecto
        fields.insert(2, "enlace_proyecto")

        labels = {
            **NegociarProyectoForm.Meta.labels,
            "enlace_proyecto": "Enlace al proyecto",
        }


# ==========================================
# EDITAR PROYECTO EN PROCESO
# ==========================================

class EditarProyectoProcesoForm(PasarProyectoAProcesoForm):

    class Meta(PasarProyectoAProcesoForm.Meta):

        fields = [
            *PasarProyectoAProcesoForm.Meta.fields,
            "enlace_proyecto",
            "fecha_final_prevista",
            "fecha_fin",
        ]

        labels = {
            **PasarProyectoAProcesoForm.Meta.labels,
            "enlace_proyecto": "Enlace al proyecto",
            "fecha_final_prevista": "Fecha prevista de finalización",
            "fecha_fin": "Fecha de fin",
        }

        widgets = {
            **PasarProyectoAProcesoForm.Meta.widgets,
            "fecha_final_prevista": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "fecha_fin": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
        }


# ==========================================
# VOLVER AL ESTADO ANTERIOR DESDE PROCESO
# ==========================================

class VolverEstadoAnteriorProcesoForm(forms.Form):

    ESTADOS = [
        ("DEFINICION", "En Definición"),
        ("SOLICITADO", "Solicitado"),
        ("NEGOCIACION", "En Negociación"),
    ]

    estado = forms.ChoiceField(
        choices=ESTADOS,
        widget=forms.RadioSelect,
        initial="DEFINICION",
        label="Estado al que volver",
        required=True,
    )
    

# ==========================================
# COPIAR PROYECTO DENEGADO A DEFINICIÓN
# ==========================================

class CopiarProyectoDenegadoForm(forms.ModelForm):

    class Meta:
        model = Proyecto

        fields = [
            "acronimo",
            "nombre",
            "organismo",
            "tipo_proyecto",
            "porcentaje_subvencion",
            "importe_solicitado",
            "importe_solicitado_cesga",
            "tipo_participacion",
            "duracion",
            "comentario",
        ]

        labels = {
            "acronimo": "Acrónimo",
            "nombre": "Nombre",
            "organismo": "Organismo",
            "tipo_proyecto": "Tipo Proyecto",
            "porcentaje_subvencion": "Porcentaje",
            "importe_solicitado": "Cantidad Total",
            "importe_solicitado_cesga": "Cantidad CESGA",
            "tipo_participacion": "Participación",
            "duracion": "Duración",
            "comentario": "Comentario",
        }

        widgets = {
            "comentario": forms.Textarea(
                attrs={"rows": 3}
            ),
        }


# ==========================================
# AÑADIR SOCIO
# ==========================================

class CrearSocioForm(forms.Form):

    # DATOS DEL SOCIO

    nombre_empresa = forms.CharField(
        label="Socio",
        max_length=100,
        required=True
    )

    direccion = forms.CharField(
        label="Dirección",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )

    # DATOS DEL RESPONSABLE

    apellido = forms.CharField(
        label="Apellidos",
        max_length=100,
        required=True
    )

    nombre = forms.CharField(
        label="Nombre",
        max_length=100,
        required=True
    )

    telefono = forms.CharField(
        label="Teléfono 1",
        max_length=20,
        required=False
    )

    telefono2 = forms.CharField(
        label="Teléfono 2",
        max_length=20,
        required=False
    )

    fax = forms.CharField(
        label="Fax",
        max_length=20,
        required=False
    )

    email = forms.EmailField(
        label="Correo electrónico",
        required=True
    )

    # GUARDAR SOCIO Y RESPONSABLE

    @transaction.atomic
    def save(self):

        datos = self.cleaned_data

        socio = Socio.objects.create(
            nombre_empresa=datos["nombre_empresa"],
            direccion=datos["direccion"]
        )

        ContactoSocio.objects.create(
            socio=socio,
            apellido=datos["apellido"],
            nombre=datos["nombre"],
            telefono=datos["telefono"],
            telefono2=datos["telefono2"],
            fax=datos["fax"],
            email=datos["email"]
        )

        return socio
    

# ==========================================
# AÑADIR TIPO DE PROYECTO
# ==========================================

class CrearTipoProyectoForm(forms.ModelForm):

    class Meta:
        model = TipoProyecto

        fields = ["nombre"]

        labels = {
            "nombre": "Nombre del tipo de proyecto"
        }

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Introduce el tipo de proyecto",
                    "autocomplete": "off"
                }
            )
        }

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if TipoProyecto.objects.filter(
            nombre__iexact=nombre
        ).exists():

            raise forms.ValidationError(
                "Ya existe un tipo de proyecto con ese nombre."
            )

        return nombre


# ==========================================
# AÑADIR ORGANISMO
# ==========================================

class CrearOrganismoForm(forms.ModelForm):

    class Meta:
        model = Organismo

        fields = ["nombre"]

        labels = {
            "nombre": "Nombre del organismo"
        }

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Introduce el nombre del organismo",
                    "autocomplete": "off"
                }
            )
        }

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if Organismo.objects.filter(
            nombre__iexact=nombre
        ).exists():

            raise forms.ValidationError(
                "Ya existe un organismo con ese nombre."
            )

        return nombre
    
# ==========================================
# AÑADIR TIPO DE PARTICIPACIÓN
# ==========================================

class CrearTipoParticipacionForm(forms.ModelForm):

    class Meta:
        model = TipoParticipacion

        fields = ["nombre"]

        labels = {
            "nombre": "Nombre del tipo de participación"
        }

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Introduce el tipo de participación",
                    "autocomplete": "off"
                }
            )
        }

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if TipoParticipacion.objects.filter(
            nombre__iexact=nombre
        ).exists():

            raise forms.ValidationError(
                "Ya existe un tipo de participación con ese nombre."
            )

        return nombre


# ==========================================
# AÑADIR ÁREA
# ==========================================

class CrearAreaForm(forms.ModelForm):

    class Meta:
        model = Area

        fields = ["nombre"]

        labels = {
            "nombre": "Nombre del área"
        }

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Introduce el nombre del área",
                    "autocomplete": "off"
                }
            )
        }

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if Area.objects.filter(
            nombre__iexact=nombre
        ).exists():

            raise forms.ValidationError(
                "Ya existe un área con ese nombre."
            )

        return nombre
    

# ==========================================
# BUSCAR PROYECTOS
# ==========================================

class BuscarProyectosForm(forms.Form):

    # ACRÓNIMO
    usar_acronimo = forms.BooleanField(required=False)

    acronimo = forms.CharField(
        required=False,
        label="Acrónimo",
        widget=forms.TextInput(
            attrs={"placeholder": "Buscar por acrónimo"}
        )
    )

    # NOMBRE
    usar_nombre = forms.BooleanField(required=False)

    nombre = forms.CharField(
        required=False,
        label="Nombre",
        widget=forms.TextInput(
            attrs={"placeholder": "Nombre del proyecto"}
        )
    )

    # ESTADO
    usar_estado = forms.BooleanField(required=False)

    estado = forms.MultipleChoiceField(
        required=False,
        label="Estado",
        choices=Proyecto._meta.get_field("estado").choices,
        widget=forms.SelectMultiple(
            attrs={"size": 6}
        )
    )

    # ORGANISMO
    usar_organismo = forms.BooleanField(required=False)

    organismo = forms.ModelChoiceField(
        required=False,
        label="Organismo",
        queryset=Organismo.objects.all().order_by("nombre"),
        empty_label="Seleccionar organismo"
    )

    # TIPO DE PROYECTO
    usar_tipo_proyecto = forms.BooleanField(required=False)

    tipo_proyecto = forms.ModelChoiceField(
        required=False,
        label="Tipo de proyecto",
        queryset=TipoProyecto.objects.all().order_by("nombre"),
        empty_label="Seleccionar tipo"
    )

    # PARTICIPACIÓN
    usar_participacion = forms.BooleanField(required=False)

    participacion = forms.ModelChoiceField(
        required=False,
        label="Participación",
        queryset=TipoParticipacion.objects.all().order_by("nombre"),
        empty_label="Seleccionar participación"
    )

    # INVESTIGADOR
    usar_investigador = forms.BooleanField(required=False)

    investigador = forms.ModelChoiceField(
        required=False,
        label="Investigador",
        queryset=Investigador.objects.select_related(
            "usuario"
        ).order_by(
            "usuario__last_name",
            "usuario__first_name"
        ),
        empty_label="Seleccionar investigador"
    )

    # SOCIO
    usar_socio = forms.BooleanField(required=False)

    socio = forms.ModelChoiceField(
        required=False,
        label="Socio",
        queryset=Socio.objects.all().order_by("nombre_empresa"),
        empty_label="Seleccionar socio"
    )

    # ÁREAS
    usar_areas = forms.BooleanField(required=False)

    areas = forms.ModelChoiceField(
        required=False,
        label="Áreas",
        queryset=Area.objects.all().order_by("nombre"),
        empty_label="Seleccionar área"
    )

    # VALIDACIÓN DE LOS CRITERIOS ACTIVADOS
    def clean(self):
        datos = super().clean()

        criterios = [
            ("usar_acronimo", "acronimo"),
            ("usar_nombre", "nombre"),
            ("usar_estado", "estado"),
            ("usar_organismo", "organismo"),
            ("usar_tipo_proyecto", "tipo_proyecto"),
            ("usar_participacion", "participacion"),
            ("usar_investigador", "investigador"),
            ("usar_socio", "socio"),
            ("usar_areas", "areas"),
        ]

        for casilla, campo in criterios:

            if datos.get(casilla) and not datos.get(campo):
                self.add_error(
                    campo,
                    "Selecciona o introduce un valor para este criterio."
                )

        return datos


# ==========================================
# CREAR LÍNEA DE INVESTIGACIÓN
# ==========================================

class CrearLineaInvestigacionForm(forms.ModelForm):

    class Meta:
        model = LineaInvestigacion

        fields = [
            "nombre",
            "presupuesto",
        ]

        labels = {
            "nombre": "Nombre de la línea",
            "presupuesto": "Presupuesto (€)",
        }

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Nombre de la línea de investigación",
                    "autocomplete": "off",
                }
            ),

            "presupuesto": forms.NumberInput(
                attrs={
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0",
                }
            ),
        }

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if LineaInvestigacion.objects.filter(
            nombre__iexact=nombre
        ).exists():

            raise forms.ValidationError(
                "Ya existe una línea de investigación con ese nombre."
            )

        return nombre

    def clean_presupuesto(self):

        presupuesto = self.cleaned_data["presupuesto"]

        if presupuesto < 0:
            raise forms.ValidationError(
                "El presupuesto no puede ser negativo."
            )

        return presupuesto

# ==========================================
# ASIGNAR LÍNEA A UN PROYECTO
# ==========================================

class AsignacionLineaForm(forms.Form):

    linea_investigacion = forms.ModelChoiceField(
        queryset=LineaInvestigacion.objects.order_by("nombre"),
        label="Línea de investigación",
        empty_label="Selecciona una línea",
        widget=forms.Select()
    )

    porcentaje = forms.DecimalField(
        label="Porcentaje del presupuesto",
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("100.00"),
        widget=forms.NumberInput(
            attrs={
                "min": "0.01",
                "max": "100",
                "step": "0.01",
                "placeholder": "Ejemplo: 30"
            }
        )
    )


# ==========================================
# EDITAR PORCENTAJE DE UNA ASIGNACIÓN
# ==========================================

class EditarPorcentajeAsignacionForm(forms.Form):

    porcentaje = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("100.00"),
        widget=forms.NumberInput(
            attrs={
                "min": "0.01",
                "max": "100",
                "step": "0.01"
            }
        )
    )
    

# ==========================================
# ASIGNAR PRESUPUESTO A UN PROYECTO
# DESDE ADMINISTRACIÓN
# ==========================================

class AsignacionProyectoForm(forms.Form):

    proyecto = forms.ModelChoiceField(
        queryset=Proyecto.objects.order_by("acronimo"),
        label="Proyecto",
        empty_label="Selecciona un proyecto"
    )

    porcentaje = forms.DecimalField(
        label="Porcentaje a asignar",
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("100.00"),
        widget=forms.NumberInput(
            attrs={
                "min": "0.01",
                "max": "100",
                "step": "0.01",
                "placeholder": "Ejemplo: 30"
            }
        )
    )


# ==========================================
# FORMULARIO DE FESTIVOS
# ==========================================

class FestivoForm(forms.ModelForm):

    class Meta:
        model = Festivo

        fields = [
            "fecha",
            "nombre",
            "ambito",
            "fuente",
            "url_fuente",
        ]

        widgets = {
            "fecha": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "cal-input"
                },
                format="%Y-%m-%d"
            ),
            "nombre": forms.TextInput(
                attrs={"class": "cal-input"}
            ),
            "ambito": forms.Select(
                attrs={"class": "cal-input"}
            ),
            "fuente": forms.TextInput(
                attrs={"class": "cal-input"}
            ),
            "url_fuente": forms.URLInput(
                attrs={"class": "cal-input"}
            ),
        }









