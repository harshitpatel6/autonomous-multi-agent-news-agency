"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ArticleSummary } from "@/lib/api";
import { categoryBySlug } from "@/lib/categories";
import ArticleCard from "@/components/ArticleCard";

export default function CategoryPage() {
  const params = useParams();
  const slug = params?.slug as string;
  const category = categoryBySlug(slug);

  const [articles, setArticles] = useState<ArticleSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!category) return;
    setArticles(null);
    api.getArticles(category.label, 60).then(setArticles).catch((e) => setError(String(e)));
  }, [category]);

  if (!category) return <p className="error">Unknown category.</p>;

  return (
    <div>
      <div className="category-hero">
        <div className="tag" style={{ color: category.color }}>Section</div>
        <h1>{category.label}</h1>
        <p>{category.blurb}</p>
      </div>

      {error && <p className="error">{error}</p>}
      {!articles && !error && <p className="news-sub">Loading…</p>}
      {articles && articles.length === 0 && <p className="news-sub">No stories in this section yet.</p>}

      <div className="article-grid">
        {articles?.map((a) => (
          <ArticleCard key={a.id} article={a} />
        ))}
      </div>
    </div>
  );
}
