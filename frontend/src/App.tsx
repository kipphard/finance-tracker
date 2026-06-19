import { AuthProvider, useAuth } from "./auth";
import { Dashboard } from "./components/Dashboard";
import { LoginScreen } from "./components/LoginScreen";

function Root() {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-screen muted">Loading…</div>;
  return user ? <Dashboard /> : <LoginScreen />;
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}
