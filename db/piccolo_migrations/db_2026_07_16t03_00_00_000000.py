from piccolo.apps.migrations.auto.migration_manager import MigrationManager

ID = "2026-07-16T03:00:00:000000"
VERSION = "1.33.0"
DESCRIPTION = "Drop Theme.home_template — themes no longer control content (home renders the Page body)"


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="db", description=DESCRIPTION
    )

    # add_raw takes a *callable*; run the idempotent DROP via table raw().
    async def drop_home_template_column():
        from db.tables import Theme
        await Theme.raw("ALTER TABLE themes DROP COLUMN IF EXISTS home_template")

    manager.add_raw(drop_home_template_column)
    return manager
