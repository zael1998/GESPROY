from django.contrib import admin
from .models import Area, Organismo, TipoProyecto, TipoParticipacion, LineaInvestigacion, Proyecto, Asignacion, Dedicacion, MovimientoEconomico, Socio, ContactoSocio

admin.site.register(Organismo)
admin.site.register(TipoProyecto)
admin.site.register(TipoParticipacion)
admin.site.register(LineaInvestigacion)
admin.site.register(Proyecto)
admin.site.register(Asignacion)
admin.site.register(Dedicacion)
admin.site.register(MovimientoEconomico)
admin.site.register(Socio)
admin.site.register(ContactoSocio)
admin.site.register(Area)
