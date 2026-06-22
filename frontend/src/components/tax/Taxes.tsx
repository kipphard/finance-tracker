import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { TaxOverviewPage } from "./TaxOverviewPage";
import { TaxSettingsPage } from "./TaxSettingsPage";

const tabClass = ({ isActive }: { isActive: boolean }) =>
  "subnav__link" + (isActive ? " is-active" : "");

// The Taxes section: a German freelance EÜR overview plus a settings/questionnaire tab.
export function Taxes() {
  return (
    <div className="container">
      <div className="page-head">
        <h1>🧾 Taxes</h1>
      </div>

      <nav className="subnav">
        <NavLink to="/taxes" end className={tabClass}>Overview</NavLink>
        <NavLink to="/taxes/settings" className={tabClass}>Settings</NavLink>
      </nav>

      <Routes>
        <Route index element={<TaxOverviewPage />} />
        <Route path="settings" element={<TaxSettingsPage />} />
        <Route path="*" element={<Navigate to="/taxes" replace />} />
      </Routes>
    </div>
  );
}
