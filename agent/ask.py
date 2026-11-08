"""Cited answers, or an abstention when the question asks for advice."""
from __future__ import annotations

from agent.llm import complete
from agent.schemas import AskAnswer, Citation
from agent.sources import cite

ABSTAIN_HINTS = (
    "compliant",
    "certify",
    "file the vat",
    "file the return",
    "how much will we save",
    "guarantee",
    "emaratax",
    "transmit",
    "deduction",
    "exempt",
    "qualifying free zone person",
    "sign the corporate",
    "asp readiness",
)


def _abstain(reason_en: str, reason_ar: str) -> dict:
    answer = AskAnswer(
        abstained=True,
        to_verify=True,
        answer_en=reason_en,
        answer_ar=reason_ar,
        citations=[],
        model="",
        retry_reason="abstained_before_model",
    )
    return answer.model_dump()


def _threshold_ok(text: str) -> bool:
    lowered = text.lower()
    if "compliant" in lowered or "saving" in lowered:
        return False
    if "375" not in text:
        return False
    return "does not" in lowered or "not the einvoicing" in lowered or "not set" in lowered


def _overclaims(text: str) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in ("is compliant", "are compliant", "be compliant")):
        return True
    if "saving" in lowered:
        return True
    return "transmitted to an asp" in lowered and "not " not in lowered


def _focus_items(question: str, trace: dict) -> list[dict]:
    items = list(trace.get("items") or [])
    named = [item for item in items if item.get("item_id") and str(item["item_id"]) in question]
    if named:
        return named
    folded = question.casefold()
    if any(word in folded for word in ("auditor", "disagree")) or any(word in question for word in ("مدقق", "اختلف")):
        disagreed = [item for item in items if (item.get("auditor") or {}).get("verdict") == "disagree"]
        if disagreed:
            return disagreed
    open_items = [item for item in items if item.get("outcome") == "to_verify"]
    return open_items or items


def _item_sentence(item: dict) -> str:
    held = ", ".join(item.get("failures") or []) or "no field rule"
    auditor = item.get("auditor") or {}
    verdict = auditor.get("verdict") or "none"
    reason = " ".join(str(auditor.get("reason") or "").split())[:240]
    conclusion = " ".join(str((item.get("classifier") or {}).get("conclusion") or "").split())[:200]
    if item.get("outcome") == "to_verify":
        action = "Leave this document to verify. Do not sign it as a pass."
    else:
        action = "The field checks passed. A pass on this desk is not a compliance certification."
    detail = f" Classifier: {conclusion}" if conclusion else ""
    heard = f" Auditor reason: {reason}" if reason else ""
    return (
        f"{item.get('item_id')} is {item.get('outcome')}. "
        f"Repairs used: {item.get('repairs') or 0}. Still held: {held}. Auditor: {verdict}.{detail}{heard} {action}"
    )


def _trace_lines(trace: dict, items: list[dict]) -> list[str]:
    lines = [
        "The review graph is orchestrator, extractor, researcher, classifier, validator, auditor, then pack.",
        "LangGraph holds that graph in the process. No graph database was called.",
    ]
    cohort = (trace.get("phase") or {}).get("cohort")
    if cohort:
        lines.append(f"The stated-revenue cohort on this run is {cohort}.")
    lines.extend(_item_sentence(item) for item in items)
    lines.append("Open items stay to verify. This is not a return and not an ASP transmission.")
    return lines


def _trace_ar(items: list[dict]) -> str:
    bits = []
    for item in items:
        mark = "للمراجعة" if item.get("outcome") == "to_verify" else "مرور"
        held = "، ".join(item.get("failures") or [])
        action = " اتركه للمراجعة ولا توقّع عليه كمرور." if item.get("outcome") == "to_verify" else " فحوص الحقول مرّت. المرور هنا ليس شهادة امتثال."
        extra = f" المتبقي {held}." if held else ""
        bits.append(f"{item.get('item_id')}: {mark}.{extra}{action}")
    return "شرح للمراجع قبل التوقيع. " + " ".join(bits) + " ليست ترجمة رسمية."


def _prior_block(prior: list[dict] | None) -> str:
    lines = []
    for turn in (prior or [])[-4:]:
        question = " ".join(str(turn.get("question") or "").split())[:400]
        answer = " ".join(str(turn.get("answer_en") or "").split())[:500]
        if question and answer:
            lines.append(f"Q: {question}\nA: {answer}")
    if not lines:
        return ""
    return "Earlier on this desk:\n" + "\n".join(lines) + "\n\n"


def answer_question(question: str, trace: dict | None = None, prior: list[dict] | None = None) -> dict:
    folded = question.casefold()
    if any(hint in folded for hint in ABSTAIN_HINTS):
        return _abstain(
            "This desk will not answer that. It does not certify readiness, file a return, or measure savings.",
            "لن يجيب المكتب عن هذا. لا يشهد بالجاهزية، ولا يقدّم إقراراً، ولا يقيس وفراً.",
        )
    if "375" in folded or "٣٧٥" in question:
        citations = [
            cite("T5-zero", ["375,000", "0%"]),
            cite("T5-nine", ["375,000", "9%"]),
            cite("T4-equal-or-exceed", ["AED 50 million"]),
        ]
        canned = (
            "AED 375,000 does not set the eInvoicing phase. "
            "CTGGCT1 applies 0% to the portion of taxable income not exceeding AED 375,000 and 9% above that. "
            "The eInvoicing notice in T4 uses an AED 50 million revenue boundary. "
            "One invoice is not taxable income."
        )
        passages = "\n".join(item["text"] for item in citations)
        result = complete(
            "ask",
            f"Question:\n{question}\n\nPassages:\n{passages}\n\nAnswer in English using only these passages.",
            canned,
        )
        content = result["content"] if _threshold_ok(result["content"]) else canned
        retry = result.get("retry_reason") or ""
        if content == canned and result["content"] != canned:
            retry = (retry + " entailment_failed").strip()
        arabic = (
            "مبلغ ٣٧٥٬٠٠٠ درهم لا يحدد مرحلة الفوترة الإلكترونية. "
            "دليل ضريبة الشركات يضع ٠٪ على شريحة الدخل الخاضع للضريبة حتى هذا المبلغ و٩٪ فوقه. "
            "إشعار الفوترة الإلكترونية يربط المرحلة بحد ٥٠ مليون درهم. "
            "فاتورة واحدة ليست دخلاً خاضعاً للضريبة. ترجمة المكتب عن النص الإنجليزي، وليست ترجمة رسمية."
        )
        answer = AskAnswer(
            abstained=False,
            to_verify=False,
            answer_en=content,
            answer_ar=arabic,
            citations=[Citation(**item) for item in citations],
            model=result.get("model") or "",
            retry_reason=retry,
        )
        return answer.model_dump()
    if not trace or not trace.get("items"):
        return _abstain(
            "No review is loaded for this company. Run the agents, then ask about that trace.",
            "لا مراجعة محمّلة لهذه الشركة. شغّل الوكلاء ثم اسأل عن أثرها.",
        )
    focus = _focus_items(question, trace)
    brief = "\n".join(_trace_lines(trace, focus))
    canned = "\n\n".join(_item_sentence(item) for item in focus)
    result = complete(
        "ask",
        _prior_block(prior)
        + "Question:\n"
        + question
        + "\n\nReview record:\n"
        + brief
        + "\n\nAnswer the human approver in two to five plain English sentences, using only this review record. "
        + "Name the document, the outcome, and the rule still held. "
        + "If the outcome is to_verify, say to leave it unsigned as a pass. "
        + "No markdown, no table, and no asterisks. Do not certify compliance.",
        canned,
    )
    content = result["content"].replace("**", "").replace("`", "")
    retry = result.get("retry_reason") or ""
    named = [str(item.get("item_id")) for item in focus if item.get("item_id")]
    if _overclaims(content) or (named and not any(item_id in content for item_id in named)):
        content = canned
        retry = (retry + " entailment_failed").strip()
    answer = AskAnswer(
        abstained=False,
        to_verify=any(item.get("outcome") == "to_verify" for item in focus),
        answer_en=content,
        answer_ar=_trace_ar(focus),
        citations=[],
        model=result.get("model") or "",
        retry_reason=retry,
    )
    return answer.model_dump()
