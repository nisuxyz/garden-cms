from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Text
from piccolo.columns.indexes import IndexMethod

ID = "2026-04-09T11:10:52:250109"
VERSION = "1.33.0"
DESCRIPTION = "add empty_template to collections"


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="db", description=DESCRIPTION
    )

    manager.add_column(
        table_class_name="Collection",
        tablename="collections",
        column_name="empty_template",
        db_column_name="empty_template",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    return manager
