const ROWS = [
  { id: "DL-INV-1001", outcome: "pass", held: "", amount: "AED 1,050.00" },
  { id: "DL-INV-1002", outcome: "verify", held: "buyer_id_present", amount: "AED 900.00" },
  { id: "DL-INV-1003", outcome: "verify", held: "duplicate_invoice_id", amount: "AED 1,050.00" },
  { id: "DL-INV-1005", outcome: "verify", held: "", amount: "AED 1,050.00" },
];

export default function Landing({ t, onEnter }) {
  return (
    <>
      <section className="hero" id="top">
        <div className="hero-copy">
          <h1>{t.headline}</h1>
          <p className="lede">{t.lede}</p>
          <div className="hero-actions">
            <button type="button" className="submit" onClick={onEnter}>{t.ctaBtn}</button>
          </div>
        </div>
        <div className="arrival-desk" id="work">
          <div className="mini-ledger">
            <header>
              <h2>{t.previewTenant}</h2>
              <p className="figures">
                <span>{t.synthetic}</span>
                <span className="ltr">SYNTHETIC_TRN_NOT_VALID</span>
                <span className="ltr">AED 62,000,000</span>
                <span className="ltr">2026-11-07</span>
              </p>
            </header>
            <table className="blotter">
              <caption className="sr">{t.workTitle}</caption>
              <thead>
                <tr>
                  <th>{t.colDoc}</th>
                  <th>{t.colMark}</th>
                  <th>{t.colHeld}</th>
                  <th>{t.colAmt}</th>
                </tr>
              </thead>
              <tbody>
                {ROWS.map((row) => (
                  <tr key={row.id}>
                    <th scope="row" className="ltr">{row.id}</th>
                    <td><span className={row.outcome === "pass" ? "mark is-pass" : "mark is-verify"}>{row.outcome === "pass" ? t.pass : t.toVerify}</span></td>
                    <td className="ltr">{row.held}</td>
                    <td className="num ltr">{row.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <aside className="mini-tape" aria-label={t.previewTape}>
            <ol>
              <li>{t.tapeKept}</li>
              <li>{t.tapeRepair}</li>
              <li>{t.tapeAuditor}</li>
            </ol>
            <div className="mini-ask">
              <p>{t.previewAsk}</p>
            </div>
          </aside>
        </div>
      </section>
      <section className="sequence" id="platform">
        <div className="band">
          <h2>{t.platTitle}</h2>
          <p className="lede">{t.p3b}</p>
          <ol className="role-line">
            {t.roles.map((role) => <li key={role}>{role}</li>)}
            <li>{t.roleApprover}</li>
          </ol>
        </div>
      </section>
      <section className="close-band" id="gate">
        <div className="band">
          <div>
            <h2>{t.ctaTitle}</h2>
            <p className="lede">{t.ctaBody}</p>
          </div>
          <button type="button" className="submit" onClick={onEnter}>{t.ctaBtn}</button>
        </div>
      </section>
    </>
  );
}
