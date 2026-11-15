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
    "django-insecure-gesproy-solo-desarrollo-local-cambiar-en-produccion",
)

DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "10.38.29.177",
    "10.0.2.2",
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
    # Django REST Framework
    "rest_framework",
    # Gesproy
    "usuarios",
    "proyectos",
    "horas",
    "api_movil",
    "economia",
    "publicaciones",
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
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
]


# ==========================================
# DJANGO REST FRAMEWORK
# ==========================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}


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
        "DIRS": [BASE_DIR / "templates"],
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
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
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
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
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
# CSRF - WEB, REACT Y ANDROID
# ==========================================

CSRF_TRUSTED_ORIGINS = [
    # Django local
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    # React local
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    # Servidor CESGA
    "http://10.38.29.177:8000",
    # Emulador Android
    "http://10.0.2.2:5173",
]


# ==========================================
# CONFIGURACIÓN DE COOKIES
# ==========================================

SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_HTTPONLY = False

# Configuración para desarrollo local.
# En producción se debe utilizar HTTPS.

SESSION_COOKIE_SECURE = False

CSRF_COOKIE_SECURE = False

SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SAMESITE = "Lax"


# ==========================================
# GITHUB CODESPACES
# ==========================================

if os.environ.get("CODESPACE_NAME"):
    codespace_name = os.environ["CODESPACE_NAME"]

    CSRF_TRUSTED_ORIGINS.extend(
        [
            f"https://{codespace_name}-5173.app.github.dev",
            f"https://{codespace_name}-8000.app.github.dev",
        ]
    )

    ALLOWED_HOSTS.extend(
        [
            f"{codespace_name}-5173.app.github.dev",
            f"{codespace_name}-8000.app.github.dev",
        ]
    )

    # ==========================================
# CONTROL DE HORAS MENSUALES
# ==========================================

GESPROY_HORAS_JORNADA = "8.00"

GESPROY_CONTROL_MENSUAL_ACTIVO = False
