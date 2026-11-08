import { lazy, Suspense, useEffect, useRef, useState } from "react";
import CompanyPick from "./CompanyPick";
import Dashboard from "./Dashboard";
import { heldPhrase } from "./marks";

const Explanation = lazy(() => import("./Explanation"));
const MEMORY_KEY = "desert-ledger-memory";

function memoryKey(companyId) {
  return `${MEMORY_KEY}:${companyId}`;
}

function readMemory(companyId = "tenant_desert_ledger") {
  try {
    const raw = localStorage.getItem(memoryKey(companyId))
      || (companyId === "tenant_desert_ledger" ? localStorage.getItem(MEMORY_KEY) : "")
      || "{}";
    const parsed = JSON.parse(raw);
    const answer = parsed.answer || null;
    const turns = Array.isArray(parsed.turns) ? parsed.turns : (answer ? [answer] : []);
    return {
      answer,
      turns,
      picks: parsed.picks && typeof parsed.picks === "object" ? parsed.picks : {},
    };
  } catch {
    return { answer: null, turns: [], picks: {} };
  }
}

function promptsFor(report, t) {
  const prompts = [];
  const open = (report?.items || []).filter((item) => item.outcome === "to_verify");
  for (const item of open.slice(0, 2)) {
    const rule = item.failures?.[0];
    prompts.push(rule ? t.askHeld.replace("{id}", item.item_id).replace("{rule}", rule) : t.askOpen.replace("{id}", item.item_id));
  }
  const disagreed = open.filter((item) => item.auditor?.verdict === "disagree").map((item) => item.item_id);
  if (disagreed.length) prompts.push(t.askAuditor.replace("{ids}", disagreed.join(", ")));
  prompts.push(t.askCite);
  return prompts.slice(0, 4);
}

const TOOL_FOR = {
  extractor: "parse_document",
  researcher: "citations_for",
  classifier: "repair_totals",
  validator: "field_failures",
  auditor: "audit",
  pack: "phase_for",
};

function tokenCount(usage, key) {
  const value = usage?.usage?.[key];
  return value === undefined || value === null ? "—" : value;
}

const STAGES = ["orchestrator", "extractor", "researcher", "classifier", "validator", "auditor", "pack"];
const MODEL_GROUP_ORDER = ["gh", "auto"];

function modelGroups(models) {
  const groups = new Map();
  for (const id of models || []) {
    const slash = id.indexOf("/");
    const name = slash === -1 ? "other" : id.slice(0, slash);
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(id);
  }
  const names = [...groups.keys()].sort((left, right) => {
    const leftRank = MODEL_GROUP_ORDER.indexOf(left);
    const rightRank = MODEL_GROUP_ORDER.indexOf(right);
    if (leftRank !== -1 || rightRank !== -1) return (leftRank === -1 ? 99 : leftRank) - (rightRank === -1 ? 99 : rightRank);
    return left.localeCompare(right);
  });
  return names.map((name) => ({ name, models: groups.get(name) }));
}

function toolFor(event) {
  if (event.phase === "start" || event.phase === "work" || event.phase === "tick") return "";
  if (event.node === "classifier") return /repaired/i.test(event.message) ? "repair_totals" : "";
  return TOOL_FOR[event.node] || "";
}

function pushStep(lines, event) {
  const kind = event.phase === "tick" ? "desk" : "agent";
  lines.push({ kind, at: event.at, text: `${event.node}  ${event.message}` });
  const tool = toolFor(event);
  if (tool) lines.push({ kind: "tool", at: event.at, text: `${tool}  called by ${event.node}` });
}

function runProgress(feed) {
  if (!feed) return null;
  const finished = new Set();
  let active = false;
  for (const event of feed.events) {
    if (event.phase === "tick") continue;
    if (event.phase === "start" || event.phase === "work") active = true;
    else if (STAGES.includes(event.node)) {
      finished.add(event.node);
      active = false;
    }
  }
  const ratio = Math.max(feed.events.length ? 0.08 : 0.06, finished.size / STAGES.length);
  const last = [...feed.events].reverse().find((event) => event.phase !== "tick");
  const label = feed.note || (last ? `${last.node} — ${last.message}` : "Waiting for the API to accept the run.");
  return { ratio: Math.min(ratio, feed.events.length ? 0.96 : 0.12), label, live: active || finished.size < STAGES.length };
}

function consumeEventFrames(buffer, onEvent) {
  const chunks = buffer.split("\n\n");
  const rest = chunks.pop() || "";
  for (const chunk of chunks) {
    let name = "message";
    const data = [];
    for (const line of chunk.split("\n")) {
      if (line.startsWith("event:")) name = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trim());
    }
    if (!data.length) continue;
    onEvent(name, JSON.parse(data.join("\n")));
  }
  return rest;
}

async function readEventStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    buffer = consumeEventFrames(buffer, onEvent);
    if (done) {
      if (buffer.trim()) consumeEventFrames(`${buffer}\n\n`, onEvent);
      break;
    }
  }
}

function consoleLines(report, turns, asking, question, runFeed) {
  const lines = [
    { kind: "graph", text: "langgraph StateGraph  orchestrator → extractor → researcher → classifier → validator → auditor → pack" },
    { kind: "graph", text: "conditional edge  validator → classifier when totals fail and the repair budget is unused" },
    { kind: "graphdb", text: "no graph database was called. The graph runs in process." },
  ];
  if (runFeed) {
    lines.push({ kind: "desk", text: runFeed.opening });
    for (const event of runFeed.events) pushStep(lines, event);
    if (runFeed.note) lines.push({ kind: "desk", text: runFeed.note });
  } else if (!report) {
    lines.push({ kind: "agent", text: "waiting for a run" });
  }
  if (report && !runFeed) {
    const phase = report.phase || {};
    lines.push({
      kind: "txn",
      text: `run ${report.run_id || "unsaved"}  ${report.status || "draft"}  cohort ${phase.cohort || "—"}  appoint ${phase.appoint || "—"}  actor ${report.approval?.actor || "unsigned"}`,
    });
    for (const event of report.events || []) pushStep(lines, event);
    for (const usage of report.usages || []) {
      lines.push({
        kind: "llm",
        text: `omniroute  ${usage.model || "replay"}  ${usage.purpose || "unknown"}  tokens ${tokenCount(usage, "prompt_tokens")}→${tokenCount(usage, "completion_tokens")}  retry ${usage.retry_reason || "none"}`,
      });
    }
    lines.push({ kind: "tool", text: `sqlite readiness.db  read run ${report.run_id || "latest"}  ${(report.items || []).length} documents` });
    for (const item of report.items || []) {
      const held = (item.failures || []).join(", ") || "none";
      const verdict = item.auditor?.verdict || "none";
      lines.push({
        kind: "txn",
        text: `${item.item_id}  ${item.outcome}  repairs ${item.repairs || 0}  held ${held}  auditor ${verdict}`,
      });
    }
  }
  for (const turn of turns || []) {
    const asked = turn.question ? `"${turn.question}"  ` : "";
    const preview = (turn.answer_en || "").replace(/\s+/g, " ").slice(0, 220);
    if (!turn.model) {
      lines.push({ kind: "txn", text: `ask  no model call  ${asked}${preview || turn.retry_reason || "abstained"}` });
    } else {
      lines.push({ kind: "txn", text: `ask  ${turn.model}  ${asked}${preview}` });
      if ((turn.citations || []).length) {
        const ids = turn.citations.map((item) => item.passage_id).join(", ");
        lines.push({ kind: "tool", text: `cite  ${ids}` });
      }
    }
  }
  if (asking) lines.push({ kind: "llm", text: `ask  waiting  "${question}"` });
  return lines;
}

function money(value) {
  if (value === undefined || value === null || value === "") return "—";
  return new Intl.NumberFormat("en-AE", { style: "currency", currency: "AED", maximumFractionDigits: 2 }).format(value);
}

export default function Desk({ t, lang, actor }) {
  const [profile, setProfile] = useState(null);
  const [residency, setResidency] = useState(null);
  const [modelCatalog, setModelCatalog] = useState(null);
  const [events, setEvents] = useState([]);
  const [report, setReport] = useState(null);
  const [replay, setReplay] = useState(false);
  const remembered = readMemory("tenant_desert_ledger");
  const skipSave = useRef(true);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState("");
  const [answer, setAnswer] = useState(remembered.answer);
  const [turns, setTurns] = useState(remembered.turns);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [picks, setPicks] = useState(remembered.picks);
  const [companyId, setCompanyId] = useState("tenant_desert_ledger");
  const [companies, setCompanies] = useState([]);
  const [view, setView] = useState("companies");
  const [running, setRunning] = useState(false);
  const [runFeed, setRunFeed] = useState(null);
  const [runId, setRunId] = useState("");
  const started = useRef(false);
  const consoleRef = useRef(null);
  const threadRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/residency")
      .then((response) => response.json())
      .then((body) => {
        if (!cancelled) setResidency(body);
      })
      .catch(() => {
        if (!cancelled) setResidency({ gateway_reachable: false, residency_verified: false, models: [] });
      });
    fetch("/api/models")
      .then((response) => response.json())
      .then((body) => {
        if (!cancelled) setModelCatalog(body);
      })
      .catch(() => {
        if (!cancelled) setModelCatalog(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (view !== "review") return undefined;
    let cancelled = false;
    fetch("/api/companies")
      .then((response) => response.json())
      .then((body) => {
        if (!cancelled) setCompanies(body.companies || []);
      })
      .catch(() => {
        if (!cancelled) setCompanies([]);
      });
    return () => {
      cancelled = true;
    };
  }, [view]);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/tenant?tenant_id=${companyId}`).then((response) => response.json()).then((body) => {
      if (!cancelled) setProfile(body);
    });
    fetch(`/api/runs/latest?tenant_id=${companyId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (cancelled || started.current) return;
        if (!body) {
          setRunId("");
          setReport(null);
          setReplay(false);
          setEvents([]);
          return;
        }
        setRunId(body.run_id);
        setReport(body);
        setReplay(Boolean(body.replay));
        setEvents(body.events || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  useEffect(() => {
    skipSave.current = true;
    const stored = readMemory(companyId);
    setAnswer(stored.answer);
    setTurns(stored.turns);
    setPicks(stored.picks);
  }, [companyId]);

  useEffect(() => {
    if (skipSave.current) {
      skipSave.current = false;
      return;
    }
    localStorage.setItem(memoryKey(companyId), JSON.stringify({ answer, turns, picks }));
  }, [answer, turns, picks, companyId]);

  async function readError(response) {
    const text = await response.text();
    try {
      const body = JSON.parse(text);
      if (typeof body?.detail === "string") return body.detail;
    } catch {
      /* The body is already plain text. */
    }
    return text;
  }

  function openCompany(id) {
    started.current = false;
    setCompanyId(id);
    setView("review");
    setError("");
    setRunId("");
    setReport(null);
    setEvents([]);
    setRunFeed(null);
  }

  async function streamRun(tenant, url, options, opening) {
    started.current = true;
    setCompanyId(tenant);
    setView("review");
    setBusy(true);
    setRunning(true);
    setError("");
    setEvents([]);
    setRunFeed({ opening, note: "Waiting for the API to accept the run.", events: [] });
    try {
      const response = await fetch(url, {
        ...options,
        headers: { Accept: "text/event-stream", ...(options?.headers || {}) },
      });
      if (!response.ok) {
        const message = await readError(response);
        setError(message);
        setRunFeed((current) => ({ ...current, note: `${response.status}  ${message}` }));
        return;
      }
      const type = response.headers.get("content-type") || "";
      if (!type.includes("text/event-stream")) {
        const accepted = await response.json();
        const packed = await fetch(`/api/reports/${accepted.run_id}?tenant_id=${tenant}`);
        const body = await packed.json();
        setRunId(accepted.run_id);
        setReplay(Boolean(accepted.replay));
        setReport(body);
        setEvents(body.events || []);
        setRunFeed(null);
        setAnswer(null);
        setTurns([]);
        return;
      }
      let donePayload = null;
      let failure = "";
      await readEventStream(response, (name, data) => {
        if (name === "accepted") {
          setRunFeed((current) => ({ ...current, note: data.message || "Request accepted." }));
          return;
        }
        if (name === "tick") {
          setRunFeed((current) => ({ ...current, note: `${data.node}  ${data.message}` }));
          return;
        }
        if (name === "node") {
          setEvents((current) => [...current, data]);
          setRunFeed((current) => ({ ...current, note: "", events: [...current.events, data] }));
          return;
        }
        if (name === "error") failure = data.detail || "The run stopped before a pack was saved.";
        if (name === "done") donePayload = data;
      });
      if (failure) {
        setError(failure);
        setRunFeed((current) => ({ ...current, note: failure }));
        return;
      }
      if (!donePayload?.run_id) {
        const message = "The run ended without a pack.";
        setError(message);
        setRunFeed((current) => ({ ...current, note: message }));
        return;
      }
      setRunId(donePayload.run_id);
      setReplay(Boolean(donePayload.replay));
      const packed = await fetch(`/api/reports/${donePayload.run_id}?tenant_id=${tenant}`);
      if (!packed.ok) {
        const message = await readError(packed);
        setError(message);
        setRunFeed((current) => ({ ...current, note: message }));
        return;
      }
      const body = await packed.json();
      setReport(body);
      setEvents(body.events || []);
      setAnswer(null);
      setTurns([]);
      setRunFeed(null);
    } catch (err) {
      const message = err?.message || "The run did not start.";
      setError(message);
      setRunFeed((current) => (current ? { ...current, note: message } : current));
    } finally {
      setBusy(false);
      setRunning(false);
    }
  }

  function processCompany(id, reuse) {
    const reuseFlag = reuse ? "true" : "false";
    return streamRun(
      id,
      `/api/companies/${id}/process?reuse=${reuseFlag}`,
      { method: "POST" },
      `POST /api/companies/${id}/process  reuse=${reuseFlag}`,
    );
  }

  function start(ids) {
    return streamRun(
      companyId,
      "/api/runs",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: companyId, document_ids: ids }),
      },
      `POST /api/runs  ${ids.length} document${ids.length === 1 ? "" : "s"}`,
    );
  }

  async function loadSeeded() {
    setBusy(true);
    setError("");
    try {
      const loaded = await fetch("/api/demo/load", { method: "POST" });
      if (!loaded.ok) {
        setError(await readError(loaded));
        setBusy(false);
        return;
      }
      const body = await loaded.json();
      await start(body.documents.map((item) => item.id));
    } catch (err) {
      setError(err?.message || "The seeded batch did not load.");
      setBusy(false);
    }
  }

  async function chooseModel(event) {
    const model = event.target.value;
    const previous = modelCatalog;
    setModelCatalog((current) => (current ? { ...current, selected: model } : current));
    try {
      const response = await fetch("/api/models", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
      });
      if (!response.ok) {
        setModelCatalog(previous);
        setError(await readError(response));
        return;
      }
      setModelCatalog(await response.json());
    } catch {
      setModelCatalog(previous);
      setError("The model was not changed.");
    }
  }

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.set("tenant_id", companyId);
    form.set("synthetic", "true");
    form.set("file", file);
    const stored = await fetch("/api/documents", { method: "POST", body: form });
    if (!stored.ok) {
      setError(await readError(stored));
      return;
    }
    const body = await stored.json();
    await start([body.id]);
  }

  async function ask(event, preset) {
    if (event) event.preventDefault();
    const asked = (typeof preset === "string" ? preset : question).trim();
    if (!asked || asking) return;
    setAsking(true);
    setAskError("");
    setPending(asked);
    setQuestion("");
    const prior = turns.slice(-3).map((turn) => ({
      question: String(turn.question || "").slice(0, 500),
      answer_en: String(turn.answer_en || "").slice(0, 800),
    }));
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: companyId, question: asked, synthetic: true, run_id: runId, prior }),
      });
      const body = await response.json();
      if (!response.ok) {
        setAskError(typeof body?.detail === "string" ? body.detail : "The question did not go through.");
        setQuestion(asked);
        return;
      }
      const next = { ...body, question: asked };
      setAnswer(next);
      setTurns((current) => [...current, next].slice(-8));
    } catch {
      setAskError("The question did not go through.");
      setQuestion(asked);
    } finally {
      setAsking(false);
    }
  }

  async function decide(action) {
    const response = await fetch(`/api/runs/${runId}/decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: companyId, action, actor, note: "Signed on the desk" }),
    });
    if (!response.ok) {
      setError(await readError(response));
      return;
    }
    const packed = await fetch(`/api/reports/${runId}?tenant_id=${companyId}`);
    setReport(await packed.json());
  }

  const score = report
    ? report.quiz.filter((item) => picks[item.id] === item.answer).length
    : 0;
  const lines = events.length ? events : t.roles.map((role) => ({ node: role, message: t.waiting, at: "" }));
  const repairTaken = (report?.items || []).some((item) => item.repairs > 0) || (report?.events || []).some((event) => /returned|repaired/i.test(event.message));
  const log = consoleLines(report, turns, asking, asking ? pending : question, runFeed);
  const progress = busy ? runProgress(runFeed) : null;
  const stageDone = new Set();
  let stageCurrent = "";
  for (const event of runFeed?.events || []) {
    if (!event?.node || event.phase === "tick") continue;
    if (event.phase === "start" || event.phase === "work") stageCurrent = event.node;
    else if (STAGES.includes(event.node)) {
      stageDone.add(event.node);
      if (stageCurrent === event.node) stageCurrent = "";
    }
  }
  const logTail = `${log.length}:${log[log.length - 1]?.text || ""}`;

  useEffect(() => {
    const node = consoleRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [logTail]);

  useEffect(() => {
    const thread = threadRef.current;
    const latest = thread?.querySelector(".is-latest");
    if (thread && latest) thread.scrollTop = latest.offsetTop - thread.offsetTop;
  }, [turns, asking]);

  const prompts = promptsFor(report, t);

  return (
    <div className="desk">
      {residency ? (
        <div className={residency.gateway_reachable || residency.residency_verified ? "status-line is-quiet" : "status-line is-down"}>
          <span>{residency.residency_verified ? t.residencyClosed : residency.gateway_reachable ? t.residencyOpen : t.residencyDown}</span>
          {modelCatalog?.models?.length ? (
            <label className="model-pick">
              <span>{t.model}</span>
              <select className="ltr" dir="ltr" value={modelCatalog.selected || ""} disabled={busy || asking} onChange={chooseModel} aria-label={t.model}>
                {modelGroups(modelCatalog.models).map((group) => (
                  <optgroup key={group.name} label={group.name}>
                    {group.models.map((id) => <option key={id} value={id}>{id}</option>)}
                  </optgroup>
                ))}
              </select>
            </label>
          ) : (
            <span className="ltr">{residency.models?.[0] || ""}</span>
          )}
          {replay ? <span>{t.replay}</span> : null}
        </div>
      ) : null}
      <div className="stage">
      <nav className="side" aria-label={t.deskNav}>
        <button type="button" className={view === "companies" ? "is-on" : ""} aria-current={view === "companies" ? "page" : undefined} onClick={() => setView("companies")}>{t.board}</button>
        <button type="button" className={view === "statistics" ? "is-on" : ""} aria-current={view === "statistics" ? "page" : undefined} onClick={() => setView("statistics")}>{t.statistics}</button>
        <button type="button" className={view === "review" ? "is-on" : ""} aria-current={view === "review" ? "page" : undefined} onClick={() => setView("review")}>{t.review}</button>
        <button type="button" className={view === "explanation" ? "is-on" : ""} aria-current={view === "explanation" ? "page" : undefined} onClick={() => setView("explanation")}>{t.explanation}</button>
      </nav>
      <div className="work">
      <div className={view === "review" ? "sheet" : "sheet is-board"}>
        <section className="ledger">
          {view === "companies" || view === "statistics" ? (
            <Dashboard t={t} pane={view} running={running} activeId={companyId} error={error} onOpen={openCompany} onProcess={processCompany} />
          ) : null}
          {view === "explanation" ? (
            <Suspense fallback={<p className="lede">{lang === "ar" ? "يُجهَّز الشرح." : "Preparing the explanation."}</p>}>
              <Explanation lang={lang} />
            </Suspense>
          ) : null}
          <div hidden={view !== "review"}>
          <header className="ledger-head">
            <div>
              <h1>
                <CompanyPick
                  companies={companies.length ? companies : profile ? [profile] : []}
                  value={companyId}
                  onChange={openCompany}
                  label={t.reviewCompany}
                  placeholder={t.companySearchHint}
                  empty={t.noCompanyMatch}
                  more={t.companySearchMore}
                />
              </h1>
              <dl className="tally">
                <div><dt>{t.metaRevenue}</dt><dd className="ltr">{profile ? money(profile.stated_revenue_aed) : "—"}</dd></div>
                <div><dt>{t.metaDate}</dt><dd className="ltr">{profile?.research_date || "—"}</dd></div>
                <div><dt>{t.metaSeat}</dt><dd>{profile?.free_zone ? t.freeZone : t.mainland}</dd></div>
                {report?.phase ? (
                  <div>
                    <dt>{t.metaPhase}</dt>
                    <dd>
                      <span className={report.phase.status === "to_verify" ? "mark is-verify" : "mark is-pass"}>
                        {report.phase.cohort} · {report.phase.status === "to_verify" ? t.toVerify : report.phase.appoint}
                      </span>
                    </dd>
                  </div>
                ) : null}
              </dl>
            </div>
            <div className="actions">
              <button type="button" className="ghost" disabled={busy} aria-busy={busy} onClick={() => processCompany(companyId, true)}>{busy ? <span className="spinner" aria-hidden="true" /> : null}{busy ? t.rerunBusy : t.rerun}</button>
              {companyId === "tenant_desert_ledger" ? <button type="button" className="submit" disabled={busy} aria-busy={busy} onClick={loadSeeded}>{busy ? <span className="spinner" aria-hidden="true" /> : null}{t.load}</button> : null}
              <label className="ghost">{t.upload}<input type="file" accept=".json,.pdf,application/pdf,application/json" hidden onChange={upload} /></label>
            </div>
          </header>
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          {progress ? (
            <div className={progress.live ? "run-progress is-live" : "run-progress"} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress.ratio * 100)} aria-valuetext={progress.label}>
              <div className="run-progress-meta">
                <span className="run-progress-label">{progress.live ? <span className="spinner" aria-hidden="true" /> : null}<span>{progress.label}</span></span>
                <span className="ltr">{Math.round(progress.ratio * 100)}%</span>
              </div>
              <div className="run-progress-track"><div className="run-progress-fill" style={{ "--run-ratio": `${Math.round(progress.ratio * 100)}%` }} /></div>
            </div>
          ) : null}
          <section className="graph" aria-label={t.graphTitle}>
            <h2>{t.graphTitle}</h2>
            <ol className="graph-flow">
              {t.roles.map((role, index) => {
                const key = STAGES[index];
                const state = key === stageCurrent ? "is-on" : stageDone.has(key) ? "is-done" : "";
                return (
                  <li key={key} className={state} aria-current={state === "is-on" ? "step" : undefined}><span>{role}</span></li>
                );
              })}
            </ol>
            <p className={repairTaken ? "graph-edge is-repair" : "graph-edge"}>{repairTaken ? t.graphRepair : t.graphStraight}</p>
            <p className="graph-edge">{t.graphDb}</p>
          </section>
          <div className="table-wrap">
            <table className="blotter">
              <caption className="sr">{t.crumbBatch}</caption>
              <thead>
                <tr>
                  <th>{t.colDoc}</th>
                  <th>{t.colMark}</th>
                  <th>{t.colHeld}</th>
                  <th className="num">{t.colAmt}</th>
                </tr>
              </thead>
              <tbody>
                {(report?.items || []).length === 0 ? (
                  <tr><td className="empty" colSpan={4}>{t.tapeWait}</td></tr>
                ) : report.items.map((item) => {
                  const held = item.failures?.length
                    ? heldPhrase(item.failures[0], t)
                    : item.auditor?.verdict === "disagree"
                      ? t.plotDisagree
                      : t.heldClear;
                  return (
                  <tr key={item.item_id}>
                    <th scope="row" className="ltr">{item.invoice_id || item.item_id}</th>
                    <td><span className={item.outcome === "pass" ? "mark is-pass" : "mark is-verify"}>{item.outcome === "pass" ? t.pass : t.toVerify}</span></td>
                    <td>{held}</td>
                    <td className="num ltr">{item.gross_total !== undefined && item.gross_total !== null ? money(item.gross_total) : "—"}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {answer ? (
            <article className="answer">
              <p>{lang === "ar" ? answer.answer_ar : answer.answer_en}</p>
              <p>{lang === "ar" ? answer.answer_en : answer.answer_ar}</p>
              {(answer.citations || []).map((item) => (
                <p className="cite" key={item.passage_id}><span className="ltr">{item.source} · {item.page}</span><br />{item.text}</p>
              ))}
            </article>
          ) : null}
          {report && report.status === "awaiting_approval" ? (
            <div className="decision">
              <button type="button" className="submit" onClick={() => decide("approve")}>{t.approve}</button>
              <button type="button" className="ghost" onClick={() => decide("reject")}>{t.reject}</button>
              <button type="button" className="ghost" onClick={() => decide("escalate")}>{t.escalate}</button>
            </div>
          ) : null}
          {report?.status && report.status !== "awaiting_approval" ? <p className="signed ltr">{report.status} · {report.approval?.actor}</p> : null}
          {report ? (
            <>
              <section className="after">
                <h2>{t.limits}</h2>
                <p>{report.narrative}</p>
                <ul>{report.limitations.map((line) => <li key={line}>{line}</li>)}</ul>
              </section>
              <section className="after">
                <h2>{t.cards}</h2>
                {report.cards.map((card) => (
                  <article key={card.passage_id}>
                    <h3>{lang === "ar" ? card.title_ar : card.title_en}</h3>
                    <p>{lang === "ar" ? card.body_ar : card.body_en}</p>
                    <p className="cite"><span className="ltr">{card.source} · {card.page}</span><br />{card.passage}</p>
                  </article>
                ))}
              </section>
              <section className="after quiz">
                <h2>{t.quiz}</h2>
                <p className="signed">{score} / {report.quiz.length}. {t.quizNote}</p>
                {report.quiz.map((item) => (
                  <fieldset key={item.id}>
                    <legend>{lang === "ar" ? item.prompt_ar : item.prompt_en}</legend>
                    {(lang === "ar" ? item.choices_ar : item.choices_en).map((label, index) => {
                      const value = item.choices_en[index];
                      return (
                        <label className="choice" key={value}>
                          <input type="radio" name={item.id} checked={picks[item.id] === value} onChange={() => setPicks((current) => ({ ...current, [item.id]: value }))} /> {label}
                        </label>
                      );
                    })}
                  </fieldset>
                ))}
              </section>
            </>
          ) : null}
          </div>
        </section>
        <aside className="tape" aria-label={t.traceTitle}>
          <header className="tape-head">
            <h2>{t.traceTitle}</h2>
            <p>{t.people}</p>
          </header>
          <ol className="tape-list">
            {lines.map((event, index) => (
              <li key={`${event.at}-${event.node}-${index}`} className={events.length ? "is-live" : ""}>
                <span className="who">{event.node}</span>
                <span>{event.message}</span>
                {event.at ? <time className="ltr">{event.at.slice(11, 19)}</time> : null}
              </li>
            ))}
          </ol>
          <form className="composer" onSubmit={(event) => ask(event)}>
            <p className="ask-label">{t.askLabel}</p>
            <div className="thread" ref={threadRef}>
              {turns.map((turn, index) => {
                const latest = index === turns.length - 1;
                return (
                  <article key={`${turn.question}-${index}`} className={latest ? "is-latest" : ""}>
                    <p className="turn-q">{turn.question}</p>
                    {latest ? (
                      <>
                        <p className="turn-a">{lang === "ar" ? turn.answer_ar : turn.answer_en}</p>
                        <p className="turn-b">{lang === "ar" ? turn.answer_en : turn.answer_ar}</p>
                      </>
                    ) : null}
                  </article>
                );
              })}
              {asking ? <p className="reply is-wait">Asking…</p> : null}
              {!turns.length && !asking ? <p className="reply is-wait">{report ? t.askHint : t.askEmpty}</p> : null}
            </div>
            {askError ? <p className="reply is-wait">{askError}</p> : null}
            <div className="prompts">
              {prompts.map((prompt) => (
                <button key={prompt} type="button" title={prompt} disabled={asking} onClick={() => ask(null, prompt)}>{prompt}</button>
              ))}
            </div>
            <div className="composer-row">
              <label className="field">
                <span className="control"><input value={question} onChange={(event) => setQuestion(event.target.value)} dir={lang === "ar" ? "rtl" : "ltr"} aria-label={t.askLabel} /></span>
              </label>
              <button className="submit" type="submit" disabled={asking || !question.trim()}>{t.askButton}</button>
            </div>
          </form>
        </aside>
      </div>
      {view === "review" ? <section className="console" aria-label={t.consoleTitle}>
        <header className="console-head">
          <h2>{t.consoleTitle}</h2>
          <p>agent · tool · llm · graph · graphdb</p>
        </header>
        <ol ref={consoleRef}>
          {log.map((entry, index) => (
            <li key={`${entry.kind}-${index}`}>
              <span className={`kind kind-${entry.kind}`}>{entry.kind}</span>
              {entry.at ? <time className="ltr">{entry.at.slice(11, 19)}</time> : <time />}
              <span>{entry.text}</span>
            </li>
          ))}
        </ol>
      </section> : null}
      </div>
      </div>
    </div>
  );
}
