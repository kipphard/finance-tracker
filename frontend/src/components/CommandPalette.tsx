import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../theme";

interface Cmd {
  id: string;
  label: string;
  run: () => void;
}

// A ⌘K / Ctrl+K quick-action menu (keyboard-only, no AI): jump to any section or toggle the theme.
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const navigate = useNavigate();
  const { toggle } = useTheme();
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: Cmd[] = useMemo(() => {
    const go = (path: string) => () => { navigate(path); setOpen(false); };
    return [
      { id: "fin", label: "Finances · Overview", run: go("/") },
      { id: "analytics", label: "Finances · Analytics", run: go("/analytics") },
      { id: "appsettings", label: "Finances · Settings (categories & playbook)", run: go("/settings") },
      { id: "time", label: "Freelance · Time / Timer", run: go("/freelance") },
      { id: "clients", label: "Freelance · Clients & projects", run: go("/freelance/clients") },
      { id: "invoices", label: "Freelance · Invoices", run: go("/freelance/invoices") },
      { id: "newinv", label: "New invoice", run: go("/freelance/invoices") },
      { id: "insights", label: "Freelance · Insights", run: go("/freelance/insights") },
      { id: "settings", label: "Freelance · Settings", run: go("/freelance/settings") },
      { id: "theme", label: "Toggle dark / light theme", run: () => { toggle(); setOpen(false); } },
    ];
  }, [navigate, toggle]);

  const filtered = q
    ? commands.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()))
    : commands;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
        setQ("");
        setSel(0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 0); }, [open]);
  useEffect(() => { setSel(0); }, [q]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") setOpen(false);
    else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, filtered.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); filtered[sel]?.run(); }
  };

  return (
    <div className="cmdk-backdrop" onClick={() => setOpen(false)}>
      <div className="cmdk" onClick={(e) => e.stopPropagation()}>
        <input ref={inputRef} className="cmdk__input" placeholder="Type a command…"
          value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKeyDown} />
        <div className="cmdk__list">
          {filtered.length === 0 ? (
            <div className="cmdk__empty">No commands</div>
          ) : (
            filtered.map((c, i) => (
              <div key={c.id} className={"cmdk__item" + (i === sel ? " is-sel" : "")}
                onMouseEnter={() => setSel(i)} onClick={() => c.run()}>
                {c.label}
              </div>
            ))
          )}
        </div>
        <div className="cmdk__foot muted">↑↓ navigate · ↵ select · esc close</div>
      </div>
    </div>
  );
}
