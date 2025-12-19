"""Database migration utilities for syncing table structure."""
import logging
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def sync_database_schema(engine: AsyncEngine, drop_all: bool = False):
    """
    Sync database schema with model definitions.
    Automatically detects and adds missing columns.
    
    Args:
        engine: SQLAlchemy async engine
        drop_all: If True, drop all tables and recreate (WARNING: loses all data!)
    """
    from app.core.database import Base
    # Import all models to ensure they're registered
    from app.models import user, position  # noqa: F401
    
    async with engine.begin() as conn:
        if drop_all:
            logger.warning("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("All tables dropped")
        
        # Create tables (only creates if not exists)
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created/verified")
        
        # Auto-sync columns for all models
        await conn.run_sync(_auto_migrate_columns, Base)
        
    logger.info("Database schema sync completed")


def _get_column_type_sql(column) -> str:
    """Convert SQLAlchemy column type to SQL type string."""
    from sqlalchemy import Integer, String, Float, Boolean, DateTime, Text
    from sqlalchemy.types import Enum
    
    col_type = type(column.type)
    
    if col_type == Integer:
        return "INTEGER"
    elif col_type == String:
        length = getattr(column.type, 'length', 255) or 255
        return f"VARCHAR({length})"
    elif col_type == Float:
        return "FLOAT"
    elif col_type == Boolean:
        return "BOOLEAN"
    elif col_type == DateTime:
        return "TIMESTAMP"
    elif col_type == Text:
        return "TEXT"
    elif col_type == Enum or 'Enum' in str(col_type):
        # For enum types, use VARCHAR
        return "VARCHAR(50)"
    else:
        # Fallback - try to use the dialect-specific compile
        try:
            return str(column.type)
        except Exception:
            return "TEXT"


def _get_default_sql(column) -> str:
    """Get SQL default value for a column."""
    if column.default is not None and hasattr(column.default, 'arg'):
        default = column.default.arg
        # Skip callable defaults (like datetime.utcnow)
        if callable(default):
            return ""
        if isinstance(default, bool):
            return " DEFAULT TRUE" if default else " DEFAULT FALSE"
        elif isinstance(default, (int, float)):
            return f" DEFAULT {default}"
        elif isinstance(default, str):
            return f" DEFAULT '{default}'"
    return ""


def _auto_migrate_columns(conn, Base):
    """Automatically add missing columns by comparing model to database."""
    inspector = inspect(conn)
    table_names = inspector.get_table_names()
    
    for table_name, table in Base.metadata.tables.items():
        # Check if table exists
        if table_name not in table_names:
            logger.info(f"Table {table_name} doesn't exist yet, skipping column migration")
            continue
        
        # Get existing columns
        existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
        
        # Check each model column
        for column in table.columns:
            if column.name not in existing_columns:
                col_type = _get_column_type_sql(column)
                default = _get_default_sql(column)
                
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{default}"
                try:
                    conn.execute(text(sql))
                    logger.info(f"Added column {table_name}.{column.name} ({col_type}{default})")
                except Exception as e:
                    logger.error(f"Failed to add column {table_name}.{column.name}: {e}")
        
        # Create indexes for columns that have index=True
        for column in table.columns:
            if column.index and column.name in existing_columns:
                index_name = f"ix_{table_name}_{column.name}"
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column.name})"))
                except Exception:
                    pass  # Index might already exist
