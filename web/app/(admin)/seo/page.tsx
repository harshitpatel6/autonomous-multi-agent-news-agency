"use client";

import { useEffect, useState } from "react";
import { api, SeoOverview, SeoPage } from "@/lib/api";

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="badge warn">pending</span>;
  const cls = score >= 85 ? "good" : score >= 60 ? "warn" : "bad";
  return <span className={`badge ${cls}`}>{Math.round(score)}</span>;
}

export default function SeoPageAdmin() {
  const [overview, setOverview] = useState<SeoOverview | null>(null);
  const [pages, setPages] = useState<SeoPage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  function load() {
    Promise.all([api.getSeoOverview(), api.getSeoPages()])
      .then(([o, p]) => {
        setOverview(o);
        setPages(p);
      })
      .catch((e) => setError(String(e)));
  }

  useEffect(load, []);

  async function runNow() {
    setRunning(true);
    try {
      await api.runSeoAudit();
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  if (error && !overview) {
    return (
      <div>
        <h2>🔍 SEO</h2>
        <p className="error">Could not reach the API: {error}</p>
      </div>
    );
  }

  const latest = overview?.runs?.[0];

  return (
    <div>
      <h2>
        🔍 SEO Agent
        <button className="secondary" onClick={runNow} disabled={running} style={{ marginLeft: "auto", fontSize: 13 }}>
          {running ? "Auditing…" : "Run audit now"}
        </button>
      </h2>
      <p style={{ color: "var(--muted)" }}>
        Runs automatically every publish cycle (new articles first, then the most stale re-audits) —
        see <code>agents/seo_agent.py</code>. This page is read-only observability, not a control panel.
      </p>

      <div className="card-grid">
        <div className="card">
          <div className="label">📄 Articles audited</div>
          <div className="value">{overview ? `${overview.articles_audited}/${overview.articles_total}` : "—"}</div>
        </div>
        <div className="card">
          <div className="label">⏳ Pending first audit</div>
          <div className="value">{overview?.articles_pending ?? "—"}</div>
        </div>
        <div className="card">
          <div className="label">⭐ Latest avg score</div>
          <div className="value">{latest?.avg_score ?? "—"}</div>
        </div>
        <div className="card">
          <div className="label">📈 Trend vs. previous run</div>
          <div className="value">
            {latest?.trend === null || latest?.trend === undefined
              ? "—"
              : `${latest.trend > 0 ? "+" : ""}${latest.trend}`}
          </div>
        </div>
      </div>

      {overview && overview.latest_site_issues.length > 0 && (
        <>
          <h3>Site-wide issues</h3>
          <ul style={{ margin: 0, paddingLeft: 20, color: "var(--text)", fontSize: 14, lineHeight: 1.9 }}>
            {overview.latest_site_issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        </>
      )}

      {overview && overview.runs.length > 1 && (
        <>
          <h3>Score history (most recent first)</h3>
          <table>
            <thead>
              <tr><th>Run</th><th>Articles checked</th><th>Avg score</th><th>Trend</th></tr>
            </thead>
            <tbody>
              {overview.runs.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.run_at).toLocaleString()}</td>
                  <td>{r.articles_checked}</td>
                  <td><ScoreBadge score={r.avg_score} /></td>
                  <td>{r.trend === null ? "—" : `${r.trend > 0 ? "+" : ""}${r.trend}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h3>Per-article scores</h3>
      <table>
        <thead>
          <tr><th>Headline</th><th>Category</th><th>SEO title</th><th>Score</th><th>Issues</th></tr>
        </thead>
        <tbody>
          {pages?.map((p) => (
            <tr key={p.id}>
              <td style={{ maxWidth: 280 }}>{p.headline}</td>
              <td>{p.category || "—"}</td>
              <td style={{ color: p.seo_title ? "var(--text)" : "var(--muted)", fontStyle: p.seo_title ? "normal" : "italic" }}>
                {p.seo_title || "not generated yet"}
              </td>
              <td><ScoreBadge score={p.seo_score} /></td>
              <td style={{ fontSize: 12.5, color: "var(--muted)" }}>
                {p.issues.length === 0 ? "—" : p.issues.map((i) => i.code).join(", ")}
              </td>
            </tr>
          ))}
          {pages && pages.length === 0 && <tr><td colSpan={5}>No published articles yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
