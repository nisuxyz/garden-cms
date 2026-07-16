from piccolo.apps.migrations.auto.migration_manager import MigrationManager

ID = "2026-07-16T01:00:00:000000"
VERSION = "1.33.0"
DESCRIPTION = "Add Theme.css_framework — per-theme base CSS framework (moved out of the site-level setting)"


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="db", description=DESCRIPTION
    )

    # Per-theme base CSS framework key. Idempotent (IF NOT EXISTS).
    # add_raw takes a *callable*; run the ALTER via the table raw executor.
    async def add_css_framework_column():
        from db.tables import Theme
        await Theme.raw(
            "ALTER TABLE themes "
            "ADD COLUMN IF NOT EXISTS css_framework VARCHAR(255) "
            "NOT NULL DEFAULT 'pico'"
        )
        # Drop the now-orphaned site-level css_framework setting, if present.
        from db.tables import SiteSettings
        await SiteSettings.raw(
            "DELETE FROM site_settings WHERE key = 'css_framework'"
        )

    manager.add_raw(add_css_framework_column)
    return manager
