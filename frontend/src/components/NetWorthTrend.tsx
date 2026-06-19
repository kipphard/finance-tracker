import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { apiPost } from "../api/client";
import type { SnapshotOut } from "../api/types";
import { money, num, shortDate } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function NetWorthTrend() {
  const state = useApi<SnapshotOut[]>("/networth/snapshots");
  const [busy, setBusy] = useState(false);

  const snapshot = async () => {
    setBusy(true);
    try {
      await apiPost("/networth/snapshots");
      state.reload();
    } finally {
      setBusy(false);
    }
  };

  const action = (
    <button className="btn btn--ghost" onClick={snapshot} disabled={busy}>
      {busy ? "…" : "Take snapshot"}
    </button>
  );

  return (
    <Card title="Net worth trend" action={action}>
      <Async state={state}>
        {(snaps) => {
          if (snaps.length < 2) {
            return (
              <div className="empty">
                Take snapshots over time to build the trend ({snaps.length} so far).
              </div>
            );
          }
          const data = [...snaps]
            .reverse()
            .map((s) => ({ date: shortDate(s.ts), total: num(s.total) }));
          return (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef0f6" />
                <XAxis dataKey="date" fontSize={11} />
                <YAxis fontSize={11} width={72} tickFormatter={(v) => money(v)} />
                <Tooltip formatter={(v: number) => money(v)} />
                <Line type="monotone" dataKey="total" stroke="#4f46e5" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          );
        }}
      </Async>
    </Card>
  );
}
