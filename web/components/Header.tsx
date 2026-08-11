"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CATEGORIES, categoryBySlug } from "@/lib/categories";

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [currentDate, setCurrentDate] = useState("");

  useEffect(() => {
    const now = new Date();
    setCurrentDate(
      now.toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    );
  }, []);

  const activeCategorySlug = pathname?.startsWith("/category/") ? pathname.split("/")[2] : undefined;
  const activeCategory = activeCategorySlug ? categoryBySlug(activeCategorySlug) : undefined;

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      setSearchOpen(false);
      router.push(`/articles?q=${encodeURIComponent(query.trim())}`);
    }
  }

  return (
    <>
      {/* Top Utility & Ticker Bar */}
      <div className="top-bar">
        <div className="top-bar-inner">
          <div className="top-bar-left">
            <span className="ticker-badge">
              <span className="ticker-pulse" /> LIVE
            </span>
            <span className="ticker-text">
              AI Newsroom pipeline actively ingesting & fact-checking global tech feeds
            </span>
          </div>
          <div className="top-bar-right">
            <span className="top-bar-date">{currentDate}</span>
            <Link href="/articles" className="top-bar-link">
              Newsroom Feed →
            </Link>
          </div>
        </div>
      </div>

      {/* Main Header Masthead */}
      <header className="site-header">
        <div className="site-header-main">
          <Link href="/" className="site-logo">
            <div className="site-logo-mark">AI</div>
            <div className="site-logo-text">
              <span className="site-logo-title">
                AI <span>Daily</span>
              </span>
              <span className="site-logo-tag">The Autonomous AI Newsroom</span>
            </div>
          </Link>

          <div className="site-header-actions">
            <button
              className="search-trigger-btn"
              onClick={() => setSearchOpen(true)}
              aria-label="Search stories"
            >
              <span>🔍</span>
              <span>Search news…</span>
            </button>

            <Link href="/articles" className="header-cta-btn">
              Explore Stories <span>→</span>
            </Link>
          </div>
        </div>

        {/* Category Navigation Bar */}
        <nav className="site-nav">
          <Link href="/" className={pathname === "/" ? "active" : undefined}>
            Home
          </Link>
          {CATEGORIES.map((c) => (
            <Link
              key={c.slug}
              href={`/category/${c.slug}`}
              className={activeCategory?.slug === c.slug ? "active" : undefined}
            >
              {c.label}
            </Link>
          ))}
        </nav>
      </header>

      {/* Instant Search Overlay Modal */}
      {searchOpen && (
        <div className="search-modal-backdrop" onClick={() => setSearchOpen(false)}>
          <div className="search-modal-content" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleSearchSubmit} className="search-modal-input-wrap">
              <span style={{ fontSize: 20, marginRight: 12 }}>🔍</span>
              <input
                type="text"
                autoFocus
                className="search-modal-input"
                placeholder="Search AI Daily stories, funding, research..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button
                type="button"
                onClick={() => setSearchOpen(false)}
                style={{ background: "none", border: "none", fontSize: 18, cursor: "pointer", color: "var(--muted)" }}
              >
                ✕
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
