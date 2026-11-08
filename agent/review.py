"""Deterministic extract, classify, validate, and blind audit."""
from __future__ import annotations

import base64
import json
import re
from typing import Any

from agent.sources import cite

TOLERANCE = 0.01
FIFTY_MILLION = 50_000_000
INJECTION = re.compile(r"ignore previous|system prompt|you are now|<\|", re.I)
EDUCATIONAL = (
    "Educational only. Guide CTGGCT1 says 0% on the portion of taxable income "
    "not exceeding AED 375,000 and 9% on the portion above that. "
    "One invoice is not taxable income. AED 375,000 does not set the eInvoicing phase."
)


def instruction_like(text: str) -> bool:
    return bool(INJECTION.search(text or ""))


def pdf_strings(raw: bytes) -> str:
    parts = re.findall(rb"\((?:\\\)|\\.|[^)])*\)", raw)
    lines = []
    for part in parts:
        text = part[1:-1].decode("latin-1", "replace")
        text = text.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
        lines.append(text)
    return "\n".join(lines)


def parse_document(filename: str, raw: bytes) -> dict[str, Any]:
    if filename.lower().endswith(".json"):
        data = json.loads(raw.decode("utf-8"))
        flagged = instruction_like(raw.decode("utf-8", "replace"))
    else:
        text = pdf_strings(raw)
        flagged = instruction_like(text)
        if "---JSON---" not in text:
            raise ValueError(f"{filename} has no embedded invoice JSON")
        encoded = "".join(text.split("---JSON---", 1)[1].split())
        data = json.loads(base64.b64decode(encoded))
        flagged = flagged or instruction_like(json.dumps(data))
    if not isinstance(data, dict):
        raise ValueError("document is not an object")
    data["_filename"] = filename
    data["_item_id"] = filename.rsplit(".", 1)[0]
    data["_instruction_like"] = flagged
    data["_page"] = "1"
    return data


def _money(invoice: dict, key: str) -> float:
    return float(invoice.get(key) or 0)


def field_failures(invoice: dict, seen_ids: set[str]) -> list[str]:
    if invoice.get("kind") != "invoice":
        return []
    failures: list[str] = []
    if not str(invoice.get("buyer_trn") or "").strip():
        failures.append("buyer_id_present")
    lines = invoice.get("lines") or []
    net = sum(float(line.get("net") or 0) for line in lines)
    vat = sum(float(line.get("vat") or 0) for line in lines)
    expected = net + vat
    if (
        abs(_money(invoice, "net_total") - net) > TOLERANCE
        or abs(_money(invoice, "vat_total") - vat) > TOLERANCE
        or abs(_money(invoice, "gross_total") - expected) > TOLERANCE
    ):
        failures.append("totals_reconcile")
    invoice_id = str(invoice.get("invoice_id") or "")
    if invoice_id and invoice_id in seen_ids:
        failures.append("duplicate_invoice_id")
    return failures


def repair_totals(invoice: dict) -> dict:
    """Recompute totals from the lines. Never invent a buyer identifier."""
    repaired = dict(invoice)
    lines = [dict(line) for line in invoice.get("lines") or []]
    repaired["lines"] = lines
    net = sum(float(line.get("net") or 0) for line in lines)
    vat = sum(float(line.get("vat") or 0) for line in lines)
    repaired["net_total"] = net
    repaired["vat_total"] = vat
    repaired["gross_total"] = net + vat
    return repaired


def stale_deadline(notes: str) -> dict | None:
    if "July 2026" not in (notes or ""):
        return None
    preferred = cite("T4-equal-or-exceed", ["30 October 2026"])
    rejected = cite("T2-july", ["31 July 2026"])
    supporting = cite("T3-october", ["30 October 2026"])
    return {
        "rule": "stale_deadline",
        "preferred_source": "T4",
        "rejected_source": "T2",
        "citations": [preferred, supporting, rejected],
        "note": "The July 2026 appointment date is historical. The newer FTA notice is T4.",
    }


def phase_for(revenue: float) -> dict:
    if revenue < FIFTY_MILLION:
        return {
            "cohort": "below",
            "status": "cited",
            "appoint": "2027-03-31",
            "implement": "2027-07-01",
            "sources": ["T4-below"],
            "citation": cite("T4-below", ["below AED 50 million", "31 March 2027"]),
            "note": "Exclusions from the eInvoicing scope stay to verify.",
        }
    if float(revenue) == float(FIFTY_MILLION):
        return {
            "cohort": "equal",
            "status": "to_verify",
            "appoint": "to verify",
            "implement": "to verify",
            "sources": ["T3-october", "T4-equal-or-exceed"],
            "citation": cite("T4-equal-or-exceed", ["equal or exceed"]),
            "note": "MoF T3 says annual revenues exceed AED 50 million. FTA T4 says equal or exceed. The equal case stays to verify.",
        }
    return {
        "cohort": "above",
        "status": "cited",
        "appoint": "2026-10-30",
        "implement": "2027-01-01",
        "sources": ["T4-equal-or-exceed", "T3-october"],
        "citation": cite("T4-equal-or-exceed", ["equal or exceed", "30 October 2026"]),
        "note": "On 2026-11-07 the 30 October 2026 appointment date is already past. Exclusions stay to verify. The revenue figure is a customer assertion.",
    }


def citations_for(document: dict) -> list[dict]:
    found = [cite("T1-einvoice", ["structured", "Federal Tax Authority"])]
    notes = document.get("notes") or ""
    if "July 2026" in notes:
        found.append(cite("T2-july", ["31 July 2026"]))
        found.append(cite("T3-october", ["30 October 2026"]))
        found.append(cite("T4-equal-or-exceed", ["30 October 2026"]))
    if "Free Zone" in notes or document.get("seed_classifier_error") == "free_zone":
        found.append(cite("T5-free-zone", ["Qualifying Free Zone Persons"]))
    if document.get("asserted_revenue_aed"):
        found.append(cite("T3-october", ["exceed AED 50 million"]))
        found.append(cite("T4-equal-or-exceed", ["equal or exceed"]))
    found.append(cite("T5-zero", ["375,000"]))
    found.append(cite("T5-nine", ["9%"]))
    unique = []
    seen = set()
    for item in found:
        if item["passage_id"] not in seen:
            seen.add(item["passage_id"])
            unique.append(item)
    return unique


def classify(document: dict) -> dict:
    error = document.get("seed_classifier_error") or ""
    if error == "free_zone":
        conclusion = "Apply 0% as a Qualifying Free Zone Person"
    elif error == "revenue_conflict":
        conclusion = "Schedule eInvoicing using the invoice figure AED 12000000, which is below AED 50 million"
    elif document.get("kind") == "contract":
        conclusion = "Contract stored as evidence. It is not an invoice and it is not a filing."
    else:
        conclusion = (
            "VAT on the invoice is stated at 5%. Whether that rate fits this supply is to verify. "
            "Corporate tax is not computed from this invoice."
        )
    if "compliant" in conclusion.lower():
        conclusion = "Treatment withheld."
    return {
        "item_id": document["_item_id"],
        "conclusion": conclusion,
        "reasoning": "Held back from the auditor.",
        "corporate_tax_note": EDUCATIONAL,
        "confidence": 0.42,
    }


def audit(conclusion: str, document: dict, profile: dict) -> dict:
    """Blind check. The reasoning string is not an input."""
    if "Qualifying Free Zone" in conclusion and not profile.get("free_zone"):
        verdict, reason = (
            "disagree",
            "The tenant profile is mainland. T5 limits the 0% rate to Qualifying Income of a Qualifying Free Zone Person, and those conditions are not in evidence.",
        )
    elif document.get("asserted_revenue_aed") and int(document["asserted_revenue_aed"]) != int(profile.get("stated_revenue_aed") or 0):
        verdict, reason = (
            "disagree",
            "The invoice asserts a different annual revenue from the tenant profile, so the phase for that document stays to verify.",
        )
    else:
        verdict, reason = (
            "agree",
            "The conclusion does not conflict with the tenant profile or the cited passages.",
        )
    return {"item_id": document["_item_id"], "verdict": verdict, "reason": reason, "saw_reasoning": False}
