import { useEffect, useId, useRef, useState } from "react";

const VISIBLE = 8;

export default function CompanyPick({ companies, value, onChange, label, placeholder, empty, more }) {
  const selected = companies.find((company) => company.tenant_id === value);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef(null);
  const listId = useId();
  const labelId = useId();
  const needle = query.trim().toLocaleLowerCase();
  const matches = needle
    ? companies.filter((company) => company.legal_name.toLocaleLowerCase().includes(needle))
    : companies;
  const visible = matches.slice(0, VISIBLE);

  useEffect(() => {
    setActive(0);
  }, [needle, open]);

  useEffect(() => {
    if (!open) return undefined;
    function close(event) {
      if (!root.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  function choose(id) {
    onChange(id);
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((index) => Math.min(index + 1, Math.max(visible.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && open && visible[active]) {
      event.preventDefault();
      choose(visible[active].tenant_id);
    } else if (event.key === "Escape") {
      setQuery("");
      setOpen(false);
    }
  }

  return (
    <div className="company-pick" ref={root}>
      <label id={labelId} htmlFor={`${listId}-input`}>{label}</label>
      <input
        id={`${listId}-input`}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open && visible[active] ? `${listId}-${active}` : undefined}
        placeholder={placeholder}
        value={open ? query : (selected?.legal_name || "")}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          setQuery("");
          setOpen(true);
        }}
        onKeyDown={onKeyDown}
      />
      {open ? (
        <ul id={listId} role="listbox" aria-labelledby={labelId}>
          {visible.map((company, index) => (
            <li key={company.tenant_id} role="presentation">
              <button
                type="button"
                id={`${listId}-${index}`}
                role="option"
                aria-selected={company.tenant_id === value}
                className={index === active ? "is-active" : ""}
                onMouseEnter={() => setActive(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(company.tenant_id)}
              >
                {company.legal_name}
              </button>
            </li>
          ))}
          {matches.length === 0 ? <li className="pick-empty">{empty}</li> : null}
          {matches.length > VISIBLE ? <li className="pick-more">{more.replace("{n}", String(matches.length - VISIBLE))}</li> : null}
        </ul>
      ) : null}
    </div>
  );
}
