from fastapi.testclient import TestClient

from server.app import create_app


def _set_min_api_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("ALLOW_NON_POSTGRES_DATABASE_URL", "true")
    monkeypatch.setenv("API_KEYS", "dev-key-1")


def test_api_runs_without_frontend_mount_when_disabled(monkeypatch):
    _set_min_api_env(monkeypatch)
    monkeypatch.setenv("SERVE_FRONTEND", "false")

    app = create_app()
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200

    root = client.get("/")
    assert root.status_code == 404


def test_api_runs_when_frontend_directory_is_missing(monkeypatch):
    _set_min_api_env(monkeypatch)
    monkeypatch.setenv("SERVE_FRONTEND", "true")
    monkeypatch.setenv("FRONTEND_DIR", "tests/.missing_frontend_for_boundary_test")

    app = create_app()
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200

    root = client.get("/")
    assert root.status_code == 404


def test_runtime_health_reports_interpreter_and_claude_readiness(monkeypatch):
    _set_min_api_env(monkeypatch)
    monkeypatch.setenv("SERVE_FRONTEND", "false")

    app = create_app()
    client = TestClient(app)

    runtime = client.get("/health/runtime")
    assert runtime.status_code == 200

    payload = runtime.json()
    assert payload["status"] in {"healthy", "degraded"}
    assert isinstance(payload.get("python_executable"), str)
    assert payload.get("python_executable")
    assert isinstance(payload.get("claude"), dict)
    assert "sdk_available" in payload["claude"]
    assert "api_key_present" in payload["claude"]
