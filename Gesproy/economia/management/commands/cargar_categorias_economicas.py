
from django.core.management.base import BaseCommand

from economia.models import CategoriaEconomica


CATEGORIAS = [

    (
        "1.1",
        "Personal",
        "COSTE",
        [
            ("1.1.1", "Personal CESGA"),
            ("1.1.2", "Personal subcontratado"),
        ],
    ),

    (
        "1.2",
        "Equipamiento (hardware y software)",
        "COSTE",
        [
            ("1.2.1", "Uso de equipos CESGA"),
            ("1.2.2", "Equipamiento subcontratado o alquilado"),
            ("1.2.3", "Equipamiento comprado"),
            ("1.2.4", "Licencias y software"),
        ],
    ),

    (
        "1.3",
        "Viajes y estancias",
        "COSTE",
        [
            ("1.3.1", "Transporte"),
            ("1.3.2", "Dietas y ayudas de coste"),
            ("1.3.3", "Alojamiento"),
            ("1.3.4", "Otros viajes"),
        ],
    ),

    (
        "1.4",
        "Consumibles",
        "COSTE",
        [
            ("1.4.1", "Material de oficina"),
            ("1.4.2", "Suministros"),
            ("1.4.3", "Otros consumibles"),
        ],
    ),

    (
        "1.5",
        "Servicios externos y otros costes",
        "COSTE",
        [
            ("1.5.1", "Formación y cursos"),
            ("1.5.2", "Bibliografía y publicaciones"),
            ("1.5.3", "Consultoría y servicios técnicos"),
            ("1.5.4", "Representación"),
            ("1.5.5", "Otros costes"),
        ],
    ),

    (
        "2.1",
        "Ingresos y financiación prevista",
        "INGRESO",
        [
            ("2.1.1", "Financiación de organismos"),
            ("2.1.2", "Aportaciones de socios"),
            ("2.1.3", "Otros ingresos previstos"),
        ],
    ),

]


class Command(BaseCommand):

    help = (
        "Carga o actualiza las categorías económicas "
        "iniciales de Gesproy."
    )

    def handle(self, *args, **options):

        for orden, (codigo, nombre, tipo, hijas) in enumerate(
            CATEGORIAS,
            start=1,
        ):

            padre, _ = CategoriaEconomica.objects.update_or_create(
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "tipo": tipo,
                    "padre": None,
                    "orden": orden,
                },
            )

            for suborden, (cod_hija, nom_hija) in enumerate(
                hijas,
                start=1,
            ):

                CategoriaEconomica.objects.update_or_create(
                    codigo=cod_hija,
                    defaults={
                        "nombre": nom_hija,
                        "tipo": tipo,
                        "padre": padre,
                        "orden": suborden,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Categorías económicas cargadas."
            )
        )
