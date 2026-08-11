"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api, ArticleSummary } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import ArticleCard from "@/components/ArticleCard";

const PAGE_SIZE = 30;

function ArticlesContent() {
  const searchParams = useSearchParams();
  const searchQuery = searchParams.get("q") || "";

  const [articles, setArticles] = useState<ArticleSummary[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [category, setCategory] = useState("All");
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setArticles(null);
    setTotal(null);
    const cat = category === "All" ? undefined : category;
    Promise.all([api.getArticles(cat, PAGE_SIZE, 0), api.getArticlesCount(cat)])
      .then(([items, count]) => {
        setArticles(items);
        setTotal(count.total);
      })
      .catch((e) => setError(String(e)));
  }, [category]);

  function loadMore() {
    if (!articles) return;
    setLoadingMore(true);
    const cat = category === "All" ? undefined : category;
    api
      .getArticles(cat, PAGE_SIZE, articles.length)
      .then((more) => setArticles([...articles, ...more]))
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingMore(false));
  }

  // If URL has search query, filter client-side
  const displayedArticles =
    searchQuery && articles
      ? articles.filter(
          (a) =>
            a.headline.toLowerCase().includes(searchQuery.toLowerCase()) ||
            a.summary.toLowerCase().includes(searchQuery.toLowerCase())
        )
      : articles;

  const [top, ...rest] = displayedArticles || [];
  const hasMore = total !== null && articles !== null && articles.length < total;

  return (
    <div>
      {/* MASTHEAD BANNER */}
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "32px 36px",
          marginBottom: 32,
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: 1.5,
            color: "var(--accent)",
            marginBottom: 8,
          }}
        >
          AI Daily — Newsroom Archives
        </div>
        <h1 style={{ fontFamily: "var(--sans)", fontSize: 32, fontWeight: 800, margin: "0 0 12px 0", letterSpacing: "-0.5px" }}>
          {searchQuery ? `Search Results for "${searchQuery}"` : "Every Story, Fact-Checked & Verified"}
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 15, margin: 0, maxWidth: 640, lineHeight: 1.6 }}>
          Explore autonomous AI newsroom reporting. Filter by desk below or search for specific AI companies, model releases, and research.
        </p>
      </div>

      {/* CATEGORY CHIPS */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 32 }}>
        <button
          onClick={() => setCategory("All")}
          style={{
            padding: "8px 18px",
            borderRadius: 999,
            border: "1px solid var(--border)",
            background: category === "All" ? "var(--accent)" : "var(--surface)",
            color: category === "All" ? "#fff" : "var(--text-secondary)",
            fontWeight: 700,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          All Desks
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c.slug}
            onClick={() => setCategory(c.label)}
            style={{
              padding: "8px 18px",
              borderRadius: 999,
              border: "1px solid var(--border)",
              background: category === c.label ? "var(--accent)" : "var(--surface)",
              color: category === c.label ? "#fff" : "var(--text-secondary)",
              fontWeight: 700,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            {c.label}
          </button>
        ))}
      </div>

      {error && <div style={{ color: "var(--bad)", padding: 20 }}>{error}</div>}
      {!articles && !error && <div style={{ textAlign: "center", padding: "60px 0", color: "var(--muted)" }}>Loading articles…</div>}
      {articles && displayedArticles && displayedArticles.length === 0 && (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--muted)" }}>
          No published stories found matching your criteria.
        </div>
      )}

      {top && !searchQuery && <ArticleCard article={top} variant="hero" />}

      <div className="article-grid" style={{ marginTop: top ? 28 : 0 }}>
        {(searchQuery ? displayedArticles : rest)?.map((a) => (
          <ArticleCard key={a.id} article={a} />
        ))}
      </div>

      {articles && total !== null && !searchQuery && (
        <div style={{ textAlign: "center", marginTop: 44 }}>
          {hasMore ? (
            <button
              onClick={loadMore}
              disabled={loadingMore}
              className="header-cta-btn"
              style={{ background: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)", padding: "12px 28px" }}
            >
              {loadingMore ? "Loading more stories…" : `Load More Stories (${total - articles.length} remaining)`}
            </button>
          ) : (
            <p style={{ color: "var(--muted)", fontSize: 14 }}>
              All {total} published article{total === 1 ? "" : "s"} loaded.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function ArticlesPage() {
  return (
    <Suspense fallback={<div style={{ textAlign: "center", padding: 60 }}>Loading newsroom…</div>}>
      <ArticlesContent />
    </Suspense>
  );
}
