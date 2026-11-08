import json
from pathlib import Path

import pytest

from agent.ask import answer_question
from agent.graph import run_batch
from agent.llm import CALLS, chat, reset_calls

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures"


def _files():
    names = [
        "CTR-DL-01.json",
        "CTR-DL-02.json",
        "DL-INV-1001.json",
        "DL-INV-1002.json",
        "DL-INV-1003.json",
        "DL-INV-1004.json",
        "DL-INV-1005.json",
        "DL-INV-1006.json",
    ]
    return [(name, (FIX / name).read_bytes()) for name in names]


def test_seeded_batch_matches_the_answer_key():
    profile = json.loads((FIX / "profile.json").read_text(encoding="utf-8"))
    key = json.loads((FIX / "answer_key.json").read_text(encoding="utf-8"))
    report = run_batch(_files(), profile)
    by_id = {item["item_id"]: item for item in report["items"]}
    for item_id, expected in key["invoices"].items():
        item = by_id[item_id]
        assert item["outcome"] == expected["outcome"]
        if "auditor" in expected:
            assert item["auditor"]["verdict"] == expected["auditor"]
            assert item["auditor"]["saw_reasoning"] is False
        if "repairs" in expected:
            assert item["repairs"] == expected["repairs"]
        if "rules_remaining" in expected:
            assert item["failures"] == expected["rules_remaining"]
        if "rules_seen" in expected:
            assert item["failures_seen"] == expected["rules_seen"]
        if expected.get("instruction_like"):
            assert item["instruction_like"] is True
            assert "compliant" not in item["classifier"]["conclusion"].lower()
        if "preferred_deadline_source" in expected:
            assert item["guidance"]["preferred_source"] == expected["preferred_deadline_source"]
            assert item["guidance"]["rejected_source"] == expected["rejected_deadline_source"]
    contract = by_id["CTR-DL-02"]
    assert contract["guidance"]["preferred_source"] == "T4"
    assert report["phase"]["cohort"] == "above"
    assert len(report["cards"]) == 3
    assert len(report["quiz"]) == 3
    assert report["replay"] is True
    assert all(row["provider"] == "omniroute" for row in report["usages"])


def test_pdf_pair_parses_to_the_same_failure():
    profile = json.loads((FIX / "profile.json").read_text(encoding="utf-8"))
    report = run_batch([("DL-INV-1002.pdf", (FIX / "DL-INV-1002.pdf").read_bytes())], profile)
    item = report["items"][0]
    assert item["failures"] == ["buyer_id_present"]
    assert item["repairs"] == 1
    assert "totals_reconcile" in item["failures_seen"]
    assert item["instruction_like"] is True


def test_unsupported_questions_abstain_without_a_model_call(monkeypatch):
    questions = json.loads((FIX / "unsupported_questions.json").read_text(encoding="utf-8"))
    assert len(questions) == 10

    def boom(*_args, **_kwargs):
        raise AssertionError("model client was called")

    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setattr("agent.llm.chat", boom)
    monkeypatch.setattr("agent.ask.complete", __import__("agent.llm", fromlist=["complete"]).complete)
    reset_calls()
    for question in questions:
        answer = answer_question(question)
        assert answer["abstained"] is True
        assert answer["to_verify"] is True
    assert CALLS == 0


def test_trace_question_answers_from_the_loaded_review(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "replay")
    trace = {
        "phase": {"cohort": "above"},
        "narrative": "Bounded readiness pack. Not a return. Not an ASP transmission.",
        "items": [
            {
                "item_id": "DL-INV-1002",
                "outcome": "to_verify",
                "repairs": 1,
                "failures": ["buyer_id_present"],
                "auditor": {"verdict": "agree"},
            }
        ],
    }
    answer = answer_question("Help me with this trace", trace)
    assert answer["abstained"] is False
    assert answer["model"] == "replay"
    assert "DL-INV-1002" in answer["answer_en"]
    assert "buyer_id_present" in answer["answer_en"]
    assert "Leave this document to verify" in answer["answer_en"]
    assert "DL-INV-1002" in answer["answer_ar"]
    assert answer["citations"] == []
    named = answer_question("Why is DL-INV-1001 still to verify?", {
        "items": trace["items"] + [{
            "item_id": "DL-INV-1001",
            "outcome": "pass",
            "repairs": 0,
            "failures": [],
            "auditor": {"verdict": "agree", "reason": "The conclusion fits the profile."},
        }],
    })
    assert "DL-INV-1001" in named["answer_en"]
    assert "DL-INV-1002" not in named["answer_en"]


def test_threshold_answer_cites_english_evidence():
    answer = answer_question("لماذا لا يحدد مبلغ 375000 مرحلة الفوترة الإلكترونية؟")
    assert answer["abstained"] is False
    sources = {item["source"] for item in answer["citations"]}
    assert "T5" in sources
    assert "T4" in sources
    assert "does not set the eInvoicing phase" in answer["answer_en"]
    assert "ترجمة المكتب" in answer["answer_ar"]


def test_chat_is_the_only_live_client(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "1")
    with pytest.raises(Exception):
        chat([{"role": "user", "content": "ping"}], "gh/gpt-5.6-terra")
