import type { ReactNode } from "react";
import type { ApiState } from "../hooks/useApi";

// Render helper for an async resource: loading / error / data.
export function Async<T>({
  state,
  children,
}: {
  state: ApiState<T>;
  children: (data: T) => ReactNode;
}) {
  if (state.loading && state.data == null) return <div className="muted">Loading…</div>;
  if (state.error) return <div className="error">{state.error}</div>;
  if (state.data == null) return <div className="empty">No data</div>;
  return <>{children(state.data)}</>;
}
