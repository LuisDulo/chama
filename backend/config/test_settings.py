"""Test settings: a real PostgreSQL.

CI sets TEST_DATABASE_URL. Locally an embedded server starts.
"""

import logging
import os
import tempfile

os.environ.setdefault("DJANGO_DEBUG", "1")

from config.settings import *  # noqa: E402,F403
from config.settings import database_from_url  # noqa: E402

url = os.environ.get("TEST_DATABASE_URL")
if not url:
    import pgserver

    # It logs while shutting down, after pytest has closed its output streams.
    logging.getLogger("pgserver").setLevel(logging.WARNING)
    _server = pgserver.get_server(tempfile.mkdtemp(prefix="chama-test-"), cleanup_mode="stop")
    url = _server.get_uri()

DATABASES = {"default": database_from_url(url)}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast, tests only
SECURE_SSL_REDIRECT = False
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"login": "1000/min", "password_reset": "1000/min"},
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
