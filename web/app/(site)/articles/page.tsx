"use client";

import { useEffect, useState } from "react";
import { api, ArticleSummary } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import ArticleCard from "@/components/ArticleCard";

export default function ArticlesPage() {
  const [articles, setArticles] = useState<ArticleSummary[] | null>(null);
  const [category, setCategory] = useState("All");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setArticles(null);
    api
      .getArticles(category === "All" ? undefined : category, 60)
      .then(setArticles)
      .catch((e) => setError(String(e)));
  }, [category]);

  const [top, ...rest] = articles || [];

  return (
    <div className="news">
      <div className="news-masthead">
        <div className="news-eyebrow">AI Daily — Newsroom</div>
        <h1>Every story, written and fact-checked by our AI newsroom.</h1>
        <p className="news-sub">
          No human editor in the loop: Reporter → Fact-Checker → Editor → QA agents research,
          write, verify, and publish every article below end to end.
        </p>
      </div>

      <div className="news-filters">
        <button className={category === "All" ? "chip active" : "chip"} onClick={() => setCategory("All")}>
          All
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c.slug}
            className={c.label === category ? "chip active" : "chip"}
            onClick={() => setCategory(c.label)}
          >
            {c.label}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {!articles && !error && <p className="news-sub">Loading articles…</p>}
      {articles && articles.length === 0 && <p className="news-sub">No published articles yet.</p>}

      {top && <ArticleCard article={top} variant="hero" />}

      <div className="article-grid" style={{ marginTop: top ? 28 : 0 }}>
        {rest.map((a) => (
          <ArticleCard key={a.id} article={a} />
        ))}
      </div>
    </div>
  );
}
