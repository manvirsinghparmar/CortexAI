from db.engine import create_db_engine


def test_create_db_engine_supports_sqlite_in_memory(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("DB_POOL_SIZE", "5")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "10")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "30")

    engine = create_db_engine()
    try:
        assert engine.url.get_backend_name() == "sqlite"
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT 1").scalar_one() == 1
    finally:
        engine.dispose()
