import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _replay_mode(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "replay")
    monkeypatch.setenv("TENANT_VOLUME_KEY", "test-passphrase")
    monkeypatch.setenv("RESIDENCY_VERIFIED", "false")
    from agent.llm import reset_selection

    reset_selection()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "readiness.db"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backup"))
    monkeypatch.setenv("TENANT_VOLUME_KEY", "test-passphrase")
    monkeypatch.setenv("LLM_MODE", "replay")
    monkeypatch.setenv("RESIDENCY_VERIFIED", "false")
    monkeypatch.setenv("RETENTION_DAYS", "30")
    from backend import app as app_mod

    app_mod.reset_store()
    with TestClient(app_mod.app) as test_client:
        yield test_client
    app_mod.reset_store()
