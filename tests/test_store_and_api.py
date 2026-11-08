import json
from datetime import datetime, timedelta, timezone

from agent import llm as llm_mod
from backend.app import _newest_per_filename
from backend.store import Store


def test_cross_tenant_reads_are_blocked(tmp_path):
    store = Store(tmp_path / "readiness.db")
    for index in range(10):
        stored = store.put_document(f"doc-{index}", "tenant_desert_ledger", f"file-{index}.json", b"{}", True)
        assert store.get_document("tenant_other_ledger", stored["id"]) is None
        assert store.get_document("tenant_desert_ledger", stored["id"])["filename"] == f"file-{index}.json"
    blocked = [row for row in store.audits_for("tenant_other_ledger") if row["action"] == "cross_tenant_blocked"]
    assert len(blocked) == 10
    store.close()


def test_payload_is_encrypted_and_audit_survives_reopen(tmp_path):
    path = tmp_path / "readiness.db"
    store = Store(path)
    store.put_document("doc-1", "tenant_desert_ledger", "note.json", b'{"trn":"SYNTHETIC_TRN_NOT_VALID"}', True)
    store.audit("tenant_desert_ledger", "run-1", "approver", "approve", "bounded pack")
    store.close()
    raw = path.read_bytes()
    assert b"SYNTHETIC_TRN_NOT_VALID" not in raw
    again = Store(path)
    rows = again.audits_for("tenant_desert_ledger")
    assert any(row["action"] == "approve" for row in rows)
    again.close()


def test_retention_and_deletion_keep_an_audit_row(tmp_path):
    store = Store(tmp_path / "readiness.db")
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    store.put_document("old", "tenant_desert_ledger", "old.json", b"{}", True, created_at=old)
    assert store.enforce_retention(30) == 1
    assert store.get_document("tenant_desert_ledger", "old") is None
    store.put_document("fresh", "tenant_desert_ledger", "fresh.json", b"{}", True)
    assert store.delete_tenant_documents("tenant_desert_ledger", "approver") == 1
    actions = [row["action"] for row in store.audits_for("tenant_desert_ledger")]
    assert "retention_deleted" in actions
    assert "tenant_documents_deleted" in actions
    store.close()


def test_backup_copies_the_database(tmp_path):
    store = Store(tmp_path / "readiness.db")
    store.audit("tenant_desert_ledger", "", "system", "marker", "keep")
    target = store.backup_to(tmp_path / "backup")
    store.close()
    restored = Store(target)
    assert any(row["action"] == "marker" for row in restored.audits_for("tenant_desert_ledger"))
    restored.close()


def test_non_synthetic_upload_does_not_call_the_model(client, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    called = {"n": 0}

    def boom(*_args, **_kwargs):
        called["n"] += 1
        raise RuntimeError("model client was called")

    monkeypatch.setattr("agent.llm.chat", boom)
    response = client.post(
        "/api/documents",
        data={"tenant_id": "tenant_desert_ledger", "synthetic": "false"},
        files={"file": ("secret.json", b'{"invoice_id":"X"}', "application/json")},
    )
    assert response.status_code == 403
    assert called["n"] == 0


def test_demo_run_approval_and_ask(client, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    called = {"n": 0}
    original_chat = llm_mod.chat

    def boom(*_args, **_kwargs):
        called["n"] += 1
        raise RuntimeError("model client was called")

    monkeypatch.setattr("agent.llm.chat", boom)
    refused = client.post(
        "/api/ask",
        json={"tenant_id": "tenant_desert_ledger", "question": "Are we compliant?", "synthetic": True},
    )
    assert refused.status_code == 200
    assert refused.json()["abstained"] is True
    assert called["n"] == 0
    monkeypatch.setattr("agent.llm.chat", original_chat)
    monkeypatch.setenv("LLM_MODE", "replay")

    loaded = client.post("/api/demo/load")
    assert loaded.status_code == 200
    ids = [item["id"] for item in loaded.json()["documents"]]
    again = client.post("/api/demo/load")
    assert again.status_code == 200
    assert [item["id"] for item in again.json()["documents"]] == ids
    assert client.get("/api/dashboard").json()["documents"] == len(ids)
    started = client.post("/api/runs", json={"tenant_id": "tenant_desert_ledger", "document_ids": ids})
    assert started.status_code == 200, started.text
    run_id = started.json()["run_id"]
    assert started.json()["replay"] is True
    events = client.get("/api/runs/" + run_id + "/events", params={"tenant_id": "tenant_desert_ledger"})
    assert events.status_code == 200
    assert "Validator" in events.text or "validator" in events.text
    report = client.get("/api/reports/" + run_id, params={"tenant_id": "tenant_desert_ledger"}).json()
    outcomes = {item["item_id"]: item["outcome"] for item in report["items"]}
    assert outcomes["DL-INV-1002"] == "to_verify"
    assert outcomes["DL-INV-1005"] == "to_verify"
    desert = next(row for row in client.get("/api/dashboard").json()["rows"] if row["tenant_id"] == "tenant_desert_ledger")
    marks = {item["item_id"]: item for item in desert["marks"]}
    assert desert["pass_count"] == 4
    assert desert["verify_count"] == 4
    assert desert["phase_cohort"] == "above"
    assert marks["DL-INV-1002"]["held"] == "buyer_id_present"
    assert marks["DL-INV-1004"]["auditor"] == "disagree"
    decision = client.post(
        f"/api/runs/{run_id}/decisions",
        json={"tenant_id": "tenant_desert_ledger", "action": "approve", "actor": "reviewer@desert-ledger.example", "note": "Bounded pack"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved_bounded"
    final = client.get("/api/reports/" + run_id, params={"tenant_id": "tenant_desert_ledger"}).json()
    assert final["status"] == "approved_bounded"
    latest = client.get("/api/runs/latest", params={"tenant_id": "tenant_desert_ledger"})
    assert latest.status_code == 200
    assert latest.json()["run_id"] == run_id
    assert latest.json()["status"] == "approved_bounded"
    assert client.get("/api/runs/latest", params={"tenant_id": "tenant_other_ledger"}).status_code == 404
    assert "Not a return" in final["narrative"] or "not a return" in final["narrative"].lower()
    other = client.get("/api/reports/" + run_id, params={"tenant_id": "tenant_other_ledger"})
    assert other.status_code == 404
    helped = client.post(
        "/api/ask",
        json={
            "tenant_id": "tenant_desert_ledger",
            "question": "Help me with this trace",
            "synthetic": True,
            "run_id": run_id,
        },
    )
    assert helped.status_code == 200
    body = helped.json()
    assert body["abstained"] is False
    assert "DL-INV-1002" in body["answer_en"]
    assert body["model"] == "replay"


def test_stale_deadline_prefers_the_newer_source(client):
    raw = ( __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "fixtures" / "DL-INV-1006.json").read_bytes()
    stored = client.post(
        "/api/documents",
        data={"tenant_id": "tenant_desert_ledger", "synthetic": "true"},
        files={"file": ("DL-INV-1006.json", raw, "application/json")},
    )
    assert stored.status_code == 200
    started = client.post(
        "/api/runs",
        json={"tenant_id": "tenant_desert_ledger", "document_ids": [stored.json()["id"]]},
    )
    report = client.get(
        "/api/reports/" + started.json()["run_id"],
        params={"tenant_id": "tenant_desert_ledger"},
    ).json()
    item = report["items"][0]
    assert item["guidance"]["preferred_source"] == "T4"
    assert item["guidance"]["rejected_source"] == "T2"
    assert item["outcome"] == "pass"


def test_newest_copy_of_each_filename_is_kept():
    chosen = _newest_per_filename([
        {"id": "old", "filename": "a.json", "created_at": "2026-01-01"},
        {"id": "new", "filename": "a.json", "created_at": "2026-02-01"},
        {"id": "b", "filename": "b.json", "created_at": "2026-01-01"},
    ])
    assert set(chosen) == {"new", "b"}


def test_companies_can_be_added_edited_and_removed(client):
    created = client.post(
        "/api/companies",
        json={"legal_name": "Sample Quay LLC", "seat": "mainland", "stated_revenue_aed": 1000000},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["trn"].endswith("_NOT_VALID")
    assert body["free_zone"] is False
    edited = client.put(
        "/api/companies/" + body["tenant_id"],
        json={"legal_name": "Sample Quay Trading LLC", "seat": "free_zone", "stated_revenue_aed": 2000000},
    )
    assert edited.status_code == 200
    assert edited.json()["legal_name"] == "Sample Quay Trading LLC"
    assert edited.json()["free_zone"] is True
    board = client.get("/api/dashboard")
    assert board.status_code == 200
    names = {row["legal_name"] for row in board.json()["rows"]}
    assert "Desert Ledger Trading LLC" in names
    assert "Sample Quay Trading LLC" in names
    blocked = client.post("/api/companies/" + body["tenant_id"] + "/process")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Upload a synthetic file before running the agents."
    asked = client.post(
        "/api/ask",
        json={"tenant_id": body["tenant_id"], "question": "Help me with this trace", "synthetic": True},
    )
    assert asked.json()["abstained"] is True
    assert "Run the agents" in asked.json()["answer_en"]
    removed = client.delete("/api/companies/" + body["tenant_id"])
    assert removed.status_code == 200
    assert removed.json()["documents_removed"] == 0
    assert client.get("/api/tenant", params={"tenant_id": body["tenant_id"]}).status_code == 404


def test_stream_accepts_the_run_before_the_graph_finishes(client, monkeypatch):
    import time

    from agent import graph as graph_mod

    loaded = client.post("/api/demo/load")
    assert loaded.status_code == 200
    ids = [item["id"] for item in loaded.json()["documents"]]
    original = graph_mod.orchestrator

    def slow(state):
        time.sleep(0.6)
        return original(state)

    monkeypatch.setattr(graph_mod, "orchestrator", slow)
    started = time.monotonic()
    accepted_at = None
    done_at = None
    body = []
    with client.stream(
        "POST",
        "/api/runs",
        json={"tenant_id": "tenant_desert_ledger", "document_ids": ids},
        headers={"Accept": "text/event-stream"},
    ) as response:
        assert response.status_code == 200
        for chunk in response.iter_text():
            body.append(chunk)
            now = time.monotonic()
            if accepted_at is None and "accepted" in chunk:
                accepted_at = now
            if done_at is None and "event: done" in chunk:
                done_at = now
    text = "".join(body)
    assert accepted_at is not None
    assert done_at is not None
    assert accepted_at - started < 0.4
    assert done_at > accepted_at
    assert '"phase": "start"' in text
    assert "Parsing DL-INV-1002.pdf" in text
    assert "Model call for DL-INV-1002" in text
    assert "event: done" in text
    run_id = text.split('"run_id": "', 1)[1].split('"', 1)[0]
    report = client.get("/api/reports/" + run_id, params={"tenant_id": "tenant_desert_ledger"})
    assert report.status_code == 200
    assert report.json()["items"]


def test_model_catalog_switches_within_the_configured_pair(client, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gh/gpt-5.6-terra")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "gh/gpt-5.6-luna")
    body = client.get("/api/models").json()
    assert body["provider"] == "omniroute"
    assert body["selected"] == "gh/gpt-5.6-terra"
    assert body["models"] == ["gh/gpt-5.6-terra", "gh/gpt-5.6-luna"]
    switched = client.put("/api/models", json={"model": "gh/gpt-5.6-luna"})
    assert switched.status_code == 200
    assert switched.json()["selected"] == "gh/gpt-5.6-luna"
    blocked = client.put("/api/models", json={"model": "gh/not-a-model"})
    assert blocked.status_code == 400
    assert client.get("/api/models").json()["selected"] == "gh/gpt-5.6-luna"


def test_live_catalog_keeps_one_id_per_model_and_complete_uses_it(monkeypatch):
    from agent import llm

    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_MODEL", "gh/gpt-5.6-terra")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "gh/gpt-5.6-luna")
    monkeypatch.setattr(
        llm,
        "gateway_model_ids",
        lambda: ["gh/claude-haiku-5.5", "github/claude-haiku-5.5", "auto/fast"],
    )
    listed = llm.catalog()
    assert listed["models"][0] == "gh/gpt-5.6-terra"
    assert "github/claude-haiku-5.5" not in listed["models"]
    assert "gh/claude-haiku-5.5" in listed["models"]
    seen = []

    def fake_chat(_messages, model):
        seen.append(model)
        return {"content": "ok", "model": model, "usage": {}, "provider": "omniroute"}

    monkeypatch.setattr(llm, "chat", fake_chat)
    llm.choose_model("github/claude-haiku-5.5")
    assert "gh/gpt-5.6-terra" in llm.catalog()["models"]
    llm.choose_model("gh/gpt-5.6-terra")
    assert llm.selected_model() == "gh/gpt-5.6-terra"
    llm.choose_model("gh/claude-haiku-5.5")
    result = llm.complete("classifier", "user text", "canned")
    assert seen == ["gh/claude-haiku-5.5"]
    assert result["model"] == "gh/claude-haiku-5.5"
    assert result["replay"] is False


def test_residency_record(client):
    body = client.get("/api/residency").json()
    assert body["provider"] == "omniroute"
    assert body["residency_verified"] is False
    assert "20128" in body["inference_base_url"] or body["inference_base_url"].endswith("/v1")
