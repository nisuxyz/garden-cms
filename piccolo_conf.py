# piccolo_conf.py
"""
Piccolo ORM configuration.

Set the PICCOLO_CONF env-var to this module's dotted path if it
isn't discovered automatically (default: ``piccolo_conf``).
"""
import os

from dotenv import load_dotenv
from piccolo.conf.apps import AppRegistry
from piccolo.engine.postgres import PostgresEngine

load_dotenv()

# ── Database engine ────────────────────────────────────────
# Expects a standard PostgreSQL DSN in DATABASE_URL, e.g.
#   postgres://user:pass@localhost:5432/mydb

DB = PostgresEngine(
    config={
        "dsn": os.environ.get(
            "DATABASE_URL",
            "postgres://postgres:postgres@localhost:5432/bussin",
        ),
    },
)

# ── Registered apps ────────────────────────────────────────

APP_REGISTRY = AppRegistry(
    apps=[
        "db.piccolo_app",                        # content tables
        "piccolo.apps.user.piccolo_app",         # BaseUser
        "piccolo_api.session_auth.piccolo_app",  # SessionsBase
    ],
)
