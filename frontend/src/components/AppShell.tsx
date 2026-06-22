import { useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { CommandPalette } from "./CommandPalette";
import { Finances } from "./Finances";
import { Freelance } from "./freelance/Freelance";
import { Taxes } from "./tax/Taxes";

// The three top-level sections. `match` drives the active state from the path because
// Finances owns "/" plus its own Analytics/Settings sub-routes (NavLink's exact matching
// can't express "everything that isn't /freelance or /taxes").
const SECTIONS = [
  {
    to: "/",
    icon: "💰",
    label: "Finances",
    match: (p: string) => !p.startsWith("/freelance") && !p.startsWith("/taxes"),
  },
  { to: "/freelance", icon: "🧑‍💻", label: "Freelance", match: (p: string) => p.startsWith("/freelance") },
  { to: "/taxes", icon: "🧾", label: "Taxes", match: (p: string) => p.startsWith("/taxes") },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [moreOpen, setMoreOpen] = useState(false);
  const path = useLocation().pathname;
  const cls = (active: boolean) => "sidebar__link" + (active ? " is-active" : "");

  return (
    <div className="app-shell">
      {/* Desktop sidebar (hidden on mobile, replaced by the bottom nav) */}
      <aside className="sidebar">
        <div className="sidebar__brand">💰 Finance</div>
        <nav className="sidebar__nav">
          {SECTIONS.map((s) => (
            <NavLink key={s.to} to={s.to} className={() => cls(s.match(path))}>
              <span className="sidebar__icon">{s.icon}</span> {s.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          <button className="icon-btn" onClick={toggle} aria-label="Toggle theme"
            title="Toggle light / dark">
            {theme === "light" ? "🌙" : "☀️"}
          </button>
          <span className="muted sidebar__email" title={user?.email}>{user?.email}</span>
          <button className="btn btn--ghost btn--sm" onClick={logout}>Log out</button>
        </div>
      </aside>

      <main className="app-main">
        <Routes>
          <Route path="/freelance/*" element={<Freelance />} />
          <Route path="/taxes/*" element={<Taxes />} />
          <Route path="/*" element={<Finances />} />
        </Routes>
      </main>

      {/* Mobile bottom tab bar */}
      <nav className="bottom-nav">
        {SECTIONS.map((s) => (
          <NavLink
            key={s.to}
            to={s.to}
            className={() => "bottom-nav__item" + (s.match(path) ? " is-active" : "")}
          >
            <span className="bottom-nav__icon">{s.icon}</span>
            {s.label}
          </NavLink>
        ))}
        <button
          className={"bottom-nav__item" + (moreOpen ? " is-active" : "")}
          onClick={() => setMoreOpen(true)}
        >
          <span className="bottom-nav__icon">☰</span>
          More
        </button>
      </nav>

      {/* Mobile "More" sheet — the desktop sidebar footer (theme / account / logout) */}
      {moreOpen && (
        <div className="more-sheet" onClick={() => setMoreOpen(false)}>
          <div className="more-sheet__panel" onClick={(e) => e.stopPropagation()}>
            <div className="more-sheet__head">
              <strong>💰 Finance</strong>
              <button className="icon-btn" onClick={() => setMoreOpen(false)} aria-label="Close">
                ✕
              </button>
            </div>
            <div className="more-sheet__row">
              <span className="muted sidebar__email" title={user?.email} style={{ flex: 1 }}>
                {user?.email}
              </span>
              <button className="icon-btn" onClick={toggle} aria-label="Toggle theme"
                title="Toggle light / dark">
                {theme === "light" ? "🌙" : "☀️"}
              </button>
            </div>
            <button
              className="btn btn--ghost"
              style={{ width: "100%" }}
              onClick={() => {
                setMoreOpen(false);
                logout();
              }}
            >
              Log out
            </button>
          </div>
        </div>
      )}

      <CommandPalette />
    </div>
  );
}
