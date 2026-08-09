"use client";

import { useEffect, useState } from "react";
import { api, AgentPerformance } from "@/lib/api";

export default function AgentsPage() {
  const [rows, setRows] = useState<AgentPerformance[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getAgentPerformance().then(setRows).catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <h2>Agent Performance</h2>
      <p style={{ color: "var(--muted)" }}>Success rate and latency per agent, last 24 hours.</p>
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr><th>Agent</th><th>Actions</th><th>Success Rate</th><th>Avg Latency</th></tr>
        </thead>
        <tbody>
          {rows?.map((r) => (
            <tr key={r.agent_name}>
              <td>{r.agent_name}</td>
              <td>{r.total_actions}</td>
              <td>
                {r.success_rate === null ? "—" : (
                  <span className={`badge ${r.success_rate >= 0.9 ? "good" : r.success_rate >= 0.6 ? "warn" : "bad"}`}>
                    {Math.round(r.success_rate * 100)}%
                  </span>
                )}
              </td>
              <td>{r.avg_latency_ms !== null ? `${r.avg_latency_ms}ms` : "—"}</td>
            </tr>
          ))}
          {rows && rows.length === 0 && <tr><td colSpan={4}>No agent activity logged yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
