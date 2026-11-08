"""Readiness desk API. Model calls stay behind the residency gate."""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from agent.ask import answer_question
from agent.graph import run_batch
from agent.llm import catalog, choose_model
from agent.sources import data_dir
from backend.residency import ResidencyBlocked, assert_inference_allowed, record
from backend.store import Store

@asynccontextmanager
async def lifespan(_app: FastAPI):
    store = get_store()
    store.enforce_retention(int(os.environ.get("RETENTION_DAYS", "30")))
    store.backup_to(os.environ.get("BACKUP_DIR", "backend/var/backup"))
    yield
    reset_store()


app = FastAPI(title="UAE tax readiness desk", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STORE: Store | None = None
DEMO_FILES = [
    "DL-INV-1001.json",
    "DL-INV-1002.pdf",
    "DL-INV-1003.json",
    "DL-INV-1004.json",
    "DL-INV-1005.json",
    "DL-INV-1006.json",
    "CTR-DL-01.json",
    "CTR-DL-02.json",
]


def reset_store() -> None:
    global _STORE
    if _STORE is not None:
        _STORE.close()
        _STORE = None


def get_store() -> Store:
    global _STORE
    path = os.environ.get("DB_PATH", "backend/var/readiness.db")
    if _STORE is None or str(_STORE.path) != str(Path(path)):
        if _STORE is not None:
            _STORE.close()
        _STORE = Store(path)
        _STORE.ensure_company(_profile())
    return _STORE


class CompanyWrite(BaseModel):
    legal_name: str = Field(min_length=2, max_length=80)
    seat: str
    stated_revenue_aed: float = Field(ge=0, le=1_000_000_000_000)


class RunRequest(BaseModel):
    tenant_id: str
    document_ids: list[str] = Field(min_length=1)


class DecisionRequest(BaseModel):
    tenant_id: str
    action: str
    actor: str
    note: str = ""


class PriorTurn(BaseModel):
    question: str = Field(default="", max_length=500)
    answer_en: str = Field(default="", max_length=800)


class ModelChoice(BaseModel):
    model: str = Field(min_length=1, max_length=160)


class AskRequest(BaseModel):
    tenant_id: str
    question: str
    synthetic: bool = True
    run_id: str = ""
    prior: list[PriorTurn] = Field(default_factory=list, max_length=4)


def _profile() -> dict:
    return json.loads((data_dir() / "fixtures" / "profile.json").read_text(encoding="utf-8"))


def _company_or_404(tenant_id: str) -> dict:
    company = get_store().get_company(tenant_id)
    if company is None:
        raise HTTPException(404, "No company with that id")
    return company


def _check_seat(seat: str) -> str:
    if seat not in {"mainland", "free_zone"}:
        raise HTTPException(400, "Seat must be mainland or free_zone")
    return seat


def _guard(synthetic: bool) -> None:
    try:
        assert_inference_allowed(synthetic)
    except ResidencyBlocked as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "residency_verified": record()["residency_verified"]}


@app.get("/api/residency")
def residency() -> dict:
    return record()


@app.get("/api/models")
def models() -> dict:
    return catalog()


@app.put("/api/models")
def select_model(body: ModelChoice) -> dict:
    try:
        choose_model(body.model)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return catalog()


@app.get("/api/tenant")
def tenant(tenant_id: str = "") -> dict:
    if not tenant_id:
        tenant_id = _profile()["tenant_id"]
    return _company_or_404(tenant_id)


@app.get("/api/dashboard")
def dashboard() -> dict:
    return get_store().dashboard()


@app.get("/api/companies")
def companies() -> dict:
    return {"companies": get_store().list_companies()}


@app.post("/api/companies")
def add_company(body: CompanyWrite) -> dict:
    seat = _check_seat(body.seat)
    slug = re.sub(r"[^a-z0-9]+", "_", body.legal_name.casefold()).strip("_")[:32] or "company"
    tenant_id = f"tenant_{slug}"
    store = get_store()
    if store.get_company(tenant_id):
        tenant_id = f"{tenant_id}_{uuid.uuid4().hex[:6]}"
    trn = f"SYNTHETIC_{slug.upper()}_NOT_VALID"
    return store.save_company(tenant_id, body.legal_name.strip(), trn, seat, body.stated_revenue_aed)


@app.put("/api/companies/{tenant_id}")
def edit_company(tenant_id: str, body: CompanyWrite) -> dict:
    _company_or_404(tenant_id)
    seat = _check_seat(body.seat)
    current = get_store().get_company(tenant_id)
    return get_store().save_company(tenant_id, body.legal_name.strip(), current["trn"], seat, body.stated_revenue_aed)


@app.delete("/api/companies/{tenant_id}")
def remove_company(tenant_id: str, actor: str = "approver") -> dict:
    _company_or_404(tenant_id)
    return get_store().delete_company(tenant_id, actor)


@app.post("/api/companies/{tenant_id}/process")
def process_company(tenant_id: str, request: Request, reuse: bool = False) -> dict:
    company = _company_or_404(tenant_id)
    store = get_store()
    if reuse:
        latest = store.latest_run(tenant_id)
        if latest is None:
            raise HTTPException(409, "No batch to re-run. Run the agents once first.")
        document_ids = latest["document_ids"]
    else:
        documents = store.list_documents(tenant_id)
        if not documents and tenant_id == _profile()["tenant_id"]:
            folder = data_dir() / "fixtures"
            for name in DEMO_FILES:
                raw = (folder / name).read_bytes()
                store.put_document(str(uuid.uuid4()), tenant_id, name, raw, True)
            documents = store.list_documents(tenant_id)
        if not documents:
            raise HTTPException(409, "Upload a synthetic file before running the agents.")
        document_ids = _newest_per_filename(documents)
    return start_run(RunRequest(tenant_id=company["tenant_id"], document_ids=document_ids), request)


@app.post("/api/documents")
async def upload(tenant_id: str = Form(...), synthetic: bool = Form(...), file: UploadFile = File(...)) -> dict:
    _guard(synthetic)
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload")
    if get_store().get_company(tenant_id) is None:
        raise HTTPException(404, "No company with that id")
    stored = get_store().put_document(str(uuid.uuid4()), tenant_id, file.filename or "upload.bin", raw, synthetic)
    stored["residency_verified"] = record()["residency_verified"]
    return stored


@app.post("/api/demo/load")
def load_demo() -> dict:
    profile = _profile()
    store = get_store()
    folder = data_dir() / "fixtures"
    existing = {item["filename"]: item for item in store.list_documents(profile["tenant_id"])}
    documents = []
    for name in DEMO_FILES:
        if name in existing:
            documents.append(existing[name])
            continue
        raw = (folder / name).read_bytes()
        documents.append(store.put_document(str(uuid.uuid4()), profile["tenant_id"], name, raw, True))
    return {"tenant_id": profile["tenant_id"], "documents": documents}


def _newest_per_filename(documents: list[dict]) -> list[str]:
    newest: dict[str, dict] = {}
    for item in documents:
        current = newest.get(item["filename"])
        if current is None or item.get("created_at", "") >= current.get("created_at", ""):
            newest[item["filename"]] = item
    return [item["id"] for item in newest.values()]


def _wants_stream(request: Request) -> bool:
    return "text/event-stream" in request.headers.get("accept", "")


def _batch_for(tenant_id: str, document_ids: list[str]) -> tuple[list, list, dict]:
    store = get_store()
    files = []
    synthetic_flags = []
    for doc_id in document_ids:
        document = store.get_document(tenant_id, doc_id)
        if document is None:
            raise HTTPException(404, "Document is not in this tenant")
        synthetic_flags.append(document["synthetic"])
        files.append((document["filename"], document["raw"]))
    if not all(synthetic_flags):
        _guard(False)
    hashes = store.hashes_for(tenant_id, document_ids)
    company = store.get_company(tenant_id) or (_profile() if tenant_id == _profile()["tenant_id"] else None)
    if company is None:
        raise HTTPException(404, "No company with that id")
    return files, hashes, company


def _finish_run(tenant_id: str, document_ids: list[str], hashes: list[dict], report: dict) -> dict:
    store = get_store()
    run_id = str(uuid.uuid4())
    store.save_run(run_id, tenant_id, "awaiting_approval", document_ids, hashes, report)
    store.audit(tenant_id, run_id, "system", "run_finished", report["items"][0]["item_id"] if report["items"] else "")
    return {"run_id": run_id, "status": "awaiting_approval", "replay": report["replay"]}


async def _stream_batch(tenant_id: str, document_ids: list[str], files: list, hashes: list, company: dict):
    """Send the first byte immediately, then each agent step as that step happens."""
    current = {"node": "orchestrator", "message": "Starting the batch."}
    yield {
        "event": "accepted",
        "data": json.dumps(
            {
                "status": "running",
                "message": "Accepted. The orchestrator is starting. Each role writes a line when it starts work and when it finishes.",
            }
        ),
    }
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def publish(kind: str, payload: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))

    def on_event(event: dict) -> None:
        current["node"] = event.get("node") or current["node"]
        current["message"] = event.get("message") or current["message"]
        publish("node", event)

    def work() -> None:
        try:
            report = run_batch(files, company, on_event=on_event)
            publish("done", _finish_run(tenant_id, document_ids, hashes, report))
        except Exception as exc:
            publish("error", {"detail": str(exc)[:300]})

    threading.Thread(target=work, name="review-batch", daemon=True).start()
    while True:
        try:
            kind, payload = await asyncio.wait_for(queue.get(), timeout=2.5)
        except asyncio.TimeoutError:
            yield {
                "event": "tick",
                "data": json.dumps(
                    {
                        "node": current["node"],
                        "message": f"Still working. {current['message']}",
                        "at": "",
                        "phase": "tick",
                    }
                ),
            }
            continue
        yield {"event": kind, "data": json.dumps(payload)}
        if kind in {"done", "error"}:
            return


@app.post("/api/runs")
def start_run(body: RunRequest, request: Request) -> dict:
    files, hashes, company = _batch_for(body.tenant_id, body.document_ids)
    if _wants_stream(request):
        return EventSourceResponse(
            _stream_batch(body.tenant_id, body.document_ids, files, hashes, company),
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    report = run_batch(files, company)
    return _finish_run(body.tenant_id, body.document_ids, hashes, report)


@app.get("/api/runs/latest")
def latest_run(tenant_id: str) -> dict:
    run = get_store().latest_run(tenant_id)
    if run is None:
        raise HTTPException(404, "No run for this tenant")
    body = dict(run["result"])
    body["run_id"] = run["id"]
    body["status"] = run["status"]
    body["tenant_id"] = run["tenant_id"]
    return body


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str, tenant_id: str):
    run = get_store().get_run(tenant_id, run_id)
    if run is None:
        raise HTTPException(404, "Run is not in this tenant")

    async def generate():
        for event in run["result"]["events"]:
            yield {"event": "node", "data": json.dumps(event)}
            await asyncio.sleep(0.01)
        yield {
            "event": "done",
            "data": json.dumps({"status": run["status"], "replay": run["replay"], "run_id": run_id}),
        }

    return EventSourceResponse(generate())


@app.post("/api/runs/{run_id}/decisions")
def decide(run_id: str, body: DecisionRequest) -> dict:
    if body.action not in {"approve", "reject", "escalate"}:
        raise HTTPException(400, "Action must be approve, reject, or escalate")
    store = get_store()
    run = store.get_run(body.tenant_id, run_id)
    if run is None:
        raise HTTPException(404, "Run is not in this tenant")
    if run["status"] != "awaiting_approval":
        raise HTTPException(409, "This run is no longer awaiting approval")
    current = store.hashes_for(body.tenant_id, run["document_ids"])
    if current != run["document_hashes"]:
        raise HTTPException(409, "Document hash changed. Approval stopped.")
    status = "approved_bounded" if body.action == "approve" else body.action
    result = run["result"]
    result["approval"] = {"action": body.action, "actor": body.actor, "note": body.note}
    result["status"] = status
    store.set_run_status(run_id, status, result)
    store.audit(body.tenant_id, run_id, body.actor, body.action, body.note[:240])
    return {"run_id": run_id, "status": status}


@app.get("/api/reports/{run_id}")
def report(run_id: str, tenant_id: str) -> dict:
    run = get_store().get_run(tenant_id, run_id)
    if run is None:
        raise HTTPException(404, "Run is not in this tenant")
    body = dict(run["result"])
    body["run_id"] = run_id
    body["status"] = run["status"]
    body["tenant_id"] = run["tenant_id"]
    return body


@app.post("/api/ask")
def ask(body: AskRequest) -> dict:
    _guard(body.synthetic)
    store = get_store()
    if store.get_company(body.tenant_id) is None:
        store.audit(body.tenant_id, "", "system", "cross_tenant_blocked", "ask")
        raise HTTPException(404, "Question refused before retrieval")
    run = store.get_run(body.tenant_id, body.run_id) if body.run_id else store.latest_run(body.tenant_id)
    trace = run["result"] if run and run.get("result") else None
    prior = [turn.model_dump() for turn in body.prior]
    return answer_question(body.question, trace, prior)


@app.delete("/api/tenants/{tenant_id}")
def delete_tenant(tenant_id: str, actor: str = "approver") -> dict:
    removed = get_store().delete_tenant_documents(tenant_id, actor)
    return {"tenant_id": tenant_id, "documents_removed": removed}


@app.post("/api/admin/backup")
def backup() -> dict:
    path = get_store().backup_to(os.environ.get("BACKUP_DIR", "backend/var/backup"))
    return {"backup": path}
