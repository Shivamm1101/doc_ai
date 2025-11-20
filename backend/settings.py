"""
Django settings for backend project.
Production-ready for Render deployment.
"""

import environ
import os
import sys
from pathlib import Path

# ======================================================
# BASE DIR
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ======================================================
# ENV VARIABLES
# ======================================================
env = environ.Env(
    DEBUG=(bool, False)
)

# Load `.env` only for local development (Render uses env vars)
env_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_file):
    env.read_env(env_file)

# ======================================================
# SECURITY
# ======================================================
SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-local-secret")

DEBUG = env("DEBUG", default=False)

ALLOWED_HOSTS = ["*"]

# ======================================================
# INSTALLED APPS
# ======================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Your apps
    "django_app",
    "django_app.ingestion",

    # API framework
    "rest_framework",
]

# ======================================================
# MIDDLEWARE
# ======================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ======================================================
# URLS + WSGI
# ======================================================
ROOT_URLCONF = "backend.urls"
WSGI_APPLICATION = "backend.wsgi.application"

# ======================================================
# DATABASE CONFIG
# Render: PostgreSQL
# Tests: SQLite in-memory
# ======================================================

if "pytest" in sys.modules:
    # -------------------------------
    # SQLite DB for pytest
    # -------------------------------
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    # -------------------------------
    # PostgreSQL for Render / Prod
    # -------------------------------
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST"),
            "PORT": env("POSTGRES_PORT"),
            "OPTIONS": {
                "options": "-c search_path=pdf-dataset-db" 
            },
        }
    }

# ======================================================
# PASSWORD VALIDATION
# ======================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ======================================================
# LANGUAGE / TIMEZONE
# ======================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ======================================================
# STATIC FILES (Render + Docker)
# ======================================================
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# ======================================================
# DEFAULT PK
# ======================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ======================================================
# CHROMA PATH (Render will mount /chroma disk)
# ======================================================
CHROMA_DISK_PATH = env("CHROMA_DISK_PATH", default="/chroma")
