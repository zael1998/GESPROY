
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

ALLOWED_HOSTS = []


# ==========================================
# APLICACIONES INSTALADAS
# ==========================================

INSTALLED_APPS = [

    # APLICACIONES DE DJANGO
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # APLICACIONES DE GESPROY
    "usuarios",
    "proyectos",
    "horas",

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

    # PROTEGER AUTOMÁTICAMENTE LAS VISTAS
    "django.contrib.auth.middleware.LoginRequiredMiddleware",

]


# ==========================================
# CONFIGURACIÓN DE URLS
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

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}


# ==========================================
# MODELO PERSONALIZADO DE USUARIOS
# ==========================================

AUTH_USER_MODEL = "usuarios.Usuario"


# ==========================================
# AUTENTICACIÓN GESPROY
# ==========================================

# DIRECCIÓN DE INICIO DE SESIÓN
LOGIN_URL = "login"

# DESPUÉS DE INICIAR SESIÓN
LOGIN_REDIRECT_URL = "mis_proyectos"

# DESPUÉS DE CERRAR SESIÓN
LOGOUT_REDIRECT_URL = "login"
