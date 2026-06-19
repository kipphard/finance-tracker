import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { useTheme } from "../theme";
import { apiPost } from "../api/client";
import type { NetWorthOut, SnapshotOut } from "../api/types";
import { money, num, shortDate } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function NetWorthHero({ className }: { className?: string }) {
  const nw = useApi<NetWorthOut>("/networth");
  const snaps = useApi<SnapshotOut[]>("/networth/snapshots");
  const { grid, axis } = useTheme();
  const [busy, setBusy] = useState(false);

  const snapshot = async () => {
    setBusy(true);
    try {
      await apiPost("/networth/snapshots");
      snaps.reload();
    } finally {
      setBusy(false);
    }
  };

  const data = [...(snaps.data ?? [])]
    .reverse()
    .map((s) => ({ date: shortDate(s.ts), total: num(s.total) }));

  return (
    <Card
      title="Net worth"
      className={className}
      action={
        <button className="btn btn--ghost btn--sm" onClick={snapshot} disabled={busy}>
          {busy ? "…" : "Take snapshot"}
        </button>
      }
    >
      <Async state={nw}>
        {(data0) => (
          <>
            <div className="hero">
              <div className="hero__value tnum">
                {money(data0.total, data0.base_currency)}
              </div>
              <div className="chips" style={{ marginTop: 6 }}>
                {Object.entries(data0.by_currency).map(([cur, amt]) => (
                  <span className="chip" key={cur}>
                    {money(amt, cur)}
                  </span>
                ))}
              </div>
            </div>

            <div style={{ marginTop: 18 }}>
              {data.length < 2 ? (
                <div className="empty">
                  Take snapshots over time to see your net-worth trend ({data.length} so
                  far).
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                    <defs>
                      <linearGradient id="nwFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                    <XAxis dataKey="date" tick={{ fill: axis, fontSize: 12 }} stroke={grid} />
                    <YAxis
                      tick={{ fill: axis, fontSize: 12 }}
                      stroke={grid}
                      width={78}
                      tickFormatter={(v) => money(v)}
                    />
                    <Tooltip
                      formatter={(v: number) => money(v)}
                      contentStyle={{
                        background: "var(--surface)",
                        border: "1px solid var(--border)",
                        borderRadius: 10,
                        color: "var(--text)",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="total"
                      stroke="var(--primary)"
                      strokeWidth={2.5}
                      fill="url(#nwFill)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </>
        )}
      </Async>
    </Card>
  );
}
