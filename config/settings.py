import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

load_dotenv() # Load biến môi trường từ file .env (khi chạy local)

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key')

# Khi deploy lên Railway, DEBUG phải là False
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*'] # Railway sẽ tự xử lý, để * cho tiện lúc đầu

CSRF_TRUSTED_ORIGINS = [
    'https://' + os.environ.get('RAILWAY_PUBLIC_DOMAIN', ''),
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Apps bên thứ 3
    'crispy_forms',
    'crispy_bootstrap5',
    # App của bạn
    'warehouse', 
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # <--- QUAN TRỌNG CHO FILE TĨNH
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Tạo thư mục templates ở root
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database chuẩn Railway
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600
    )
}

# Password validation (Giữ nguyên mặc định)

LANGUAGE_CODE = 'vi' # Chuyển sang tiếng Việt
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (Ảnh upload)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



LOGIN_REDIRECT_URL = '/'  # Đăng nhập xong về trang chủ
LOGOUT_REDIRECT_URL = '/accounts/login/' # Đăng xuất xong về trang login
