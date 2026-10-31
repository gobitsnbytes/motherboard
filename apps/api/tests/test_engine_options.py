from fastapi.testclient import TestClient

from app.database import engine_options
from app.main import create_app


def test_postgres_gets_capped_pool_and_statement_timeout():
    options = engine_options("postgresql+asyncpg://u:p@db/x")
    assert options["pool_size"] + options["max_overflow"] <= 8
    assert options["pool_timeout"] <= 10
    assert options["connect_args"]["server_settings"]["statement_timeout"] == "30000"


def test_sqlite_gets_no_pool_arguments():
    # SQLite's pool class rejects pool_size/max_overflow, which would break local runs and tests.
    assert engine_options("sqlite+aiosqlite:///x.db") == {"pool_pre_ping": True}


def test_large_json_is_gzipped():
    app = create_app()

    @app.get("/__big")
    def big():
        return {"rows": ["motherboard"] * 400}

    response = TestClient(app).get("/__big", headers={"Accept-Encoding": "gzip"})
    assert response.headers["content-encoding"] == "gzip"
    assert len(response.json()["rows"]) == 400
