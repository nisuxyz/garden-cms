from piccolo.apps.migrations.auto.migration_manager import MigrationManager

ID = "2026-04-10T09:00:00:000000"
VERSION = "1.33.0"
DESCRIPTION = "rename pages.body_md to pages.body"


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="db", description=DESCRIPTION
    )

    manager.rename_column(
        table_class_name="Page",
        tablename="pages",
        old_column_name="body_md",
        new_column_name="body",
        old_db_column_name="body_md",
        new_db_column_name="body",
    )

    return manager
