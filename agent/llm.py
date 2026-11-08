"""Chat completions through the local OmniRoute gateway only."""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any

SYSTEM_PREFIX = (
    "You are a specialist on the Desert Ledger readiness desk. "
    "Use only the passages in the user message. "
    "Do not claim that a business is compliant, that an ASP transmission happened, "
    "or that any saving was measured. "
    "AED 375,000 is a corporate-tax illustration. It does not set the eInvoicing phase. "
    "Keep amounts and identifiers exactly as written."
)

CALLS = 0
_SELECTED = ""
_LOCK = threading.Lock()
_ALIAS_PREFIX = (
    ("github/", "gh/"),
    ("cloudflare-ai/", "cf/"),
    ("ollama-cloud/", "ollamacloud/"),
)


def settings() -> dict[str, Any]:
    return {
        "base_url": os.environ.get("LLM_BASE_URL", "http://127.0.0.1:20128/v1").rstrip("/"),
        "model": os.environ.get("LLM_MODEL", "gh/gpt-5.6-terra"),
        "fallback": os.environ.get("LLM_FALLBACK_MODEL", "gh/gpt-5.6-luna"),
        "timeout": float(os.environ.get("LLM_TIMEOUT_SECONDS", "25")),
    }


def reset_calls() -> None:
    global CALLS
    CALLS = 0


def reset_selection() -> None:
    global _SELECTED
    with _LOCK:
        _SELECTED = ""


def selected_model() -> str:
    with _LOCK:
        return _SELECTED or settings()["model"]


def canonical_model(model_id: str) -> str:
    """Collapse OmniRoute's duplicate provider spellings onto the short id."""
    name = model_id.strip()
    for long, short in _ALIAS_PREFIX:
        if name.startswith(long):
            return short + name[len(long):]
        nested = "/" + long
        if nested in name:
            return name.replace(nested, "/" + short, 1)
    return name


def gateway_model_ids() -> list[str]:
    """Ids from OmniRoute /models. An empty list means the gateway did not answer."""
    if os.environ.get("LLM_MODE", "live") != "live":
        return []
    cfg = settings()
    request = urllib.request.Request(cfg["base_url"] + "/models")
    key = os.environ.get("LLM_API_KEY")
    if key:
        request.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return []
    rows = payload.get("data") if isinstance(payload, dict) else payload
    ids: list[str] = []
    for row in rows or []:
        if isinstance(row, dict) and row.get("id"):
            ids.append(str(row["id"]))
        elif isinstance(row, str) and row.strip():
            ids.append(row.strip())
    return ids


def _deduped(ids: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for model_id in ids:
        seen.setdefault(canonical_model(model_id), None)
    return sorted(seen, key=str.lower)


def catalog() -> dict[str, Any]:
    cfg = settings()
    selected = selected_model()
    fetched = _deduped(gateway_model_ids())
    models: list[str] = []
    for name in (selected, cfg["model"], cfg["fallback"], *fetched):
        if name and name not in models:
            models.append(name)
    return {
        "selected": selected,
        "fallback": cfg["fallback"],
        "models": models,
        "provider": "omniroute",
    }


def choose_model(model: str) -> str:
    """Pin the next live call to one model OmniRoute is offering."""
    global _SELECTED
    chosen = canonical_model(model)
    allowed = set(catalog()["models"])
    if not chosen or chosen not in allowed:
        raise ValueError("That model is not on OmniRoute.")
    with _LOCK:
        _SELECTED = chosen
    return chosen


def chat(messages: list[dict[str, str]], model: str) -> dict[str, Any]:
    """One OpenAI-compatible call. This is the only provider client."""
    global CALLS
    CALLS += 1
    cfg = settings()
    body = {"model": model, "messages": messages, "max_tokens": 700}
    request = urllib.request.Request(
        cfg["base_url"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    key = os.environ.get("LLM_API_KEY")
    if key:
        request.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(request, timeout=cfg["timeout"]) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"omniroute HTTP {exc.code}: {detail}") from exc
    message = (data.get("choices") or [{}])[0].get("message") or {}
    content = message.get("content") or ""
    if not str(content).strip():
        raise RuntimeError("model returned an empty reply")
    return {
        "content": content,
        "model": data.get("model") or model,
        "usage": data.get("usage") or {},
        "provider": "omniroute",
    }


def complete(purpose: str, user: str, canned: str) -> dict[str, Any]:
    """Stable system prefix, volatile user text last. Replay never touches the network."""
    if os.environ.get("LLM_MODE", "live") != "live":
        return {
            "content": canned,
            "model": "replay",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "provider": "omniroute",
            "retry_reason": "labelled_replay",
            "purpose": purpose,
            "replay": True,
        }
    messages = [
        {"role": "system", "content": SYSTEM_PREFIX},
        {"role": "user", "content": user},
    ]
    cfg = settings()
    primary = selected_model()
    fallback = cfg["fallback"] if cfg["fallback"] != primary else cfg["model"]
    try:
        result = chat(messages, primary)
        result.update({"retry_reason": "", "purpose": purpose, "replay": False})
        return result
    except Exception as first_error:
        if not fallback or fallback == primary:
            return {
                "content": canned,
                "model": "replay",
                "usage": {},
                "provider": "omniroute",
                "retry_reason": f"primary_failed:{first_error.__class__.__name__}",
                "purpose": purpose,
                "replay": True,
            }
        try:
            result = chat(messages, fallback)
            result.update(
                {
                    "retry_reason": f"primary_failed:{first_error.__class__.__name__}",
                    "purpose": purpose,
                    "replay": False,
                }
            )
            return result
        except Exception as second_error:
            return {
                "content": canned,
                "model": "replay",
                "usage": {},
                "provider": "omniroute",
                "retry_reason": f"gateway_unreachable:{second_error.__class__.__name__}",
                "purpose": purpose,
                "replay": True,
            }
