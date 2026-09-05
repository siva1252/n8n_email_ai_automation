"""
Django settings for backend project.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
load_dotenv(REPO_ROOT / ".env", override=True)
load_dotenv(override=True)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-only")
DEBUG = _bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,*").split(",") if h.strip()]
for extra in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"):
    if extra not in ALLOWED_HOSTS and "*" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(extra)
if "host.docker.internal" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("host.docker.internal")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "deals",
    "rest_framework",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "backend.wsgi.application"

database_url = os.environ.get("DATABASE_URL", "sqlite:///db.sqlite3")
if database_url.startswith("sqlite:///"):
    db_name = database_url.replace("sqlite:///", "", 1)
    db_path = Path(db_name)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(db_path)}}
elif database_url.startswith("postgres"):
    # postgresql://user:pass@host:5432/dbname
    from urllib.parse import urlparse, unquote

    parsed = urlparse(database_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(BASE_DIR / "db.sqlite3")}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"

FLASK_AI_URL = os.environ.get("FLASK_AI_URL", "http://127.0.0.1:5000").rstrip("/")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "http://127.0.0.1:5678/webhook/deal-action")
N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "http://127.0.0.1:5678")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
NEGOTIATION_MIN_PRICE = float(os.environ.get("NEGOTIATION_MIN_PRICE", "4000"))
NEGOTIATION_TARGET_PRICE = float(os.environ.get("NEGOTIATION_TARGET_PRICE", "5000"))
NEGOTIATION_MAX_ROUNDS = int(os.environ.get("NEGOTIATION_MAX_ROUNDS", "3"))
DEMO_MODE = _bool("DEMO_MODE", True)
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]
