import json
from pathlib import Path

from agent.review import field_failures, parse_document, phase_for
from agent.sources import entails, passages, register

ROOT = Path(__file__).resolve().parents[1]


def test_passages_sit_inside_the_frozen_extracts():
    for item in register()["passages"]:
        extract = (ROOT / "data" / "sources" / "text" / f"{item['source']}.txt").read_text(encoding="utf-8")
        assert item["text"] in extract
        assert item["source"] in {"T1", "T2", "T3", "T4", "T5"}


def test_golden_claims_entail():
    claims = json.loads((ROOT / "data" / "fixtures" / "claims.json").read_text(encoding="utf-8"))
    known = passages()
    assert len(claims) >= 8
    for claim in claims:
        text = known[claim["passage"]]["text"]
        assert entails(text, claim["tokens"])


def test_twenty_arithmetic_and_field_cases():
    cases = json.loads((ROOT / "data" / "fixtures" / "arithmetic_cases.json").read_text(encoding="utf-8"))
    assert len(cases) == 20
    for case in cases:
        found = field_failures(case["invoice"], set(case["prior_ids"]))
        assert found == case["expect_rules"], case["id"]


def test_revenue_boundaries():
    rows = json.loads((ROOT / "data" / "fixtures" / "boundaries.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in rows] == ["below", "equal", "above"]
    for row in rows:
        phase = phase_for(row["revenue_aed"])
        if row["expect"] == "to_verify":
            assert phase["status"] == "to_verify"
            assert phase["cohort"] == "equal"
        else:
            assert phase["cohort"] == row["expect"]
            assert phase["status"] == "cited"


def test_sample_pdfs_parse():
    files = sorted((ROOT / "sample").glob("*.pdf"))
    assert len(files) == 14
    for path in files:
        parsed = parse_document(path.name, path.read_bytes())
        assert parsed["_filename"] == path.name
        assert parsed.get("invoice_id") or parsed.get("contract_id")
    fuller = parse_document("DL-INV-2005.pdf", (ROOT / "sample" / "DL-INV-2005.pdf").read_bytes())
    assert len(fuller["lines"]) == 8
    assert fuller["buyer_address"].startswith("Office 906")
    assert fuller["purchase_order"] == "AD-PO-318"
    broken = parse_document("DL-INV-2004.pdf", (ROOT / "sample" / "DL-INV-2004.pdf").read_bytes())
    assert field_failures(broken, set()) == ["totals_reconcile"]
    missing = parse_document("DL-INV-2003.pdf", (ROOT / "sample" / "DL-INV-2003.pdf").read_bytes())
    assert field_failures(missing, set()) == ["buyer_id_present"]


def test_manifest_hashes_match():
    import hashlib

    manifest = json.loads((ROOT / "data" / "fixtures" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]
    for item in manifest["files"]:
        digest = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
        assert digest == item["sha256"]
        assert item["author"] == "synthetic-desk"
