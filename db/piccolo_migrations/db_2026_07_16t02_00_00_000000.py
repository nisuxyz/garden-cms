from piccolo.apps.migrations.auto.migration_manager import MigrationManager

ID = "2026-07-16T02:00:00:000000"
VERSION = "1.33.0"
DESCRIPTION = "Add Theme.home_template — admin-editable per-theme home page body override"


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="db", description=DESCRIPTION
    )

    # add_raw takes a *callable*; run the idempotent ALTER via table raw().
    async def add_home_template_column():
        from db.tables import Theme
        await Theme.raw(
            "ALTER TABLE themes "
            "ADD COLUMN IF NOT EXISTS home_template TEXT NOT NULL DEFAULT ''"
        )

    manager.add_raw(add_home_template_column)
    return manager
