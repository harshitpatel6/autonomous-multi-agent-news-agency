"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ArticleSummary, PipelineRun } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { formatDateTime, timeAgo } from "@/lib/format";

const PAGE_SIZE = 25;
// publish.py runs every 15 minutes (launchd StartInterval), so a poll faster than
// that just re-fetches the same rows - 60s keeps page 1 feeling live without hammering
// the API.
const AUTO_REFRESH_MS = 60_000;

function PipelineRunsPanel() {
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
    <div style={{ marginBottom: 36 }}>
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

export default function HistoryPage() {
  const [articles, setArticles] = useState<ArticleSummary[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [category, setCategory] = useState("All");
  const [page, setPage] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const cat = category === "All" ? undefined : category;
    Promise.all([
      api.getArticles(cat, PAGE_SIZE, page * PAGE_SIZE),
      api.getArticlesCount(cat),
    ])
      .then(([items, count]) => {
        setArticles(items);
        setTotal(count.total);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, [category, page]);

  useEffect(() => {
    setArticles(null);
    load();
  }, [load]);

  // Only auto-refresh while looking at the newest page - flipping rows out from
  // under someone reading page 3 would be more annoying than useful.
  useEffect(() => {
    if (page !== 0) return;
    const id = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [page, load]);

  const lastPage = total !== null ? Math.max(0, Math.ceil(total / PAGE_SIZE) - 1) : 0;

  return (
    <div>
      <PipelineRunsPanel />

      <h2>Article History</h2>
      <p style={{ color: "var(--muted)" }}>
        Every story published to the site, newest first. <code>publish.py</code> runs on a
        15-minute cycle, so a new story here means it went live within the last ~15 minutes -
        it does not wait for the twice-daily email digest.
      </p>

      <div className="news-filters" style={{ margin: "16px 0" }}>
        <button
          className={category === "All" ? "chip active" : "chip"}
          onClick={() => {
            setCategory("All");
            setPage(0);
          }}
        >
          All
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c.slug}
            className={c.label === category ? "chip active" : "chip"}
            onClick={() => {
              setCategory(c.label);
              setPage(0);
            }}
          >
            {c.label}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>Headline</th>
            <th>Category</th>
            <th>Score</th>
            <th>Published</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {articles?.map((a) => (
            <tr key={a.id}>
              <td style={{ maxWidth: 420 }}>{a.headline}</td>
              <td>{a.category || "—"}</td>
              <td>{a.importance_score ?? "—"}</td>
              <td>
                {formatDateTime(a.published_at)}
                <div style={{ fontSize: 12, color: "var(--muted)" }}>{timeAgo(a.published_at)}</div>
              </td>
              <td>
                <a href={`/articles/${a.id}`} target="_blank" rel="noreferrer">
                  View →
                </a>
              </td>
            </tr>
          ))}
          {articles && articles.length === 0 && (
            <tr>
              <td colSpan={5}>No published articles yet.</td>
            </tr>
          )}
          {!articles && !error && (
            <tr>
              <td colSpan={5}>Loading…</td>
            </tr>
          )}
        </tbody>
      </table>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16 }}>
        <button className="secondary" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
          ← Newer
        </button>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>
          {total !== null
            ? `Page ${page + 1} of ${lastPage + 1} · ${total} published article${total === 1 ? "" : "s"} total`
            : "…"}
        </span>
        <button className="secondary" disabled={page >= lastPage} onClick={() => setPage((p) => p + 1)}>
          Older →
        </button>
      </div>
    </div>
  );
}
