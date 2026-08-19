"use client";

import { useCallback, useEffect, useState } from "react";
import { api, FailedCluster, ProviderStatus } from "@/lib/api";
import { formatDateTime, timeAgo } from "@/lib/format";

// Same 60s cadence as the runs table above it - fast enough to feel live, slow
// enough not to hammer the API between publish.py's 15-min cycles.
const AUTO_REFRESH_MS = 60_000;

// Per-row status while a "Re-process" click is in flight, so a slow LLM call can't
// be fired twice from an impatient double-click and the row shows what's happening.
type RowState = "idle" | "working" | { error: string };

export default function FailedClustersTable() {
  const [clusters, setClusters] = useState<FailedCluster[] | null>(null);
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rowState, setRowState] = useState<Record<number, RowState>>({});

  const load = useCallback(() => {
    Promise.all([api.getFailedClusters(50), api.getProviderStatus()])
      .then(([c, p]) => {
        setClusters(c);
        setProviders(p);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(load, [load]);
  useEffect(() => {
    const id = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  async function reprocess(id: number) {
    setRowState((s) => ({ ...s, [id]: "working" }));
    try {
      const result = await api.reprocessCluster(id);
      if (result.ok) {
        // Summarized (now or already) - it's no longer "failed", drop it from the list
        // instead of waiting for the next 60s poll.
        setClusters((cur) => (cur ? cur.filter((c) => c.id !== id) : cur));
      } else {
        setRowState((s) => ({ ...s, [id]: { error: result.error } }));
      }
    } catch (e) {
      setRowState((s) => ({ ...s, [id]: { error: String(e) } }));
    }
  }

  const allProvidersDown = providers ? Object.values(providers).every((p) => p.open) : false;

  if (error && !clusters) {
    return <p className="error">Could not load failed clusters: {error}</p>;
  }

  if (clusters && clusters.length === 0) {
    return null; // nothing stuck - don't clutter the page with an empty section
  }

  return (
    <>
      <h3 style={{ marginTop: 32 }}>Clusters needing attention</h3>
      <p style={{ color: "var(--muted)" }}>
        Clusters that failed to summarize and are shown here instead of being retried forever -
        each one already burned an attempt through Claude → Groq → Gemini (see{" "}
        <code>summarize.py</code>). Rows past their automatic-retry budget stop being picked up by
        the 15-min cron on their own; hit <strong>Re-process</strong> to try again by hand. This
        never re-summarizes anything already summarized or already sent in a digest, so clicking
        it is always a single, deliberate LLM call - never a wasted one.
      </p>

      {allProvidersDown && (
        <p className="error" style={{ fontSize: 13 }}>
          ⚠️ All LLM providers are currently rate-limited or cooling down. Re-processing right now
          will fail immediately without spending any tokens (the circuit breaker skips the call) -
          worth waiting before retrying.
        </p>
      )}

      <table>
        <thead>
          <tr>
            <th>Cluster</th>
            <th>Articles</th>
            <th>Attempts</th>
            <th>Last attempt</th>
            <th>Error</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {clusters?.map((c) => {
            const state = rowState[c.id] ?? "idle";
            const working = state === "working";
            return (
              <tr key={c.id}>
                <td style={{ maxWidth: 320 }}>
                  {c.sample_titles[0]?.title ?? `Cluster #${c.id}`}
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    created {timeAgo(c.created_at)}
                    {!c.auto_retry_pending && (
                      <span className="badge warn" style={{ marginLeft: 6, fontSize: 10 }}>
                        needs manual retry
                      </span>
                    )}
                  </div>
                </td>
                <td>{c.article_count}</td>
                <td>{c.summarize_attempts}</td>
                <td>
                  {c.last_summarize_attempt_at ? (
                    <>
                      {formatDateTime(c.last_summarize_attempt_at)}
                      <div style={{ fontSize: 12, color: "var(--muted)" }}>
                        {timeAgo(c.last_summarize_attempt_at)}
                      </div>
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td style={{ maxWidth: 260, fontSize: 12.5, color: "var(--muted)" }}>
                  {c.summarize_error || "—"}
                </td>
                <td>
                  <button className="secondary" disabled={working} onClick={() => reprocess(c.id)}>
                    {working ? "Re-processing…" : "Re-process"}
                  </button>
                  {typeof state === "object" && (
                    <div style={{ fontSize: 11.5, color: "#e5484d", marginTop: 4, maxWidth: 180 }}>
                      {state.error}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
