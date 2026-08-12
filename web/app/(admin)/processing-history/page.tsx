"use client";

import { useCallback, useEffect, useState } from "react";
import { api, PipelineRun } from "@/lib/api";
import { formatDateTime, timeAgo } from "@/lib/format";

// publish.py runs every 15 minutes (launchd StartInterval), so a poll faster than
// that just re-fetches the same rows - 60s keeps page 1 feeling live without hammering
// the API.
const AUTO_REFRESH_MS = 60_000;

export default function ProcessingHistoryPage() {
  const [runs, setRuns] = useState<PipelineRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = useCallback(() => {
    api.getPipelineRuns(20).then(setRuns).catch((e) => setError(String(e)));
  }, []);

  useEffect(load, [load]);
  useEffect(() => {
    const id = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  return (
    <div>
      <h2>Processing History</h2>
      <p style={{ color: "var(--muted)" }}>
        What each <code>publish.py</code> run actually did — how many articles it ingested, how
        many clusters it managed to summarize (vs. failed), and why. This is the place to look
        when very few stories publish in a cycle: it&apos;s usually an ingest/summarize bottleneck,
        not a &quot;the RSS feeds went quiet&quot; problem.
      </p>

      {error && <p className="error">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>Run</th>
            <th>Ingested</th>
            <th>Clusters formed</th>
            <th>Summarized</th>
            <th>Candidates</th>
            <th>Published</th>
            <th>Top errors</th>
          </tr>
        </thead>
        <tbody>
          {runs?.map((r) => {
            const summarizedTotal = r.clusters_summarized_ok + r.clusters_summarized_failed;
            const isOpen = expanded === r.id;
            return (
              <tr key={r.id}>
                <td>
                  {formatDateTime(r.started_at)}
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>{timeAgo(r.started_at)}</div>
                </td>
                <td>
                  {r.new_articles}
                  {r.feed_errors > 0 && (
                    <div style={{ fontSize: 12, color: "var(--muted)" }}>{r.feed_errors} feed error(s)</div>
                  )}
                </td>
                <td>{r.clusters_pending}</td>
                <td>
                  {summarizedTotal === 0 ? (
                    "—"
                  ) : (
                    <>
                      <span style={{ color: r.clusters_summarized_ok > 0 ? "inherit" : "var(--muted)" }}>
                        {r.clusters_summarized_ok} ok
                      </span>
                      {r.clusters_summarized_failed > 0 && (
                        <span style={{ color: "#e5484d" }}> / {r.clusters_summarized_failed} failed</span>
                      )}
                    </>
                  )}
                </td>
                <td>{r.publish_candidates}</td>
                <td>{r.published_count}</td>
                <td style={{ maxWidth: 320 }}>
                  {r.error_summary.length === 0 ? (
                    "—"
                  ) : (
                    <>
                      <div>
                        {r.error_summary[0].count}x {r.error_summary[0].reason}
                      </div>
                      {r.error_summary.length > 1 && (
                        <button
                          className="secondary"
                          style={{ fontSize: 11, padding: "2px 8px", marginTop: 4 }}
                          onClick={() => setExpanded(isOpen ? null : r.id)}
                        >
                          {isOpen ? "Hide" : `+${r.error_summary.length - 1} more`}
                        </button>
                      )}
                      {isOpen &&
                        r.error_summary.slice(1).map((e, i) => (
                          <div key={i} style={{ fontSize: 12, color: "var(--muted)" }}>
                            {e.count}x {e.reason}
                          </div>
                        ))}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
          {runs && runs.length === 0 && (
            <tr>
              <td colSpan={7}>No pipeline runs logged yet.</td>
            </tr>
          )}
          {!runs && !error && (
            <tr>
              <td colSpan={7}>Loading…</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
