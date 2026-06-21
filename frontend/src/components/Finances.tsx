import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Dashboard } from "./Dashboard";
import { AnalyticsPage } from "./AnalyticsPage";
import { SettingsPage } from "./SettingsPage";

const tabClass = ({ isActive }: { isActive: boolean }) =>
  "subnav__link" + (isActive ? " is-active" : "");

// The Finances section: an Overview dashboard plus Analytics and Settings sub-tabs.
export function Finances() {
  return (
    <div className="container">
      <div className="page-head">
        <h1>💰 Finances</h1>
      </div>

      <nav className="subnav">
        <NavLink to="/" end className={tabClass}>Overview</NavLink>
        <NavLink to="/analytics" className={tabClass}>Analytics</NavLink>
        <NavLink to="/settings" className={tabClass}>Settings</NavLink>
      </nav>

      <Routes>
        <Route index element={<Dashboard />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
