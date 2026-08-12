"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ArticleSummary } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { formatDateTime, timeAgo } from "@/lib/format";

const PAGE_SIZE = 25;
// publish.py runs every 15 minutes (launchd StartInterval), so a poll faster than
// that just re-fetches the same rows - 60s keeps page 1 feeling live without hammering
// the API.
const AUTO_REFRESH_MS = 60_000;

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
