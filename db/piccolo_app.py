# db/piccolo_app.py
"""Piccolo AppConfig for the content tables (posts, projects, site_content)."""
import os

from piccolo.conf.apps import AppConfig, table_finder

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

APP_CONFIG = AppConfig(
    app_name="db",
    migrations_folder_path=os.path.join(CURRENT_DIRECTORY, "piccolo_migrations"),
    table_classes=table_finder(modules=["db.tables"]),
    migration_dependencies=[],
    commands=[],
)
