"use client";

import { useEffect, useRef, useState } from "react";
import { api, API_URL, MetricsReport } from "@/lib/api";

export default function DashboardHome() {
  const [metrics, setMetrics] = useState<MetricsReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Initial load over plain HTTP so the page renders even if WS is unavailable.
  useEffect(() => {
    api.getMetrics().then(setMetrics).catch((e) => setError(String(e)));
  }, []);

  // Real-time updates (Task 5.4): the backend pushes a fresh snapshot every few seconds.
  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, "ws") + "/ws/metrics?interval_seconds=10";
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => setLive(true);
    ws.onclose = () => setLive(false);
    ws.onerror = () => setLive(false);
    ws.onmessage = (event) => {
      try {
        setMetrics(JSON.parse(event.data));
      } catch {
        /* ignore malformed frame */
      }
    };
    return () => ws.close();
  }, []);

  if (error && !metrics) {
    return (
      <div>
        <h2>Overview</h2>
        <p className="error">Could not reach the API at {API_URL}: {error}</p>
        <p>Start the backend with: <code>uvicorn api.main:app --reload</code></p>
      </div>
    );
  }

  const digestStats = metrics?.digest_stats;
  const quality = metrics?.quality_metrics;

  return (
    <div>
      <h2>Overview {live && <span className="badge good">live</span>}</h2>

      <div className="card-grid">
        <div className="card">
          <div className="label">📬 Digests sent ({digestStats?.window_days ?? 7}d)</div>
          <div className="value">{digestStats?.digests_sent ?? "—"}</div>
        </div>
        <div className="card">
          <div className="label">📰 Stories delivered</div>
          <div className="value">{digestStats?.stories_sent ?? "—"}</div>
        </div>
        <div className="card">
          <div className="label">⭐ Avg quality score</div>
          <div className="value">{quality?.avg_quality_score ?? "n/a"}</div>
        </div>
        <div className="card">
          <div className="label">🔁 Backup story rate</div>
          <div className="value">{quality ? `${Math.round(quality.backup_rate * 100)}%` : "—"}</div>
        </div>
      </div>

      <h3>API Health</h3>
      <table>
        <thead>
          <tr><th>Provider</th><th>Calls</th><th>Success Rate</th></tr>
        </thead>
        <tbody>
          {metrics && Object.entries(metrics.api_health).map(([provider, h]) => (
            <tr key={provider}>
              <td>{provider}</td>
              <td>{h.total_calls}</td>
              <td>
                <StatusBadge rate={h.success_rate} />
              </td>
            </tr>
          ))}
          {metrics && Object.keys(metrics.api_health).length === 0 && (
            <tr><td colSpan={3}>No LLM calls logged yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ rate }: { rate: number | null }) {
  if (rate === null) return <span className="badge warn">no data</span>;
  const cls = rate >= 0.9 ? "good" : rate >= 0.6 ? "warn" : "bad";
  return <span className={`badge ${cls}`}>{Math.round(rate * 100)}%</span>;
}
