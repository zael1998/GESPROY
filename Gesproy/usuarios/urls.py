from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView

urlpatterns = [
    path("investigadores/", views.gestion_investigadores, name="gestion_investigadores"),
    path("investigadores/anadir/", views.anadir_investigador, name="anadir_investigador"),
    path("investigadores/<int:id>/estado/", views.cambiar_estado_investigador, name="cambiar_estado_investigador"),
    path("login/", LoginView.as_view(template_name="usuarios/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/",LogoutView.as_view(next_page="login"),name="logout"),
]