import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Stub any missing grpc proto modules if running outside full Docker LND build
for mod in [
    "api.lightning.invoices_pb2", "api.lightning.invoices_pb2_grpc",
    "api.lightning.lightning_pb2", "api.lightning.lightning_pb2_grpc",
    "api.lightning.router_pb2", "api.lightning.router_pb2_grpc",
    "api.lightning.signer_pb2", "api.lightning.signer_pb2_grpc",
    "api.lightning.verrpc_pb2", "api.lightning.verrpc_pb2_grpc",
    "api.lightning.node_pb2", "api.lightning.node_pb2_grpc",
    "api.lightning.hold_pb2", "api.lightning.hold_pb2_grpc",
    "api.lightning.primitives_pb2", "api.lightning.primitives_pb2_grpc",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Ensure base .env defaults are present
os.environ.setdefault("FEE", "0.002")
os.environ.setdefault("MAX_TRADE", "5000000")
os.environ.setdefault("MIN_TRADE", "10000")
os.environ.setdefault("LND_CERT_BASE64", "ZHVtbXk=")
os.environ.setdefault("LND_MACAROON_BASE64", "ZHVtbXk=")
os.environ.setdefault("LND_GRPC_HOST", "127.0.0.1:10009")
os.environ.setdefault("SECRET_KEY", "insecure-dev-secret-key-robosats-lite-admin")
os.environ.setdefault("DEVELOPMENT", "True")
os.environ.setdefault("HOST_NAME", "localhost")
os.environ.setdefault("HOST_NAME2", "127.0.0.1")
os.environ.setdefault("I2P_ALIAS", "localhost")
os.environ.setdefault("I2P_LONG", "localhost")
os.environ.setdefault("LOCAL_ALIAS", "localhost")
os.environ.setdefault("POSTGRES_DB", "robosats")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LANGUAGE_CODE", "ru")

# Import standard settings
from robosats.settings import *  # noqa: F401, F403

# Override for local lightweight SQLite development
DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
]
