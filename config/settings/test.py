from .base import *

DEBUG = False
ALLOWED_HOSTS = ["*"]

# fast hashing so tests don't spend seconds on bcrypt/PBKDF2
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# in-memory cache: throttle counters stay out of Redis and reset per test run
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# dummy credentials, so a test can never reach real services by accident
AWS_ACCESS_KEY_ID = "test"
AWS_SECRET_ACCESS_KEY = "test"
AWS_S3_BUCKET_NAME = "test-bucket"
GEMINI_API_KEY = "test"