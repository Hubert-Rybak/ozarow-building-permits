import { useEffect, useState } from "react";
import { safeUrl } from "./model";

export function ExternalLink({ url, children, className = "", sub }: {
  url: string;
  children: React.ReactNode;
  className?: string;
  sub?: React.ReactNode;
}) {
  const href = safeUrl(url);
  if (!href) return <span className="muted">Link niedostępny</span>;
  return (
    <a className={className} href={href} target="_blank" rel="noopener noreferrer">
      <span className="link-main">{children}<span aria-hidden="true"> ↗</span></span>
      {sub && <span className="link-sub">{sub}</span>}
    </a>
  );
}

export function CopyButton({ value, label }: { value: string; label: string }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const timer = setTimeout(() => setDone(false), 2000);
    return () => clearTimeout(timer);
  }, [done]);
  return (
    <button
      type="button"
      className="copy-button"
      onClick={() => {
        navigator.clipboard?.writeText(value).then(() => setDone(true), () => {});
      }}
    >
      {done ? "Skopiowano" : label}
    </button>
  );
}

export function ShareButton({ url }: { url: string }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const timer = setTimeout(() => setDone(false), 2000);
    return () => clearTimeout(timer);
  }, [done]);
  return (
    <button
      type="button"
      className="round-button"
      aria-label={done ? "Skopiowano link do wpisu" : "Udostępnij link do wpisu"}
      title="Udostępnij link"
      onClick={() => {
        if (typeof navigator.share === "function")
          navigator.share({ url }).catch(() => {});
        else navigator.clipboard?.writeText(url).then(() => setDone(true), () => {});
      }}
    >
      {done ? <span aria-hidden="true">✓</span> : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" /><path d="M12 3v12" /><path d="m7 8 5-5 5 5" />
        </svg>
      )}
    </button>
  );
}

export function BackButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" className="back-button" onClick={onClick} aria-label={label}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 18 9 12l6-6" /></svg>
      Lista
    </button>
  );
}

export function Chip({ pressed, onClick, children, dot, shape = "circle" }: {
  pressed: boolean;
  onClick: () => void;
  children: React.ReactNode;
  dot?: string;
  shape?: "circle" | "square";
}) {
  return (
    <button type="button" className="chip" aria-pressed={pressed} onClick={onClick}>
      {dot && <span className={`chip-dot ${shape}`} style={{ background: dot }} aria-hidden="true" />}
      {children}
    </button>
  );
}

export function ChipSelect({ label, value, onChange, children, active }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
  active: boolean;
}) {
  return (
    <label className={`chip chip-select${active ? " active" : ""}`}>
      <span className="sr-only">{label}</span>
      <select value={value} onChange={event => onChange(event.target.value)}>{children}</select>
    </label>
  );
}

export function SearchBox({ id, label, value, onChange, placeholder, onFocus }: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  onFocus?: () => void;
}) {
  return (
    <div className="search-box">
      <label htmlFor={id} className="sr-only">{label}</label>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.5 15.5 5 5" /></svg>
      <input id={id} type="search" value={value} placeholder={placeholder} onFocus={onFocus}
        onChange={event => onChange(event.target.value)} />
    </div>
  );
}

export function useIsMobile() {
  const query = "(max-width: 720px)";
  const read = () => typeof window.matchMedia === "function" && !!window.matchMedia(query)?.matches;
  const [mobile, setMobile] = useState(read);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const list = window.matchMedia(query);
    if (!list?.addEventListener) return;
    const update = () => setMobile(list.matches);
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, []);
  return mobile;
}

export const PAGE = 50;
export function MoreButton({ shown, total, onMore }: { shown: number; total: number; onMore: () => void }) {
  if (shown >= total) return null;
  return (
    <button type="button" className="more-button" onClick={onMore}>
      Pokaż kolejne {Math.min(PAGE, total - shown)} z {total - shown}
    </button>
  );
}
