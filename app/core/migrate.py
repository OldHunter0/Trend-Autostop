"""Database migration utilities for syncing table structure."""
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def sync_database_schema(engine: AsyncEngine, drop_all: bool = False):
    """
    Sync database schema with model definitions.
    
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
        
        # Run column migrations for existing tables
        await _migrate_api_credentials(conn)
        await _migrate_users(conn)
        await _migrate_sessions(conn)
        await _migrate_position_configs(conn)
        
    logger.info("Database schema sync completed")


async def _column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = await conn.execute(text(f"""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = :table_name AND column_name = :column_name
    """), {"table_name": table_name, "column_name": column_name})
    return result.fetchone() is not None


async def _add_column_if_not_exists(conn, table_name: str, column_name: str, column_def: str):
    """Add a column to a table if it doesn't exist."""
    if not await _column_exists(conn, table_name, column_name):
        await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))
        logger.info(f"Added column {table_name}.{column_name}")
        return True
    return False


async def _migrate_api_credentials(conn):
    """Migrate api_credentials table."""
    table = "api_credentials"
    
    # Check if table exists
    result = await conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = :table_name
    """), {"table_name": table})
    if not result.fetchone():
        logger.info(f"Table {table} doesn't exist, will be created by create_all")
        return
    
    # Add missing columns
    await _add_column_if_not_exists(conn, table, "user_id", "INTEGER")
    await _add_column_if_not_exists(conn, table, "wrapped_data_key", "TEXT")
    await _add_column_if_not_exists(conn, table, "error_count", "INTEGER DEFAULT 0")
    await _add_column_if_not_exists(conn, table, "last_used_at", "TIMESTAMP")
    await _add_column_if_not_exists(conn, table, "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    
    # Create index if not exists
    try:
        await conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table}(user_id)"))
    except Exception as e:
        logger.debug(f"Index might already exist: {e}")


async def _migrate_users(conn):
    """Migrate users table."""
    table = "users"
    
    result = await conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = :table_name
    """), {"table_name": table})
    if not result.fetchone():
        return
    
    # Add missing columns for user model
    await _add_column_if_not_exists(conn, table, "username", "VARCHAR(100)")
    await _add_column_if_not_exists(conn, table, "role", "VARCHAR(20) DEFAULT 'user'")
    await _add_column_if_not_exists(conn, table, "is_active", "BOOLEAN DEFAULT TRUE")
    await _add_column_if_not_exists(conn, table, "is_email_verified", "BOOLEAN DEFAULT FALSE")
    await _add_column_if_not_exists(conn, table, "email_verified_at", "TIMESTAMP")
    await _add_column_if_not_exists(conn, table, "email_verify_token", "VARCHAR(255)")
    await _add_column_if_not_exists(conn, table, "email_verify_token_expires", "TIMESTAMP")
    await _add_column_if_not_exists(conn, table, "password_reset_token", "VARCHAR(255)")
    await _add_column_if_not_exists(conn, table, "password_reset_token_expires", "TIMESTAMP")
    await _add_column_if_not_exists(conn, table, "last_login_at", "TIMESTAMP")
    await _add_column_if_not_exists(conn, table, "failed_login_attempts", "INTEGER DEFAULT 0")
    await _add_column_if_not_exists(conn, table, "locked_until", "TIMESTAMP")
    await _add_column_if_not_exists(conn, table, "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")


async def _migrate_sessions(conn):
    """Migrate sessions table."""
    table = "sessions"
    
    result = await conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = :table_name
    """), {"table_name": table})
    if not result.fetchone():
        return
    
    await _add_column_if_not_exists(conn, table, "refresh_token_hash", "VARCHAR(255)")
    await _add_column_if_not_exists(conn, table, "refresh_expires_at", "TIMESTAMP")
    await _add_column_if_not_exists(conn, table, "revoked_at", "TIMESTAMP")
    await _add_column_if_not_exists(conn, table, "last_used_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")


async def _migrate_position_configs(conn):
    """Migrate position_configs table."""
    table = "position_configs"
    
    result = await conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = :table_name
    """), {"table_name": table})
    if not result.fetchone():
        return
    
    # SuperTrend parameters that might be missing
    await _add_column_if_not_exists(conn, table, "ema_len", "INTEGER DEFAULT 8")
    await _add_column_if_not_exists(conn, table, "atr_len", "INTEGER DEFAULT 14")
    await _add_column_if_not_exists(conn, table, "base_mult", "FLOAT DEFAULT 2.0")
    await _add_column_if_not_exists(conn, table, "vol_lookback", "INTEGER DEFAULT 20")
    await _add_column_if_not_exists(conn, table, "vol_power", "FLOAT DEFAULT 1.0")
    await _add_column_if_not_exists(conn, table, "trend_lookback", "INTEGER DEFAULT 25")
    await _add_column_if_not_exists(conn, table, "trend_impact", "FLOAT DEFAULT 0.4")
    await _add_column_if_not_exists(conn, table, "mult_min", "FLOAT DEFAULT 1.0")
    await _add_column_if_not_exists(conn, table, "mult_max", "FLOAT DEFAULT 4.0")
    await _add_column_if_not_exists(conn, table, "confirm_bars", "INTEGER DEFAULT 1")
    await _add_column_if_not_exists(conn, table, "delay_bars", "INTEGER DEFAULT 0")
    await _add_column_if_not_exists(conn, table, "bars_since_open", "INTEGER DEFAULT 0")
    await _add_column_if_not_exists(conn, table, "last_regime", "INTEGER DEFAULT 0")
    await _add_column_if_not_exists(conn, table, "entry_bar_time", "TIMESTAMP")

