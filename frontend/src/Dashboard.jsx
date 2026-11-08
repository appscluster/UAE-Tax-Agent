import { useEffect, useRef, useState } from "react";
import Plots from "./Plots";
import { runStatus, statusClass } from "./marks";

const ROLES = ["orchestrator", "extractor", "researcher", "classifier", "validator", "auditor", "pack"];

export default function Dashboard({ t, pane, running, activeId, error, onOpen, onProcess }) {
  const [board, setBoard] = useState(null);
  const [form, setForm] = useState({ legal_name: "", seat: "mainland", stated_revenue_aed: "" });
  const [editing, setEditing] = useState("");
  const [confirmId, setConfirmId] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [query, setQuery] = useState("");
  const heading = useRef(null);
  const formRef = useRef(null);

  async function reload() {
    const response = await fetch("/api/dashboard");
    if (response.ok) setBoard(await response.json());
  }

  useEffect(() => {
    reload();
  }, [running]);

  useEffect(() => {
    heading.current?.focus();
  }, [pane]);

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setFormError("");
    const payload = {
      legal_name: form.legal_name.trim(),
      seat: form.seat,
      stated_revenue_aed: Number(form.stated_revenue_aed),
    };
    const response = await fetch(editing ? `/api/companies/${editing}` : "/api/companies", {
      method: editing ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setSaving(false);
    if (!response.ok) {
      const text = await response.text();
      try {
        const body = JSON.parse(text);
        setFormError(typeof body?.detail === "string" ? body.detail : text);
      } catch {
        setFormError(text);
      }
      return;
    }
    setEditing("");
    setConfirmId("");
    setForm({ legal_name: "", seat: "mainland", stated_revenue_aed: "" });
    reload();
  }

  function beginEdit(row) {
    setEditing(row.tenant_id);
    setConfirmId("");
    setForm({
      legal_name: row.legal_name,
      seat: row.free_zone ? "free_zone" : "mainland",
      stated_revenue_aed: String(row.stated_revenue_aed),
    });
    window.requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ block: "nearest" });
      formRef.current?.querySelector("input")?.focus();
    });
  }

  async function remove(id) {
    if (confirmId !== id) {
      setConfirmId(id);
      return;
    }
    await fetch(`/api/companies/${id}`, { method: "DELETE" });
    setConfirmId("");
    if (editing === id) setEditing("");
    reload();
  }

  const rows = board?.rows || [];
  const needle = query.trim().toLocaleLowerCase();
  const shown = needle
    ? rows.filter((row) => row.legal_name.toLocaleLowerCase().includes(needle))
    : rows;
  const focus = rows.find((row) => row.tenant_id === activeId) || rows[0];

  return (
    <div className="board">
      <h1 ref={heading} tabIndex={-1}>{pane === "statistics" ? t.statistics : t.board}</h1>
      {error || formError ? <p className="form-error" role="alert">{error || formError}</p> : null}
      {pane === "companies" ? null : <>
      <p className="graph-edge">{t.dashNote}</p>
      <dl className="tally">
        <div><dt>{t.dashCompanies}</dt><dd className="ltr">{board ? board.companies : "—"}</dd></div>
        <div><dt>{t.dashDocuments}</dt><dd className="ltr">{board ? board.documents : "—"}</dd></div>
        <div><dt>{t.dashOpen}</dt><dd className="ltr">{board ? board.open_items : "—"}</dd></div>
        <div><dt>{t.dashAwaiting}</dt><dd className="ltr">{board ? board.awaiting : "—"}</dd></div>
      </dl>
      <Plots rows={rows} t={t} />
      <h2>{t.dashAgents}</h2>
      <p className="graph-edge">{focus ? `${t.dashFocus} ${focus.legal_name}. ${running ? t.dashLive : t.dashIdle}` : t.dashIdle}</p>
      <ul className="agent-board">
        {ROLES.map((role, index) => {
          const known = focus?.agents?.find((item) => item.node === role);
          return (
            <li key={role}>
              <span>{t.roles[index]}</span>
              <p>{running ? t.dashLive : known?.message}</p>
            </li>
          );
        })}
      </ul>
      </>}
      {pane === "statistics" ? null : <>
      <label className="company-search">
        <span>{t.companySearch}</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t.companySearchHint} />
      </label>
      <div className="table-wrap">
        <table className="blotter">
          <thead>
            <tr>
              <th>{t.dashCompanies}</th>
              <th>{t.dashDocuments}</th>
              <th>{t.pass}</th>
              <th>{t.toVerify}</th>
              <th>{t.colMark}</th>
            </tr>
          </thead>
          <tbody>
            {needle && shown.length === 0 ? (
              <tr>
                <td colSpan={5}>{t.noCompanyMatch}</td>
              </tr>
            ) : null}
            {shown.map((row) => (
              <tr key={row.tenant_id}>
                <th scope="row">
                  <button type="button" className="row-open" onClick={() => onOpen(row.tenant_id)}>{row.legal_name}</button>
                  <div className="row-actions">
                    <button type="button" className="ghost" disabled={running} aria-busy={running && activeId === row.tenant_id} onClick={() => onProcess(row.tenant_id, false)}>{running && activeId === row.tenant_id ? <span className="spinner" aria-hidden="true" /> : null}{running && activeId === row.tenant_id ? t.rerunBusy : t.runAgents}</button>
                    <button type="button" className="ghost" disabled={running || !row.run_id} aria-busy={running && activeId === row.tenant_id} onClick={() => onProcess(row.tenant_id, true)}>{running && activeId === row.tenant_id ? <span className="spinner" aria-hidden="true" /> : null}{running && activeId === row.tenant_id ? t.rerunBusy : t.rerun}</button>
                    <button type="button" className="ghost" onClick={() => beginEdit(row)}>{t.edit}</button>
                    <button type="button" className={confirmId === row.tenant_id ? "ghost is-danger" : "ghost"} onClick={() => remove(row.tenant_id)}>{confirmId === row.tenant_id ? t.confirmRemove : t.removeCompany}</button>
                  </div>
                </th>
                <td className="num ltr">{row.documents}</td>
                <td className="num ltr">{row.run_id ? row.pass_count : "—"}</td>
                <td className="num ltr">{row.run_id ? row.verify_count : "—"}</td>
                <td><span className={statusClass(row.run_status)}>{runStatus(row.run_status, t)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="company-form" ref={formRef} onSubmit={save}>
        <h2>{editing ? t.editCompany : t.addCompany}</h2>
        <label className="field">
          <span>{t.companyName}</span>
          <span className="control"><input value={form.legal_name} onChange={(event) => setForm({ ...form, legal_name: event.target.value })} required /></span>
        </label>
        <label className="field">
          <span>{t.companySeat}</span>
          <span className="control">
            <select value={form.seat} onChange={(event) => setForm({ ...form, seat: event.target.value })}>
              <option value="mainland">{t.mainland}</option>
              <option value="free_zone">{t.freeZone}</option>
            </select>
          </span>
        </label>
        <label className="field">
          <span>{t.companyRevenue}</span>
          <span className="control"><input className="ltr" inputMode="decimal" value={form.stated_revenue_aed} onChange={(event) => setForm({ ...form, stated_revenue_aed: event.target.value })} required /></span>
        </label>
        <button className="submit" type="submit" disabled={saving}>{editing ? t.editCompany : t.addCompany}</button>
      </form>
      </>}
    </div>
  );
}
