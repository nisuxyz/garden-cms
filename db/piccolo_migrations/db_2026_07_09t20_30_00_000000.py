from piccolo.apps.migrations.auto.migration_manager import MigrationManager

ID = "2026-07-09T20:30:00:000000"
VERSION = "1.33.0"
DESCRIPTION = "Add DB-level uniqueness for single-active theme, single homepage, and (collection, slug) item uniqueness"


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="db", description=DESCRIPTION
    )

    # A single theme can be active at a time. App code toggles others off,
    # but a partial unique index enforces it at the DB so concurrent admin
    # saves can't leave two active themes. Idempotent: IF NOT EXISTS.
    manager.add_raw(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS themes_active_unique
        ON themes (active)
        WHERE active = TRUE
        """
    )

    # Similarly, at most one homepage. (One row with is_homepage=true.)
    manager.add_raw(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS pages_homepage_unique
        ON pages (is_homepage)
        WHERE is_homepage = TRUE
        """
    )

    # CollectionItem.slug was unique=False at the model level — routing
    # (resolve_collection_item) returns the first match, so two items in the
    # same collection sharing a slug silently shadow each other. Enforce
    # uniqueness within a collection at the DB. Idempotent.
    manager.add_raw(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS collection_items_collection_slug_unique
        ON collection_items (collection, slug)
        """
    )

    return manager