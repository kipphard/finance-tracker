import { CategoriesCard } from "./CategoriesCard";
import { PlaybookCard } from "./PlaybookCard";

// App-level configuration + reference reading. (Your business profile lives under
// Business → Settings.)
export function SettingsPage() {
  return (
    <>
      <CategoriesCard />
      <p className="muted" style={{ fontSize: 13, marginTop: 16 }}>
        Looking for your invoice sender details, IBAN or §19 note? Those live under{" "}
        <b>Business → Settings</b>.
      </p>
      <div style={{ marginTop: 24 }}>
        <PlaybookCard />
      </div>
    </>
  );
}
