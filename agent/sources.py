"""Versioned source register. Retrieval is over frozen passages only."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("DATA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "data"


@lru_cache(maxsize=1)
def register() -> dict:
    return json.loads((data_dir() / "sources" / "register.json").read_text(encoding="utf-8"))


def passages() -> dict[str, dict]:
    return {item["id"]: item for item in register()["passages"]}


def passage(passage_id: str) -> dict:
    found = passages().get(passage_id)
    if not found:
        raise KeyError(passage_id)
    return found


def entails(text: str, tokens: list[str]) -> bool:
    return all(token in text for token in tokens)


def cite(passage_id: str, tokens: list[str]) -> dict:
    item = passage(passage_id)
    if not entails(item["text"], tokens):
        raise ValueError(f"{passage_id} does not entail {tokens}")
    return {
        "passage_id": item["id"],
        "source": item["source"],
        "page": item["page"],
        "text": item["text"],
        "historical": item["historical"],
    }
