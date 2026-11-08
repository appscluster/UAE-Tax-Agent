import { useState } from "react";
import { emailOk, passwordOk } from "./copy";

export default function Login({ t, onOpen, onBack }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");

  function submit(event) {
    event.preventDefault();
    if (!emailOk(email)) {
      setError(t.errEmail);
      return;
    }
    if (!passwordOk(password)) {
      setError(t.errPassword);
      return;
    }
    onOpen(email.trim());
  }

  const lengthMet = password.length >= 8;
  const symbolMet = /[0-9]|[^A-Za-z0-9\s]/.test(password);

  return (
    <section className="seat" id="desk">
      <div className="seat-card">
        <button type="button" className="quiet-link back" onClick={onBack}>{t.backHome}</button>
        <h1>{t.loginTitle}</h1>
        <p className="lede">{t.loginLede}</p>
        <form onSubmit={submit} noValidate>
          <label className="field">
            <span>{t.emailLabel}</span>
            <span className={emailOk(email) ? "control is-valid" : "control"}>
              <input value={email} onChange={(event) => { setEmail(event.target.value); setError(""); }} type="email" dir="ltr" placeholder="reviewer@desert-ledger.example" autoComplete="username" />
            </span>
          </label>
          <label className="field">
            <span>{t.passwordLabel}</span>
            <span className="control">
              <input value={password} onChange={(event) => { setPassword(event.target.value); setError(""); }} type={show ? "text" : "password"} dir="ltr" autoComplete={mode === "login" ? "current-password" : "new-password"} />
              <button type="button" className="eye" aria-pressed={show} onClick={() => setShow((value) => !value)}>{show ? t.hidePassword : t.showPassword}</button>
            </span>
          </label>
          <ul className="rules">
            <li className={lengthMet ? "is-met" : ""}>{t.ruleLength}</li>
            <li className={symbolMet ? "is-met" : ""}>{t.ruleSymbol}</li>
          </ul>
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          <button className="submit" type="submit">{mode === "login" ? t.submitLogin : t.submitSignup}</button>
        </form>
        <p className="fine">{mode === "login" ? t.needAccount : t.haveAccount} <button type="button" className="text-btn" onClick={() => setMode(mode === "login" ? "signup" : "login")}>{mode === "login" ? t.swapToSignup : t.swapToLogin}</button></p>
      </div>
    </section>
  );
}
