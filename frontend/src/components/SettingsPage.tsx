import { CategoriesCard } from "./CategoriesCard";

// App-level configuration. (Your freelance business profile lives under Freelance → Settings.)
export function SettingsPage() {
  return (
    <div className="container">
      <div className="page-head">
        <h1>⚙️ Settings</h1>
      </div>
      <CategoriesCard />
      <p className="muted" style={{ fontSize: 13, marginTop: 16 }}>
        Looking for your invoice sender details, IBAN or §19 note? Those live under{" "}
        <b>Freelance → Settings</b>.
      </p>
    </div>
  );
}
