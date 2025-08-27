"""
Django settings for BLACK CORAL project.

BLACK CORAL is an internal MVP web application designed to streamline 
and accelerate the U.S. government contracting workflow.
"""

from pathlib import Path
import environ
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables
env = environ.Env(
    DEBUG=(bool, False)
)
# Only try to read .env file if it exists (for local development)
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-w(k^u0nm24xrti#99%mc82yr3xot95=!v8&zkn=f)!mjnu7z62')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', 'testserver'])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Third-party apps
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "drf_spectacular",
    "django_htmx",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    "django_redis",
    "csp",
    
    # BLACK CORAL apps
    "apps.core",
    "apps.authentication",
    "apps.opportunities",
    "apps.documents",
    "apps.ai_integration",
    "apps.compliance",
    "apps.collaboration",
    "apps.notifications",
    "apps.agents",
    "apps.external_apis",
    "apps.workflows",
    "apps.salary_analysis",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "blackcoral.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "blackcoral.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# Database Configuration
# Use PostgreSQL if DB_HOST is set (Docker/Production), otherwise SQLite (Local)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="blackcoral"),
        "USER": env("DB_USER", default="blackcoral_user"),
        "PASSWORD": env("DB_PASSWORD", default="blackcoral_dev_pass_123"),
        "HOST": env("DB_HOST", default="postgres"),
        "PORT": env("DB_PORT", default="5432"),
        "OPTIONS": {
            "charset": "utf8",
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# BLACK CORAL Specific Settings

# External API Configuration
SAM_GOV_API_KEY = env("SAM_GOV_API_KEY", default="")
# Additional SAM.gov API keys for rotation
SAM_GOV_API_KEY_1 = env("SAM_GOV_API_KEY_1", default="")
SAM_GOV_API_KEY_2 = env("SAM_GOV_API_KEY_2", default="")
SAM_GOV_API_KEY_3 = env("SAM_GOV_API_KEY_3", default="")
SAM_GOV_API_KEY_4 = env("SAM_GOV_API_KEY_4", default="")
SAM_GOV_API_KEY_5 = env("SAM_GOV_API_KEY_5", default="")
SAM_GOV_API_KEY_6 = env("SAM_GOV_API_KEY_6", default="")
SAM_GOV_API_KEY_7 = env("SAM_GOV_API_KEY_7", default="")
SAM_GOV_API_KEY_8 = env("SAM_GOV_API_KEY_8", default="")
SAM_GOV_API_KEY_9 = env("SAM_GOV_API_KEY_9", default="")
SAM_GOV_API_KEY_10 = env("SAM_GOV_API_KEY_10", default="")

# SAM.gov API Configuration
SAM_GOV_ACCOUNT_TYPE = env("SAM_GOV_ACCOUNT_TYPE", default="non_federal")  # non_federal, entity_associated, federal_system
SAM_GOV_USE_ALPHA = env.bool("SAM_GOV_USE_ALPHA", default=False)  # Use testing endpoints
SAM_GOV_TIMEOUT = env.int("SAM_GOV_TIMEOUT", default=60)  # Request timeout in seconds
SAM_GOV_MAX_RETRIES = env.int("SAM_GOV_MAX_RETRIES", default=3)  # Max retry attempts
SAM_GOV_BACKOFF_FACTOR = env.float("SAM_GOV_BACKOFF_FACTOR", default=2.0)  # Exponential backoff factor
SAM_GOV_CACHE_DEFAULT_TTL = env.int("SAM_GOV_CACHE_DEFAULT_TTL", default=3600)  # Default cache TTL in seconds

# Description Enhancement Settings
SAM_GOV_ENABLE_DESCRIPTION_ENHANCEMENT = env.bool("SAM_GOV_ENABLE_DESCRIPTION_ENHANCEMENT", default=True)
SAM_GOV_USE_V3_API = env.bool("SAM_GOV_USE_V3_API", default=True)  # Use v3 API for enhanced features
SAM_GOV_DESCRIPTION_FETCH_TIMEOUT = env.int("SAM_GOV_DESCRIPTION_FETCH_TIMEOUT", default=10)  # Timeout for description URL requests
SAM_GOV_DESCRIPTION_CACHE_TTL = env.int("SAM_GOV_DESCRIPTION_CACHE_TTL", default=3600)  # Cache TTL for description content
SAM_GOV_MAX_DESCRIPTION_LENGTH = env.int("SAM_GOV_MAX_DESCRIPTION_LENGTH", default=10000)  # Max description length
SAM_GOV_DESCRIPTION_MIN_ENHANCEMENT_LENGTH = env.int("SAM_GOV_DESCRIPTION_MIN_ENHANCEMENT_LENGTH", default=50)  # Min chars to consider enhancement worthwhile

# Rate Limiting Configuration
SAM_GOV_RATE_LIMIT_BUFFER = env.float("SAM_GOV_RATE_LIMIT_BUFFER", default=0.1)  # 10% buffer on rate limits
SAM_GOV_BURST_LIMIT_OVERRIDE = env.int("SAM_GOV_BURST_LIMIT_OVERRIDE", default=None)  # Override burst limit

# Data Quality and Monitoring
SAM_GOV_ENABLE_MONITORING = env.bool("SAM_GOV_ENABLE_MONITORING", default=True)
SAM_GOV_ALERT_ON_FAILURES = env.bool("SAM_GOV_ALERT_ON_FAILURES", default=True)
SAM_GOV_HEALTH_CHECK_INTERVAL = env.int("SAM_GOV_HEALTH_CHECK_INTERVAL", default=300)  # 5 minutes

# Other External APIs
USASPENDING_API_KEY = env("USASPENDING_API_KEY", default="")
GAO_API_KEY = env("GAO_API_KEY", default="")

# AI Integration
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
GOOGLE_API_KEY = env("GOOGLE_API_KEY", default="")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")

# LangExtract Configuration
LANGEXTRACT_ENABLED = env.bool("LANGEXTRACT_ENABLED", default=True)
LANGEXTRACT_MODEL = env("LANGEXTRACT_MODEL", default="gemini-1.5-flash")  # Primary model for extractions
LANGEXTRACT_CACHE_DIR = env("LANGEXTRACT_CACHE_DIR", default=".langextract_cache")
LANGEXTRACT_MAX_TEXT_LENGTH = env.int("LANGEXTRACT_MAX_TEXT_LENGTH", default=100000)  # 100k chars max
LANGEXTRACT_CACHE_TTL = env.int("LANGEXTRACT_CACHE_TTL", default=3600)  # 1 hour cache
LANGEXTRACT_BATCH_SIZE = env.int("LANGEXTRACT_BATCH_SIZE", default=5)  # Documents per batch
LANGEXTRACT_RETRY_ATTEMPTS = env.int("LANGEXTRACT_RETRY_ATTEMPTS", default=3)
LANGEXTRACT_TIMEOUT_SECONDS = env.int("LANGEXTRACT_TIMEOUT_SECONDS", default=60)

# Celery Configuration
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Cache Configuration (using Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env("REDIS_URL", default="redis://localhost:6379/1"),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Security Settings
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["https://localhost:8000"])
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG

# Email Configuration
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="BLACK CORAL <noreply@blackcoral.ai>")
EMAIL_SUBJECT_PREFIX = env("EMAIL_SUBJECT_PREFIX", default="[BLACK CORAL] ")
EMAIL_SHARING_RATE_LIMIT = env.int("EMAIL_SHARING_RATE_LIMIT", default=10)

# CORS Settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only allow all origins in debug mode

# Additional CORS settings to handle preflight requests
CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-forwarded-for',
    'x-forwarded-proto',
    'x-forwarded-host',
    'cookie',
]

CORS_EXPOSE_HEADERS = [
    'content-type',
    'content-length',
    'access-control-allow-origin',
    'set-cookie',
    'x-csrftoken',
]

# Additional CORS settings for ServiceWorker compatibility
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours
CORS_ALLOW_PRIVATE_NETWORK = True  # For development

# Content Security Policy Configuration
CSP_DEFAULT_SRC = ["'self'"]
CSP_CONNECT_SRC = [
    "'self'",
    "ws:",
    "wss:",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "https://api.sam.gov",
    "https://*.sam.gov",
    "https://www.usaspending.gov",
    "https://api.usaspending.gov"
]
CSP_SCRIPT_SRC = [
    "'self'",
    "'unsafe-inline'",
    "'unsafe-eval'",
    "http://localhost:3000",
    "http://localhost:8000",
]
CSP_STYLE_SRC = [
    "'self'",
    "'unsafe-inline'",
    "https://fonts.googleapis.com",
    "https://cdn.tailwindcss.com",
]
CSP_FONT_SRC = [
    "'self'",
    "https://fonts.gstatic.com",
]
CSP_IMG_SRC = [
    "'self'",
    "data:",
    "https:",
]
CSP_FRAME_SRC = [
    "'self'",
]

# Role-based Authentication
AUTH_USER_MODEL = "authentication.User"

# Login/Logout URLs
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# AI Integration Settings
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

AI_DEFAULT_PROVIDER = os.getenv('AI_DEFAULT_PROVIDER', 'claude')
AI_FALLBACK_ENABLED = os.getenv('AI_FALLBACK_ENABLED', 'True').lower() == 'true'
SITE_URL = os.getenv('SITE_URL', 'https://blackcoral.ai')
SITE_NAME = os.getenv('SITE_NAME', 'BLACK CORAL')

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "blackcoral.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "blackcoral": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Agent OS Configuration
AGENT_OS_API_KEY = env('AGENT_OS_API_KEY', default='')
AGENT_OS_PROJECT_ID = env('AGENT_OS_PROJECT_ID', default='black-coral')
AGENT_OS_ENVIRONMENT = env('AGENT_OS_ENVIRONMENT', default='development')
AGENT_OS_BASE_URL = env('AGENT_OS_BASE_URL', default='https://api.agent-os.com/v1')
AGENT_OS_MOCK_MODE = env.bool('AGENT_OS_MOCK_MODE', default=False)

# Agent OS Features
AGENT_OS_FEATURES = {
    'auto_code_review': True,
    'auto_test_generation': True,
    'security_scanning': True,
    'performance_monitoring': True,
    'ai_optimization': True,
    'workflow_automation': True,
}

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'ai_analysis': '50/hour',
        'bulk_operations': '10/hour',
    }
}

# API Documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'BLACK CORAL API',
    'DESCRIPTION': 'AI-Powered Government Contracting Platform API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
}

# Agent OS Workflow Configuration
AGENT_OS_WORKFLOWS = {
    'opportunity-intake': {
        'enabled': True,
        'auto_trigger': True,
        'notification_channels': ['email', 'in_app'],
    },
    'compliance-check': {
        'enabled': True,
        'auto_trigger': True,
        'severity_threshold': 'medium',
    },
    'proposal-creation': {
        'enabled': True,
        'requires_approval': True,
        'template_selection': 'auto',
    },
    'ai-development': {
        'enabled': True,
        'cost_threshold': 100,  # Maximum cost in dollars
        'quality_threshold': 0.85,
    },
}
