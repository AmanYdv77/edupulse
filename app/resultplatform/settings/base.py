"""
Base settings for EduPulse project.
Shared configuration inherited by environment-specific settings (dev, test, e2e, prod).
"""

from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
import environ

# Build paths inside the project: BASE_DIR is 'app/', REPO_DIR is repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = BASE_DIR.parent

env = environ.Env()
env_file = REPO_DIR / ".env"
if env_file.is_file():
    environ.Env.read_env(env_file)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # --- our apps ---
    'accounts',
    'academics',
    'predictions',
]

# Custom User model with institutional role hierarchy
AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.NoCacheAuthenticatedMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'resultplatform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'resultplatform.wsgi.application'


# Database Configuration
# Uses PostgreSQL via django-environ (DATABASE_URL)
DATABASES = {
    'default': env.db("DATABASE_URL"),
}
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['CONN_HEALTH_CHECKS'] = True


def require_db_name(allowed_suffix: str | None = None, disallowed_suffixes: tuple[str, ...] = ()):
    """Guard ensuring the configured database matches the environment naming convention."""
    db_name = DATABASES["default"].get("NAME", "")
    if allowed_suffix and not db_name.endswith(allowed_suffix):
        raise ImproperlyConfigured(
            f"Database name '{db_name}' must end with '{allowed_suffix}' for this environment."
        )
    for suffix in disallowed_suffixes:
        if db_name.endswith(suffix):
            raise ImproperlyConfigured(
                f"Database name '{db_name}' must not end with '{suffix}' for this environment."
            )


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = 'static/'

# Authentication redirects
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"
LOGIN_URL = "login"

# Machine Learning model artifact storage directory
MODEL_ARTIFACT_DIR = env("MODEL_ARTIFACT_DIR", default=None)
