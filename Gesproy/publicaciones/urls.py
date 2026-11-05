from django.urls import path
from . import views

app_name = "publicaciones"
urlpatterns = [
    path("", views.lista_publicaciones, name="lista"),
    path("nueva/", views.crear_publicacion, name="crear"),
    path("<int:pk>/editar/", views.editar_publicacion, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_publicacion, name="eliminar"),
    path("<int:pk>/descargar/", views.descargar_publicacion, name="descargar"),
]