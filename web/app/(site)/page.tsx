"use client";

import { useEffect, useState } from "react";
import { api, ArticleSummary } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import ArticleCard from "@/components/ArticleCard";
import CategorySections from "@/components/CategorySections";
import NewsletterCTA from "@/components/NewsletterCTA";

export default function HomePage() {
  const [articles, setArticles] = useState<ArticleSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getArticles(undefined, 60).then(setArticles).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!articles) return <p className="news-sub">Loading the newsroom…</p>;
  if (articles.length === 0) {
    return <p className="news-sub">No published stories yet — run the pipeline to publish the first digest.</p>;
  }

  const byImportance = [...articles].sort((a, b) => (b.importance_score ?? 0) - (a.importance_score ?? 0));
  const hero = byImportance[0];
  const secondary = byImportance.slice(1, 5);
  const trending = byImportance.slice(0, 6);
  const featuredIds = new Set([hero.id, ...secondary.map((a) => a.id)]);

  return (
    <div>
      <div className="home-top">
        <ArticleCard article={hero} variant="hero" />
        <div className="home-secondary">
          {secondary.map((a) => (
            <ArticleCard key={a.id} article={a} variant="compact" />
          ))}
        </div>
      </div>

      <div className="home-body">
        <div>
          {CATEGORIES.map((cat) => {
            const inCategory = articles.filter((a) => a.category === cat.label && !featuredIds.has(a.id));
            return <CategorySections key={cat.slug} category={cat} articles={inCategory} />;
          })}
        </div>

        <aside>
          <NewsletterCTA />
          <div className="sidebar-widget">
            <h3>Trending</h3>
            {trending.map((a, i) => (
              <ArticleCard key={a.id} article={a} variant="compact" rank={i + 1} />
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
