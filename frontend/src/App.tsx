import { HashRouter } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { AppShell } from "./components/AppShell";
import { LoginScreen } from "./components/LoginScreen";

function Root() {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-screen muted">Loading…</div>;
  if (!user) return <LoginScreen />;
  return (
    <HashRouter>
      <AppShell />
    </HashRouter>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}
