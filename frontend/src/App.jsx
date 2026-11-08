import { useEffect, useState } from "react";
import { copy, emailOk } from "./copy";
import Desk from "./Desk";
import Landing from "./Landing";
import Login from "./Login";

const SEAT_KEY = "desert-ledger-seat";

function storedSeat() {
  try {
    const value = localStorage.getItem(SEAT_KEY) || "";
    return emailOk(value) ? value : "";
  } catch {
    return "";
  }
}

function rememberSeat(email) {
  const value = email.trim();
  localStorage.setItem(SEAT_KEY, value);
  return value;
}

function forgetSeat() {
  localStorage.removeItem(SEAT_KEY);
}

function Mark() {
  return (
    <svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true">
      <rect width="28" height="28" rx="8" fill="#5266eb" />
      <path d="M7 9.5h14M7 14h14M7 18.5h9" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export default function App() {
  const [lang, setLang] = useState("en");
  const [actor, setActor] = useState(storedSeat);
  const [screen, setScreen] = useState("landing");
  const t = copy[lang];

  function showLanding(hash) {
    setScreen("landing");
    if (!hash) return;
    window.setTimeout(() => document.querySelector(hash)?.scrollIntoView({ behavior: "smooth" }), 0);
  }

  useEffect(() => {
    document.documentElement.lang = lang === "ar" ? "ar" : "en";
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  return (
    <>
      <a className="skip" href="#main">{lang === "ar" ? "إلى المكتب" : "Skip to the desk"}</a>
      <header className="bar">
        <a className="brand" href="#top" onClick={(event) => { if (actor) return; event.preventDefault(); showLanding("#top"); }}><Mark /><span>{t.brand}</span></a>
        {actor ? null : (
          <nav className="nav-links" aria-label="Page">
            <a href="#work" onClick={(event) => { event.preventDefault(); showLanding("#work"); }}>{t.navWork}</a>
            <a href="#platform" onClick={(event) => { event.preventDefault(); showLanding("#platform"); }}>{t.navPlatform}</a>
            <a href="#gate" onClick={(event) => { event.preventDefault(); showLanding("#gate"); }}>{t.navGate}</a>
          </nav>
        )}
        <div className="nav-end">
          <button type="button" className="lang" aria-pressed={lang === "ar"} onClick={() => setLang(lang === "en" ? "ar" : "en")}>{lang === "en" ? "العربية" : "English"}</button>
          {actor ? (
            <>
              <p className="session">{t.seat}</p>
              <button type="button" className="logout" onClick={() => { forgetSeat(); setActor(""); setScreen("landing"); }}>{t.logout}</button>
            </>
          ) : <button type="button" className="nav-signin" onClick={() => setScreen("login")}>{t.navSign}</button>}
        </div>
      </header>
      <main id="main">
        {actor ? <Desk t={t} lang={lang} actor={actor} /> : screen === "login"
          ? <Login t={t} onOpen={(email) => setActor(rememberSeat(email))} onBack={() => showLanding("#top")} />
          : <Landing t={t} onEnter={() => setScreen("login")} />}
      </main>
      <footer className="foot"><p>{t.footer}</p><p className="ltr">2026-11-07</p></footer>
    </>
  );
}
