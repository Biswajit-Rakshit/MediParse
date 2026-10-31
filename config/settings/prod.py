from .base import *

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")