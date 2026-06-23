import { useState } from "react";
import { useAuth } from "../auth";

export function LoginScreen() {
  const { login, startDemo } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | "login" | "demo">(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("login");
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(null);
    }
  };

  const demo = async () => {
    setBusy("demo");
    setError(null);
    try {
      await startDemo();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the demo — try again shortly");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1>💰 Finance Tracker</h1>

        <button className="btn btn--demo" type="button" onClick={demo} disabled={busy !== null}>
          {busy === "demo" ? "Spinning up your sandbox…" : "🚀 Try the live demo"}
        </button>
        <p className="muted" style={{ fontSize: 12, margin: "2px 0 4px" }}>
          A private, throwaway sandbox seeded with sample data. Resets automatically.
        </p>

        <div className="auth-divider"><span>or sign in</span></div>

        <form className="form" onSubmit={submit}>
          <input className="input" type="email" placeholder="Email" value={email}
            onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
          <input className="input" type="password" placeholder="Password" value={password}
            onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
          {error && <div className="error">{error}</div>}
          <button className="btn" type="submit" disabled={busy !== null}>
            {busy === "login" ? "…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
