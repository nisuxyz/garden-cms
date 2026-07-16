from piccolo.apps.migrations.auto.migration_manager import MigrationManager

ID = "2026-07-16T00:00:00:000000"
VERSION = "1.33.0"
DESCRIPTION = "Add Theme.site_head — per-theme <head> HTML combined with the site-level site_head setting"


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="db", description=DESCRIPTION
    )

    # Per-theme Site Head column. Idempotent (IF NOT EXISTS) so it's safe on
    # an install that already has the column (e.g. seeded fresh from the model).
    # add_raw takes a *callable*; run the ALTER via the table's raw() executor.
    async def add_site_head_column():
        from db.tables import Theme
        await Theme.raw(
            "ALTER TABLE themes "
            "ADD COLUMN IF NOT EXISTS site_head TEXT NOT NULL DEFAULT ''"
        )

    manager.add_raw(add_site_head_column)
    return manager
