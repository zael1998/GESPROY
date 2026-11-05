
"""
Django settings for config project.

Proyecto Gesproy
Gestión de proyectos de investigación.
"""

import os
from pathlib import Path


# ==========================================
# RUTAS DEL PROYECTO
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ==========================================
# SEGURIDAD
# ==========================================

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-gesproy-solo-desarrollo-local-cambiar-en-produccion"
)

DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "10.38.29.177",
]


# ==========================================
# APLICACIONES INSTALADAS
# ==========================================

INSTALLED_APPS = [

    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Gesproy
    "usuarios",
    "proyectos",
    "horas",
    "api_movil",
    "economia",
    "publicaciones"
]


# ==========================================
# MIDDLEWARE
# ==========================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Toda vista privada requiere iniciar sesión.
    # La vista de login debe usar @login_not_required.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
]


# ==========================================
# URLS
# ==========================================

ROOT_URLCONF = "config.urls"


# ==========================================
# PLANTILLAS HTML
# ==========================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates"
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ==========================================
# WSGI
# ==========================================

WSGI_APPLICATION = "config.wsgi.application"


# ==========================================
# BASE DE DATOS
# ==========================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ==========================================
# VALIDACIÓN DE CONTRASEÑAS
# ==========================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
        "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# ==========================================
# IDIOMA Y ZONA HORARIA
# ==========================================

LANGUAGE_CODE = "es-es"

TIME_ZONE = "Europe/Madrid"

USE_I18N = True

USE_TZ = True


# ==========================================
# ARCHIVOS ESTÁTICOS
# ==========================================

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]


# ==========================================
# CORREO ELECTRÓNICO
# ==========================================

EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
)


# ==========================================
# MODELO PERSONALIZADO DE USUARIOS
# ==========================================

AUTH_USER_MODEL = "usuarios.Usuario"


# ==========================================
# AUTENTICACIÓN
# ==========================================

LOGIN_URL = "login"

LOGIN_REDIRECT_URL = "mis_proyectos"

LOGOUT_REDIRECT_URL = "login"


# ==========================================
# CSRF - DESARROLLO WEB Y API MÓVIL
# ==========================================

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://10.38.29.177:8000",
]

# Sesiones Django:
# La cookie se mantiene entre peticiones al mismo host.
SESSION_COOKIE_HTTPONLY = True

# La cookie CSRF puede ser leída por el cliente React
# si utilizamos el sistema actual de CSRF.
CSRF_COOKIE_HTTPONLY = False

# Para desarrollo local con HTTP.
# En producción HTTPS estos valores deben cambiar.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Evitar compartir cookies entre dominios diferentes.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"


# ==========================================
# GITHUB CODESPACES
# ==========================================

if os.environ.get("CODESPACE_NAME"):
    codespace_name = os.environ["CODESPACE_NAME"]

    CSRF_TRUSTED_ORIGINS.extend([
        f"https://{codespace_name}-5173.app.github.dev",
        f"https://{codespace_name}-8000.app.github.dev",
    ])

    ALLOWED_HOSTS.extend([
        f"{codespace_name}-5173.app.github.dev",
        f"{codespace_name}-8000.app.github.dev",
    ])
