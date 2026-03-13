import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ON_AWS = os.environ.get("ON_AWS", "").lower() in ("1", "true", "yes")

SECRET_KEY = os.environ.get(
    "SECRET_KEY", "django-insecure-local-dev-key-change-this-in-production"
)

DEBUG = not ON_AWS

ALLOWED_HOSTS = (
    ["localhost", "127.0.0.1"]
    if not ON_AWS
    else os.environ.get("ALLOWED_HOSTS", "").split(",")
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
] + (["storages"] if ON_AWS else [])

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "stellarator_db.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "stellarator_db.wsgi.application"

# --- Database ---
if ON_AWS:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "stellarator_db"),
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASS", ""),
            "HOST": os.environ.get("DB_HOST", ""),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Media / File Storage ---
if ON_AWS:
    AWS_STORAGE_BUCKET_NAME = os.environ.get("S3_BUCKET", "")
    AWS_S3_REGION_NAME = os.environ.get("S3_REGION", "")
    AWS_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_KEY", "")
    AWS_S3_FILE_OVERWRITE = False
    CSRF_TRUSTED_ORIGINS = [
        o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
    ]
    _https = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() in ("1", "true", "yes")
    SECURE_SSL_REDIRECT = _https
    SESSION_COOKIE_SECURE = _https
    CSRF_COOKIE_SECURE = _https
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"
else:
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "test-storage"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
