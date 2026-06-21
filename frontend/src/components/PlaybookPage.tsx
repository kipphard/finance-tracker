import { PlaybookCard } from "./PlaybookCard";

// The money playbook gets its own tab — reference reading, not a daily dashboard card.
export function PlaybookPage() {
  return (
    <div className="container">
      <div className="page-head">
        <h1>🧭 Playbook</h1>
      </div>
      <PlaybookCard />
    </div>
  );
}
