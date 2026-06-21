import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { CommandPalette } from "./CommandPalette";
import { Dashboard } from "./Dashboard";
import { AnalyticsPage } from "./AnalyticsPage";
import { PlaybookPage } from "./PlaybookPage";
import { SettingsPage } from "./SettingsPage";
import { Freelance } from "./freelance/Freelance";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  "sidebar__link" + (isActive ? " is-active" : "");

export function AppShell() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">💰 Finance</div>
        <nav className="sidebar__nav">
          <NavLink to="/" end className={linkClass}>
            <span className="sidebar__icon">💰</span> Finances
          </NavLink>
          <NavLink to="/analytics" className={linkClass}>
            <span className="sidebar__icon">📈</span> Analytics
          </NavLink>
          <NavLink to="/freelance" className={linkClass}>
            <span className="sidebar__icon">🧑‍💻</span> Freelance
          </NavLink>
          <NavLink to="/playbook" className={linkClass}>
            <span className="sidebar__icon">🧭</span> Playbook
          </NavLink>
          <NavLink to="/settings" className={linkClass}>
            <span className="sidebar__icon">⚙️</span> Settings
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
          <Route path="/" element={<Dashboard />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/playbook" element={<PlaybookPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/freelance/*" element={<Freelance />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <CommandPalette />
    </div>
  );
}
