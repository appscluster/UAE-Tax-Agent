"""Encrypted tenant store. Cross-tenant reads stop before a lookup returns data."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import FunctionType

from cryptography.fernet import Fernet


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fernet_from_secret(secret: str) -> Fernet:
    try:
        return Fernet(secret.encode())
    except Exception:
        digest = hashlib.sha256(secret.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def _serialized(fn):
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)

    return wrapped


def _mark(item: dict) -> dict:
    failures = item.get("failures") or []
    auditor = item.get("auditor") or {}
    return {
        "item_id": item.get("item_id") or "",
        "outcome": item.get("outcome") or "",
        "held": failures[0] if failures else "",
        "auditor": auditor.get("verdict") or "",
    }


class Store:
    def __init__(self, path: str | Path, secret: str | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = secret if secret is not None else os.environ.get("TENANT_VOLUME_KEY", "")
        if not key:
            raise RuntimeError("TENANT_VOLUME_KEY is required")
        self._fernet = fernet_from_secret(key)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              filename TEXT NOT NULL,
              sha256 TEXT NOT NULL,
              synthetic INTEGER NOT NULL,
              payload BLOB NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              status TEXT NOT NULL,
              document_ids TEXT NOT NULL,
              document_hashes TEXT NOT NULL,
              result_enc BLOB,
              replay INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS companies (
              tenant_id TEXT PRIMARY KEY,
              legal_name TEXT NOT NULL,
              trn TEXT NOT NULL,
              seat TEXT NOT NULL,
              free_zone INTEGER NOT NULL,
              stated_revenue_aed REAL NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant_id TEXT,
              run_id TEXT,
              actor TEXT,
              action TEXT,
              detail TEXT,
              created_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()
        self._lock = threading.RLock()
        for name, fn in list(Store.__dict__.items()):
            if name.startswith("_") or not isinstance(fn, FunctionType):
                continue
            setattr(self, name, _serialized(fn).__get__(self, Store))

    def close(self) -> None:
        self._conn.close()

    def _encrypt(self, payload: bytes) -> bytes:
        return self._fernet.encrypt(payload)

    def _decrypt(self, payload: bytes) -> bytes:
        return self._fernet.decrypt(payload)

    def put_document(self, doc_id: str, tenant_id: str, filename: str, raw: bytes, synthetic: bool, created_at: str | None = None) -> dict:
        digest = hashlib.sha256(raw).hexdigest()
        self._conn.execute(
            "INSERT INTO documents (id, tenant_id, filename, sha256, synthetic, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, tenant_id, filename, digest, int(synthetic), self._encrypt(raw), created_at or _now()),
        )
        self._conn.commit()
        self.audit(tenant_id, "", "system", "document_stored", filename)
        return {"id": doc_id, "tenant_id": tenant_id, "filename": filename, "sha256": digest, "synthetic": synthetic}

    def get_document(self, tenant_id: str, doc_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            return None
        if row["tenant_id"] != tenant_id:
            self.audit(tenant_id, "", "system", "cross_tenant_blocked", doc_id)
            return None
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "filename": row["filename"],
            "sha256": row["sha256"],
            "synthetic": bool(row["synthetic"]),
            "raw": self._decrypt(row["payload"]),
            "created_at": row["created_at"],
        }

    def list_documents(self, tenant_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, filename, sha256, synthetic, created_at FROM documents WHERE tenant_id = ? ORDER BY filename",
            (tenant_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def hashes_for(self, tenant_id: str, doc_ids: list[str]) -> list[dict]:
        found = []
        for doc_id in doc_ids:
            document = self.get_document(tenant_id, doc_id)
            if document is None:
                raise KeyError(doc_id)
            found.append({"id": doc_id, "sha256": document["sha256"]})
        return found

    def save_run(self, run_id: str, tenant_id: str, status: str, doc_ids: list[str], hashes: list[dict], result: dict) -> None:
        self._conn.execute(
            """
            INSERT INTO runs (id, tenant_id, status, document_ids, document_hashes, result_enc, replay, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                tenant_id,
                status,
                json.dumps(doc_ids),
                json.dumps(hashes),
                self._encrypt(json.dumps(result).encode()),
                int(bool(result.get("replay"))),
                _now(),
            ),
        )
        self._conn.commit()

    def latest_run(self, tenant_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id FROM runs WHERE tenant_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (tenant_id,),
        ).fetchone()
        if row is None:
            return None
        return self.get_run(tenant_id, row["id"])

    def get_run(self, tenant_id: str, run_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        if row["tenant_id"] != tenant_id:
            self.audit(tenant_id, run_id, "system", "cross_tenant_blocked", run_id)
            return None
        result = json.loads(self._decrypt(row["result_enc"]).decode()) if row["result_enc"] else None
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "status": row["status"],
            "document_ids": json.loads(row["document_ids"]),
            "document_hashes": json.loads(row["document_hashes"]),
            "result": result,
            "replay": bool(row["replay"]),
            "created_at": row["created_at"],
        }

    def set_run_status(self, run_id: str, status: str, result: dict) -> None:
        self._conn.execute(
            "UPDATE runs SET status = ?, result_enc = ?, replay = ? WHERE id = ?",
            (status, self._encrypt(json.dumps(result).encode()), int(bool(result.get("replay"))), run_id),
        )
        self._conn.commit()

    def audit(self, tenant_id: str, run_id: str, actor: str, action: str, detail: str) -> None:
        self._conn.execute(
            "INSERT INTO audit (tenant_id, run_id, actor, action, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, run_id, actor, action, detail, _now()),
        )
        self._conn.commit()

    def audits_for(self, tenant_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, tenant_id, run_id, actor, action, detail, created_at FROM audit WHERE tenant_id = ? ORDER BY id",
            (tenant_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def enforce_retention(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self._conn.execute("SELECT id, tenant_id FROM documents WHERE created_at < ?", (cutoff,)).fetchall()
        for row in rows:
            self.audit(row["tenant_id"], "", "system", "retention_deleted", row["id"])
        self._conn.execute("DELETE FROM documents WHERE created_at < ?", (cutoff,))
        self._conn.commit()
        return len(rows)

    def ensure_company(self, profile: dict) -> dict:
        existing = self.get_company(profile["tenant_id"])
        if existing:
            return existing
        self._conn.execute(
            """
            INSERT INTO companies (tenant_id, legal_name, trn, seat, free_zone, stated_revenue_aed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile["tenant_id"],
                profile["legal_name"],
                profile["trn"],
                "free_zone" if profile.get("free_zone") else profile.get("seat") or "mainland",
                int(bool(profile.get("free_zone"))),
                float(profile["stated_revenue_aed"]),
                _now(),
            ),
        )
        self._conn.commit()
        self.audit(profile["tenant_id"], "", "system", "company_seeded", profile["legal_name"])
        return self.get_company(profile["tenant_id"])

    def get_company(self, tenant_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM companies WHERE tenant_id = ?", (tenant_id,)).fetchone()
        if row is None:
            return None
        return self._company(row)

    def list_companies(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM companies ORDER BY created_at, legal_name").fetchall()
        return [self._company(row) for row in rows]

    def save_company(self, tenant_id: str, legal_name: str, trn: str, seat: str, revenue: float) -> dict:
        free_zone = seat == "free_zone"
        stored_seat = "free zone" if free_zone else "mainland"
        existing = self.get_company(tenant_id)
        if existing:
            self._conn.execute(
                """
                UPDATE companies
                SET legal_name = ?, seat = ?, free_zone = ?, stated_revenue_aed = ?
                WHERE tenant_id = ?
                """,
                (legal_name, stored_seat, int(free_zone), float(revenue), tenant_id),
            )
            self.audit(tenant_id, "", "approver", "company_edited", legal_name)
        else:
            self._conn.execute(
                """
                INSERT INTO companies (tenant_id, legal_name, trn, seat, free_zone, stated_revenue_aed, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, legal_name, trn, stored_seat, int(free_zone), float(revenue), _now()),
            )
            self.audit(tenant_id, "", "approver", "company_added", legal_name)
        self._conn.commit()
        return self.get_company(tenant_id)

    def delete_company(self, tenant_id: str, actor: str) -> dict:
        documents = self.delete_tenant_documents(tenant_id, actor)
        runs = self._conn.execute("SELECT COUNT(*) AS n FROM runs WHERE tenant_id = ?", (tenant_id,)).fetchone()["n"]
        self._conn.execute("DELETE FROM runs WHERE tenant_id = ?", (tenant_id,))
        self._conn.execute("DELETE FROM companies WHERE tenant_id = ?", (tenant_id,))
        self._conn.commit()
        self.audit(tenant_id, "", actor, "company_removed", tenant_id)
        return {"tenant_id": tenant_id, "documents_removed": documents, "runs_removed": int(runs)}

    def dashboard(self) -> dict:
        roles = ["orchestrator", "extractor", "researcher", "classifier", "validator", "auditor", "pack"]
        rows = []
        for company in self.list_companies():
            documents = self.list_documents(company["tenant_id"])
            latest = self.latest_run(company["tenant_id"])
            result = (latest or {}).get("result") or {}
            items = result.get("items") or []
            events = result.get("events") or []
            last_by_role = {}
            for event in events:
                last_by_role[event.get("node")] = event.get("message") or ""
            phase = result.get("phase") or {}
            rows.append({
                **company,
                "documents": len(documents),
                "document_ids": [item["id"] for item in documents],
                "run_id": latest["id"] if latest else "",
                "run_status": latest["status"] if latest else "",
                "replay": bool(latest["replay"]) if latest else False,
                "created_at_run": latest["created_at"] if latest else "",
                "pass_count": sum(1 for item in items if item.get("outcome") == "pass"),
                "verify_count": sum(1 for item in items if item.get("outcome") == "to_verify"),
                "phase_cohort": phase.get("cohort") or "",
                "phase_status": phase.get("status") or "",
                "marks": [_mark(item) for item in items],
                "agents": [{"node": role, "message": last_by_role.get(role) or "Idle. This role runs only inside a batch."} for role in roles],
            })
        return {
            "companies": len(rows),
            "documents": sum(row["documents"] for row in rows),
            "open_items": sum(row["verify_count"] for row in rows),
            "awaiting": sum(1 for row in rows if row["run_status"] == "awaiting_approval"),
            "rows": rows,
        }

    def _company(self, row: sqlite3.Row) -> dict:
        return {
            "tenant_id": row["tenant_id"],
            "legal_name": row["legal_name"],
            "trn": row["trn"],
            "seat": row["seat"],
            "free_zone": bool(row["free_zone"]),
            "stated_revenue_aed": row["stated_revenue_aed"],
            "revenue_is": "customer_assertion",
            "research_date": "2026-11-07",
            "currency": "AED",
            "created_at": row["created_at"],
        }

    def delete_tenant_documents(self, tenant_id: str, actor: str) -> int:
        count = self._conn.execute("SELECT COUNT(*) AS n FROM documents WHERE tenant_id = ?", (tenant_id,)).fetchone()["n"]
        self._conn.execute("DELETE FROM documents WHERE tenant_id = ?", (tenant_id,))
        self._conn.commit()
        self.audit(tenant_id, "", actor, "tenant_documents_deleted", str(count))
        return int(count)

    def backup_to(self, directory: str | Path) -> str:
        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)
        self._conn.commit()
        target = target_dir / "readiness.db"
        # The copy is the encrypted database file. The key stays outside the volume.
        shutil.copy2(self.path, target)
        return str(target)
