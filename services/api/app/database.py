from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
class Base(DeclarativeBase): pass


def ensure_schema_compatibility() -> None:
    """Apply additive v1 migrations for databases created by earlier portfolio releases."""
    additions = {
        "organizations": {
            "low_stock_threshold": "FLOAT DEFAULT 10",
            "overstock_days": "INTEGER DEFAULT 60",
            "digest_enabled": "BOOLEAN DEFAULT TRUE",
        },
        "uploads": {"total_rows": "INTEGER DEFAULT 0", "payload": "JSON", "completed_at": "TIMESTAMP"},
        "sales": {"unit_price": "FLOAT", "product_name": "VARCHAR(240)", "category": "VARCHAR(120)"},
        "inventory": {"reorder_point": "FLOAT", "product_name": "VARCHAR(240)", "category": "VARCHAR(120)", "unit_cost": "FLOAT"},
        "forecasts": {"confidence": "VARCHAR(16) DEFAULT 'limited'", "status": "VARCHAR(32) DEFAULT 'ready'"},
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table_name, columns in additions.items():
            if not inspector.has_table(table_name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))


def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
