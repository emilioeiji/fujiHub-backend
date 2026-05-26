from .base import *  # noqa: F403
from .base import DATABASES, env_bool
from django.core.exceptions import ImproperlyConfigured

DEBUG = env_bool("DJANGO_DEBUG", True)

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", True)


def _looks_like_production_database(database_config):
    host = str(database_config.get("HOST") or "").lower()
    name = str(database_config.get("NAME") or "").lower()
    suspicious_hosts = ("emilioeiji", "digitalocean", "prod", "production")
    suspicious_names = {"fujihub", "fujihub_prod", "production", "prod"}
    return any(token in host for token in suspicious_hosts) or name in suspicious_names


if DEBUG and not env_bool("ALLOW_DEV_TO_USE_PROD_DB", False):
    default_database = DATABASES.get("default", {})
    if _looks_like_production_database(default_database):
        raise ImproperlyConfigured(
            "Blocked dev settings from using a production-looking database. "
            "Set ALLOW_DEV_TO_USE_PROD_DB=true only for an intentional one-off operation."
        )
