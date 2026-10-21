from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from proyectos.models import Dedicacion, Proyecto
from usuarios.models import Investigador, Usuario
from horas.models import CierreMensualHoras, HistorialValidacionHoras, RegistroHoras, Tarea


class ValidacionHorasTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_prueba", password="prueba", rol="ADMIN", is_staff=True
        )
        self.validador_usuario = Usuario.objects.create_user(
            username="validador_prueba", password="prueba", rol="INVESTIGADOR"
        )
        self.trabajador_usuario = Usuario.objects.create_user(
            username="trabajador_prueba", password="prueba", rol="INVESTIGADOR"
        )
        self.ajeno_usuario = Usuario.objects.create_user(
            username="ajeno_prueba", password="prueba", rol="INVESTIGADOR"
        )
        self.validador = Investigador.objects.create(
            usuario=self.validador_usuario, puede_validar_horas=True
        )
        self.trabajador = Investigador.objects.create(usuario=self.trabajador_usuario)
        self.ajeno = Investigador.objects.create(usuario=self.ajeno_usuario)
        self.proyecto = Proyecto.objects.create(
            nombre="Prueba de validación", acronimo="VALIDA", estado="PROCESO",
            fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31),
        )
        self.tarea = Tarea.objects.create(
            nombre="Reunión", proyecto=self.proyecto,
            fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31),
            horas_estimadas=Decimal("50.00"),
        )
        self.dedicacion = Dedicacion.objects.create(
            proyecto=self.proyecto,
            investigador=self.trabajador,
            porcentaje=Decimal("100.00"),
            fecha_inicio=date(2026, 1, 1),
            validador=self.validador,
        )
        self.registro = RegistroHoras.objects.create(
            investigador=self.trabajador,
            tarea=self.tarea,
            fecha=date(2026, 10, 13),
            horas=Decimal("2.00"),
            descripcion="Prueba",
        )

    def test_validador_puede_validar_solo_sus_asignados(self):
        self.client.force_login(self.validador_usuario)
        respuesta = self.client.post(reverse("horas:accion_validar"), {
            "accion": "individual", "registro_id": self.registro.pk
        })
        self.assertEqual(respuesta.status_code, 302)
        self.registro.refresh_from_db()
        self.assertTrue(self.registro.validado)
        self.assertEqual(self.registro.validado_por, self.validador_usuario)
        self.assertTrue(HistorialValidacionHoras.objects.filter(
            registro=self.registro, accion="VALIDAR"
        ).exists())

    def test_no_puede_validar_sin_asignacion(self):
        self.client.force_login(self.ajeno_usuario)
        respuesta = self.client.post(reverse("horas:accion_validar"), {
            "accion": "individual", "registro_id": self.registro.pk
        })
        self.assertEqual(respuesta.status_code, 403)
        self.registro.refresh_from_db()
        self.assertFalse(self.registro.validado)

    def test_mes_cerrado_no_admite_nuevos_registros(self):
        self.client.force_login(self.validador_usuario)
        respuesta = self.client.post(reverse("horas:accion_validar"), {
            "accion": "mes", "investigador_id": self.trabajador.pk,
            "anio": "2026", "mes": "10",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(CierreMensualHoras.objects.filter(
            proyecto=self.proyecto, investigador=self.trabajador,
            anio=2026, mes=10
        ).exists())
        with self.assertRaises(ValidationError):
            RegistroHoras.objects.create(
                investigador=self.trabajador,
                tarea=self.tarea,
                fecha=date(2026, 10, 14),
                horas=Decimal("3.00"),
            )

    def test_admin_reabre_con_motivo(self):
        self.client.force_login(self.validador_usuario)
        self.client.post(reverse("horas:accion_validar"), {
            "accion": "mes", "investigador_id": self.trabajador.pk,
            "anio": "2026", "mes": "10",
        })
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("horas:accion_validar"), {
            "accion": "reabrir", "registro_id": self.registro.pk,
            "motivo": "Corrección de fecha",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.registro.refresh_from_db()
        self.assertFalse(self.registro.validado)
        self.assertFalse(CierreMensualHoras.objects.filter(
            proyecto=self.proyecto, investigador=self.trabajador,
            anio=2026, mes=10
        ).exists())
        self.assertTrue(HistorialValidacionHoras.objects.filter(
            registro=self.registro, accion="REABRIR"
        ).exists())

    def test_modelo_impide_editar_registro_validado(self):
        self.client.force_login(self.validador_usuario)
        self.client.post(reverse("horas:accion_validar"), {
            "accion": "individual", "registro_id": self.registro.pk
        })
        self.registro.refresh_from_db()
        self.registro.horas = Decimal("7.00")
        with self.assertRaises(ValidationError):
            self.registro.save()

    def test_admin_no_puede_validar_por_url_ni_por_post(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("horas:validar_horas"))
        self.assertEqual(respuesta.status_code, 403)
        respuesta = self.client.post(reverse("horas:accion_validar"), {
            "accion": "individual", "registro_id": self.registro.pk
        })
        self.assertEqual(respuesta.status_code, 403)
        self.registro.refresh_from_db()
        self.assertFalse(self.registro.validado)

    def test_validador_sin_asignar_no_puede_validar(self):
        sin_asignar = Usuario.objects.create_user(
            username="validador_sin_asignar", password="prueba", rol="INVESTIGADOR"
        )
        Investigador.objects.create(usuario=sin_asignar, puede_validar_horas=True)
        self.client.force_login(sin_asignar)
        respuesta = self.client.post(reverse("horas:accion_validar"), {
            "accion": "individual", "registro_id": self.registro.pk
        })
        self.assertEqual(respuesta.status_code, 404)
        self.registro.refresh_from_db()
        self.assertFalse(self.registro.validado)