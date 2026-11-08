"""Residency gate. Unverified inference accepts synthetic content only."""
from __future__ import annotations

import os
import urllib.error
import urllib.request

from agent.llm import settings


class ResidencyBlocked(Exception):
    pass


def verified() -> bool:
    return os.environ.get("RESIDENCY_VERIFIED", "false").lower() == "true"


def assert_inference_allowed(synthetic: bool) -> None:
    if synthetic or verified():
        return
    raise ResidencyBlocked(
        "Inference residency is not verified. Only synthetic content can be sent to the model."
    )


def gateway_reachable() -> bool:
    """True when the local OmniRoute models endpoint answers. Replay skips the network."""
    if os.environ.get("LLM_MODE", "live") != "live":
        return False
    cfg = settings()
    request = urllib.request.Request(cfg["base_url"].rstrip("/") + "/models")
    key = os.environ.get("LLM_API_KEY")
    if key:
        request.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def record() -> dict:
    cfg = settings()
    return {
        "storage": os.environ.get("DB_PATH", "backend/var/readiness.db"),
        "logs": "Container stdout on this deployment. Logs are not shipped to another sink.",
        "backups": os.environ.get("BACKUP_DIR", "backend/var/backup"),
        "inference_base_url": cfg["base_url"],
        "models": [cfg["model"], cfg["fallback"]],
        "provider": "omniroute",
        "gateway_reachable": gateway_reachable(),
        "residency_verified": verified(),
        "retention_days": int(os.environ.get("RETENTION_DAYS", "30")),
        "note": "A localhost OmniRoute URL does not prove where an upstream provider processes data.",
    }
