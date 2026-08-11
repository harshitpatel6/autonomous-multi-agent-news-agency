"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ArticleSummary } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import ArticleCard from "@/components/ArticleCard";
import CategorySections from "@/components/CategorySections";
import NewsletterCTA from "@/components/NewsletterCTA";

export default function HomePage() {
  const [articles, setArticles] = useState<ArticleSummary[] | null>(null);
  const [activeTab, setActiveTab] = useState("All");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getArticles(undefined, 60)
      .then(setArticles)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div style={{ padding: 40, color: "var(--bad)" }}>Error loading newsroom: {error}</div>;
  if (!articles) return <div style={{ padding: "60px 0", textAlign: "center", color: "var(--muted)" }}>Loading the AI Newsroom…</div>;
  if (articles.length === 0) {
    return (
      <div style={{ padding: "60px 0", textAlign: "center", color: "var(--muted)" }}>
        No published stories yet — run the pipeline to publish newsroom digests.
      </div>
    );
  }

  // Sort by importance score for featured hero
  const byImportance = [...articles].sort((a, b) => (b.importance_score ?? 0) - (a.importance_score ?? 0));
  const hero = byImportance[0];
  const secondary = byImportance.slice(1, 5);
  const trending = byImportance.slice(0, 5);

  const featuredIds = new Set([hero.id, ...secondary.map((a) => a.id)]);

  // Filter latest feed based on tab selection
  const filteredLatest =
    activeTab === "All"
      ? articles.filter((a) => !featuredIds.has(a.id))
      : articles.filter((a) => a.category === activeTab);

  return (
    <div>
      {/* TECHCRUNCH / YOURSTORY HERO SPOTLIGHT GRID */}
      <section style={{ marginBottom: 48 }}>
        <div className="home-hero-grid">
          {/* Main Hero Featured Article */}
          <ArticleCard article={hero} variant="hero" />

          {/* Sub-featured 2x2 Grid */}
          <div className="home-secondary-grid">
            {secondary.map((a) => (
              <ArticleCard key={a.id} article={a} />
            ))}
          </div>
        </div>
      </section>

      {/* MAIN CONTENT SPLIT LAYOUT */}
      <div className="home-body-split">
        {/* LEFT COLUMN: LATEST STORIES FEED & SPOTLIGHTS */}
        <div>
          {/* Latest Feed Header & Category Filter Tabs */}
          <div className="section-head">
            <div className="section-head-title">
              <span className="section-accent-dot" />
              <h2>Latest Stories</h2>
            </div>
            <Link href="/articles">Browse all ({articles.length}) →</Link>
          </div>

          {/* Category Filter Chips */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 28 }}>
            <button
              onClick={() => setActiveTab("All")}
              style={{
                padding: "6px 14px",
                borderRadius: 999,
                border: "1px solid var(--border)",
                background: activeTab === "All" ? "var(--accent)" : "var(--surface)",
                color: activeTab === "All" ? "#fff" : "var(--text-secondary)",
                fontWeight: 600,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              All News
            </button>
            {CATEGORIES.slice(0, 5).map((c) => (
              <button
                key={c.slug}
                onClick={() => setActiveTab(c.label)}
                style={{
                  padding: "6px 14px",
                  borderRadius: 999,
                  border: "1px solid var(--border)",
                  background: activeTab === c.label ? "var(--accent)" : "var(--surface)",
                  color: activeTab === c.label ? "#fff" : "var(--text-secondary)",
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                {c.label}
              </button>
            ))}
          </div>

          {/* Feed Grid */}
          <div className="article-grid" style={{ marginBottom: 48 }}>
            {filteredLatest.slice(0, 9).map((a) => (
              <ArticleCard key={a.id} article={a} />
            ))}
          </div>

          {/* CATEGORY SPOTLIGHT SECTIONS */}
          {CATEGORIES.slice(0, 4).map((cat) => {
            const categoryArticles = articles.filter((a) => a.category === cat.label && !featuredIds.has(a.id));
            return <CategorySections key={cat.slug} category={cat} articles={categoryArticles} max={3} />;
          })}
        </div>

        {/* RIGHT SIDEBAR: TRENDING RANKINGS & NEWSLETTER */}
        <aside>
          {/* Newsletter Box */}
          <NewsletterCTA />

          {/* TechCrunch / YourStory Style Numbered Trending List */}
          <div className="sidebar-widget">
            <div className="sidebar-widget-title">
              <span>🔥 Top Trending</span>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>Live</span>
            </div>
            <div>
              {trending.map((a, i) => (
                <ArticleCard key={a.id} article={a} variant="trending" rank={i + 1} />
              ))}
            </div>
          </div>

          {/* Categories Quick Jump Card */}
          <div className="sidebar-widget">
            <div className="sidebar-widget-title">
              <span>Explore Desks</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {CATEGORIES.map((c) => (
                <Link
                  key={c.slug}
                  href={`/category/${c.slug}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "var(--surface-alt)",
                    fontSize: 13.5,
                    fontWeight: 600,
                    color: "var(--text)",
                    textDecoration: "none",
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: c.color }} />
                    {c.label}
                  </span>
                  <span style={{ color: "var(--muted)", fontSize: 12 }}>→</span>
                </Link>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
