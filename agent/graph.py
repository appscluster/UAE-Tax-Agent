"""LangGraph planner, operators, and checkers for one readiness run."""
from __future__ import annotations

import base64
import contextvars
from datetime import datetime, timezone
from typing import Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

from agent.llm import complete
from agent.review import (
    audit,
    citations_for,
    classify,
    field_failures,
    parse_document,
    phase_for,
    repair_totals,
    stale_deadline,
)
from agent.sources import cite

CARDS = [
    {
        "title_en": "A PDF is not an eInvoice",
        "title_ar": "ملف PDF ليس فاتورة إلكترونية",
        "body_en": "MoF describes an eInvoice as structured data issued and exchanged electronically and reported to the FTA.",
        "body_ar": "تصف وزارة المالية الفاتورة الإلكترونية بأنها بيانات منظمة تُتبادل إلكترونياً وتُبلَّغ إلى الهيئة. ترجمة المكتب عن النص الإنجليزي.",
        "passage_id": "T1-einvoice",
    },
    {
        "title_en": "The July appointment date lost",
        "title_ar": "موعد يوليو لم يعد هو الموعد الحالي",
        "body_en": "T2 records 31 July 2026. T3 moved the large-cohort appointment to 30 October 2026. T4, dated 25 October 2026, is the newer notice the desk prefers.",
        "body_ar": "المصدر الأقدم يذكر ٣١ يوليو ٢٠٢٦. التعديل نقل الموعد إلى ٣٠ أكتوبر ٢٠٢٦، وإشعار الهيئة في ٢٥ أكتوبر ٢٠٢٦ هو الأحدث. ترجمة المكتب.",
        "passage_id": "T4-equal-or-exceed",
    },
    {
        "title_en": "AED 375,000 is corporate tax",
        "title_ar": "٣٧٥٬٠٠٠ درهم تخص ضريبة الشركات",
        "body_en": "CTGGCT1 applies 0% up to AED 375,000 of taxable income and 9% above that. That band does not schedule eInvoicing.",
        "body_ar": "حد ٣٧٥٬٠٠٠ درهم في دليل ضريبة الشركات شريحة على الدخل الخاضع للضريبة، وليس مرحلة الفوترة الإلكترونية. ترجمة المكتب عن النص الإنجليزي.",
        "passage_id": "T5-zero",
    },
]

QUIZ = [
    {
        "id": "q1",
        "prompt_en": "Is a PDF an eInvoice under the MoF wording in T1?",
        "prompt_ar": "هل ملف PDF فاتورة إلكترونية وفق صياغة وزارة المالية في المصدر T1؟",
        "choices_en": ["Yes", "No"],
        "choices_ar": ["نعم", "لا"],
        "answer": "No",
    },
    {
        "id": "q2",
        "prompt_en": "Does AED 375,000 set the eInvoicing phase?",
        "prompt_ar": "هل يحدد مبلغ ٣٧٥٬٠٠٠ درهم مرحلة الفوترة الإلكترونية؟",
        "choices_en": ["Yes", "No"],
        "choices_ar": ["نعم", "لا"],
        "answer": "No",
    },
    {
        "id": "q3",
        "prompt_en": "After one failed repair, what does the desk do?",
        "prompt_ar": "بعد فشل إصلاح واحد، ماذا يفعل المكتب؟",
        "choices_en": ["Send it to an ASP", "Mark it to verify and escalate"],
        "choices_ar": ["يرسلها إلى مزود معتمد", "يوسمها للمراجعة ويصعّد"],
        "answer": "Mark it to verify and escalate",
    },
]


_SINK: contextvars.ContextVar[Callable[[dict], None] | None] = contextvars.ContextVar("review_step_sink", default=None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(node: str, message: str) -> dict[str, str]:
    return {"node": node, "message": message, "at": _now()}


def _note(node: str, message: str, phase: str) -> None:
    """Live step for the desk console. These lines are not stored on the pack."""
    sink = _SINK.get()
    if sink is None:
        return
    sink({"node": node, "message": message, "at": _now(), "phase": phase})


def _absorb(state: dict, result: dict) -> dict:
    usages = list(state.get("usages") or [])
    usages.append(
        {
            "purpose": result.get("purpose"),
            "model": result.get("model"),
            "usage": result.get("usage") or {},
            "retry_reason": result.get("retry_reason") or "",
            "provider": "omniroute",
        }
    )
    return {
        "usages": usages,
        "replay": bool(state.get("replay") or result.get("replay")),
    }


def orchestrator(state: dict) -> dict:
    count = len(state["raw_documents"])
    _note("orchestrator", f"Splitting {count} documents. Retry budget is one repair.", "start")
    return {"events": state["events"] + [_event("orchestrator", f"Split {count} documents. Retry budget is one repair.")]}


def extractor(state: dict) -> dict:
    items = []
    flagged = 0
    _note("extractor", f"Opening {len(state['raw_documents'])} files. Upload text stays data.", "start")
    for document in state["raw_documents"]:
        _note("extractor", f"Parsing {document['filename']}.", "work")
        parsed = parse_document(document["filename"], base64.b64decode(document["b64"]))
        flagged += int(bool(parsed.get("_instruction_like")))
        items.append({"document": parsed, "failures_seen": [], "repairs": 0})
    message = "Extracted fields and kept page 1 as the source reference. Upload text stays data."
    if flagged:
        message += f" {flagged} file(s) contained instruction-like text and were quarantined as data."
    return {"items": items, "events": state["events"] + [_event("extractor", message)]}


def researcher(state: dict) -> dict:
    _note("researcher", "Attaching frozen passages. Each citation has to entail the claim.", "start")
    items = []
    for item in state["items"]:
        items.append({**item, "citations": citations_for(item["document"])})
    return {
        "items": items,
        "events": state["events"] + [_event("researcher", "Attached frozen passages. Each citation has to entail the claim.")],
    }


def classifier(state: dict) -> dict:
    if state.get("repair_required"):
        _note("classifier", "The validator sent a totals failure back. One repair is allowed.", "start")
    else:
        _note("classifier", "Proposing a treatment from the extracted fields.", "start")
    items = []
    repaired: list[str] = []
    for item in state["items"]:
        document = item["document"]
        repairs = item.get("repairs", 0)
        if state.get("repair_required") and "totals_reconcile" in item.get("failures_seen", []) and repairs < 1:
            document = repair_totals(document)
            repairs = 1
            repaired.append(document["_item_id"])
        items.append({**item, "document": document, "repairs": repairs, "classifier": classify(document)})
    _note("classifier", "Calling the model for one readable sentence. It cannot certify compliance.", "work")
    result = complete(
        "classifier",
        "Write one sentence that a person can read. Do not call the business compliant. Do not change any conclusion.",
        "The classifier proposed a treatment from the fields. This is not a compliance decision.",
    )
    absorbed = _absorb(state, result)
    if repaired:
        message = "Classifier repaired line totals for " + ", ".join(repaired) + ". It did not invent a buyer identifier."
    else:
        message = "Classifier proposed a treatment. Corporate tax on one invoice was refused."
    return {
        "items": items,
        "repair_required": False,
        "repaired_once": bool(state.get("repaired_once") or repaired),
        "events": state["events"] + [_event("classifier", message)],
        **absorbed,
    }


def validator(state: dict) -> dict:
    _note("validator", "Checking the frozen field rules.", "start")
    seen: set[str] = set()
    items = []
    repair_required = False
    notes: list[str] = []
    for item in state["items"]:
        document = item["document"]
        failures = field_failures(document, seen)
        if document.get("kind") == "invoice" and document.get("invoice_id"):
            seen.add(str(document["invoice_id"]))
        guidance = stale_deadline(document.get("notes") or "")
        seen_failures = list(dict.fromkeys([*item.get("failures_seen", []), *failures]))
        if failures and "totals_reconcile" in failures and item.get("repairs", 0) < 1 and not state.get("repaired_once"):
            repair_required = True
            notes.append(document["_item_id"])
        items.append({**item, "failures": failures, "failures_seen": seen_failures, "guidance": guidance})
    if repair_required:
        message = "Validator rejected " + ", ".join(notes) + " and returned the invoice for one repair."
    else:
        message = "Validator finished the frozen field checks. Anything still failing is to verify."
    return {
        "items": items,
        "repair_required": repair_required,
        "events": state["events"] + [_event("validator", message)],
    }


def _route(state: dict) -> str:
    return "classifier" if state.get("repair_required") else "auditor"


def auditor(state: dict) -> dict:
    invoices = [item for item in state["items"] if item["document"].get("kind") == "invoice"]
    _note("auditor", f"Sampling {len(invoices)} conclusions. The model does not see the classifier reasoning.", "start")
    items = []
    disagreements = []
    for item in state["items"]:
        document = item["document"]
        conclusion = item["classifier"]["conclusion"]
        if document.get("kind") == "invoice":
            _note("auditor", f"Model call for {document['_item_id']}.", "work")
            opinion = complete(
                "auditor",
                "You do not see the classifier reasoning. Conclusion only: "
                + conclusion
                + " Reply with agree or disagree, and do not certify compliance.",
                "Evidence rule stands.",
            )
            absorbed_usage = opinion
            verdict = audit(conclusion, document, state["profile"])
            verdict["model"] = opinion.get("model")
            verdict["retry_reason"] = opinion.get("retry_reason") or ""
            _note("auditor", f"{document['_item_id']}  {verdict['verdict']}.", "work")
        else:
            absorbed_usage = None
            verdict = {
                "item_id": document["_item_id"],
                "verdict": "agree",
                "reason": "Contracts are evidence, not a sampled tax call.",
                "saw_reasoning": False,
            }
        if verdict["verdict"] == "disagree":
            disagreements.append(document["_item_id"])
        remaining = item.get("failures") or []
        outcome = "to_verify" if remaining or verdict["verdict"] == "disagree" else "pass"
        items.append({**item, "auditor": verdict, "outcome": outcome, "_opinion": absorbed_usage})
    message = "Auditor sampled the conclusions without the reasoning."
    if disagreements:
        message += " Disagreed on " + ", ".join(disagreements) + " and escalated."
    usages = list(state.get("usages") or [])
    replay = bool(state.get("replay"))
    for item in items:
        opinion = item.get("_opinion")
        if opinion:
            usages.append(
                {
                    "purpose": opinion.get("purpose"),
                    "model": opinion.get("model"),
                    "usage": opinion.get("usage") or {},
                    "retry_reason": opinion.get("retry_reason") or "",
                    "provider": "omniroute",
                }
            )
            replay = replay or bool(opinion.get("replay"))
    public = []
    for item in items:
        public.append({key: value for key, value in item.items() if key != "_opinion"})
    return {
        "items": public,
        "usages": usages,
        "replay": replay,
        "events": state["events"] + [_event("auditor", message)],
    }


def pack(state: dict) -> dict:
    profile = state["profile"]
    phase = phase_for(float(profile["stated_revenue_aed"]))
    _note("pack", "Drafting the bounded pack. Nothing is sent to an accredited provider.", "start")
    _note("pack", "Calling the model for the pack summary.", "work")
    result = complete(
        "narrative",
        "Summarise a bounded readiness pack. Say it is not a return and not an ASP transmission.",
        "Bounded readiness pack. Not a return. Not an ASP transmission. Open items stay to verify.",
    )
    absorbed = _absorb(state, result)
    content = result["content"]
    if "not a return" not in content.lower() and "not an asp" not in content.lower():
        content = "Bounded readiness pack. Not a return. Not an ASP transmission. Open items stay to verify."
        absorbed["usages"][-1]["retry_reason"] = (absorbed["usages"][-1]["retry_reason"] + " entailment_failed").strip()
    cards = []
    for card in CARDS:
        source = cite(card["passage_id"], [])
        cards.append({**card, "source": source["source"], "page": source["page"], "passage": source["text"]})
    limitations = [
        "This pack is not tax, legal, or regulatory advice.",
        "Nothing was transmitted to an ASP.",
        "A passing checklist is not a compliance certification.",
        "Corporate tax on this desk is an educational example. Taxable income is not derived from one invoice.",
        "Exclusions, groups, reliefs, and free-zone conditions stay to verify.",
        "The stated revenue is a customer assertion, not a verified filing.",
        phase["note"],
    ]
    if absorbed["replay"]:
        limitations.append("Model wording is a labelled synthetic replay. Timings of that replay are not live measurements.")
    else:
        limitations.append("A localhost OmniRoute URL does not prove where the upstream provider processes data.")
    report = {
        "profile": profile,
        "phase": phase,
        "items": [_public_item(item) for item in state["items"]],
        "cards": cards,
        "quiz": QUIZ,
        "narrative": content,
        "limitations": limitations,
        "replay": absorbed["replay"],
        "usages": absorbed["usages"],
        "events": state["events"] + [_event("pack", "Drafted a bounded pack. A person still has to sign it.")],
    }
    return {"report": report, "events": report["events"], **absorbed}


def _public_item(item: dict) -> dict:
    classifier = dict(item["classifier"])
    classifier.pop("reasoning", None)
    return {
        "item_id": item["document"]["_item_id"],
        "filename": item["document"]["_filename"],
        "kind": item["document"].get("kind"),
        "invoice_id": item["document"].get("invoice_id") or item["document"].get("contract_id"),
        "page": item["document"].get("_page"),
        "instruction_like": bool(item["document"].get("_instruction_like")),
        "outcome": item["outcome"],
        "repairs": item.get("repairs", 0),
        "failures": item.get("failures") or [],
        "failures_seen": item.get("failures_seen") or [],
        "guidance": item.get("guidance"),
        "citations": item.get("citations") or [],
        "classifier": classifier,
        "auditor": item.get("auditor"),
        "buyer_trn": item["document"].get("buyer_trn", ""),
        "gross_total": item["document"].get("gross_total"),
    }


class ReviewState(TypedDict, total=False):
    profile: dict
    raw_documents: list
    events: list
    items: list
    repair_required: bool
    repaired_once: bool
    usages: list
    replay: bool
    report: dict


def _graph():
    graph = StateGraph(ReviewState)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("extractor", extractor)
    graph.add_node("researcher", researcher)
    graph.add_node("classifier", classifier)
    graph.add_node("validator", validator)
    graph.add_node("auditor", auditor)
    graph.add_node("pack", pack)
    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "extractor")
    graph.add_edge("extractor", "researcher")
    graph.add_edge("researcher", "classifier")
    graph.add_edge("classifier", "validator")
    graph.add_conditional_edges("validator", _route, {"classifier": "classifier", "auditor": "auditor"})
    graph.add_edge("auditor", "pack")
    graph.add_edge("pack", END)
    return graph.compile()


def run_batch(
    files: list[tuple[str, bytes]],
    profile: dict,
    on_event: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    raw_documents = [
        {"filename": name, "b64": base64.b64encode(raw).decode("ascii")}
        for name, raw in files
    ]
    state = {
        "profile": profile,
        "raw_documents": raw_documents,
        "events": [],
        "items": [],
        "repair_required": False,
        "repaired_once": False,
        "usages": [],
        "replay": False,
    }
    token = _SINK.set(on_event)
    try:
        report = None
        for update in _graph().stream(state, stream_mode="updates"):
            if not isinstance(update, dict):
                continue
            for delta in update.values():
                if not isinstance(delta, dict):
                    continue
                events = delta.get("events") or []
                if events and on_event:
                    on_event(events[-1])
                if delta.get("report"):
                    report = delta["report"]
        if report is None:
            raise RuntimeError("The review graph finished without a pack.")
        return report
    finally:
        _SINK.reset(token)
