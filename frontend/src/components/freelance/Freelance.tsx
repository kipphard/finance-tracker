import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { TimePage } from "./TimePage";
import { ClientsPage } from "./ClientsPage";
import { InvoicesPage } from "./InvoicesPage";
import { InvoiceDetail } from "./InvoiceDetail";
import { InsightsPage } from "./InsightsPage";
import { SettingsPage } from "./SettingsPage";

const tabClass = ({ isActive }: { isActive: boolean }) =>
  "subnav__link" + (isActive ? " is-active" : "");

export function Freelance() {
  return (
    <div className="container">
      <div className="page-head">
        <h1>🧑‍💻 Business</h1>
      </div>

      <nav className="subnav">
        <NavLink to="/business" end className={tabClass}>Time</NavLink>
        <NavLink to="/business/clients" className={tabClass}>Clients</NavLink>
        <NavLink to="/business/invoices" className={tabClass}>Invoices</NavLink>
        <NavLink to="/business/insights" className={tabClass}>Insights</NavLink>
        <NavLink to="/business/settings" className={tabClass}>Settings</NavLink>
      </nav>

      <Routes>
        <Route index element={<TimePage />} />
        <Route path="clients" element={<ClientsPage />} />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="invoices/:id" element={<InvoiceDetail />} />
        <Route path="insights" element={<InsightsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/business" replace />} />
      </Routes>
    </div>
  );
}
