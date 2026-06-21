import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { CommandPalette } from "./CommandPalette";
import { Finances } from "./Finances";
import { Freelance } from "./freelance/Freelance";

export function AppShell() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  // Finances owns every route that isn't under /freelance (incl. its Analytics/Settings sub-tabs),
  // so drive the sidebar active state from the path rather than NavLink's exact matching.
  const inFreelance = useLocation().pathname.startsWith("/freelance");
  const cls = (active: boolean) => "sidebar__link" + (active ? " is-active" : "");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">💰 Finance</div>
        <nav className="sidebar__nav">
          <NavLink to="/" className={() => cls(!inFreelance)}>
            <span className="sidebar__icon">💰</span> Finances
          </NavLink>
          <NavLink to="/freelance" className={() => cls(inFreelance)}>
            <span className="sidebar__icon">🧑‍💻</span> Freelance
          </NavLink>
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
          <Route path="/*" element={<Finances />} />
        </Routes>
      </main>

      <CommandPalette />
    </div>
  );
}
