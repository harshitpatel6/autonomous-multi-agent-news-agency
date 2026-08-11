import Link from "next/link";
import type { Metadata } from "next";
import { api, SITE_URL } from "@/lib/api";
import { categoryByLabel } from "@/lib/categories";
import { formatDate, formatDateTime, readTime } from "@/lib/format";
import ReadingProgressBar from "@/components/ReadingProgressBar";
import ArticleShareBar from "@/components/ArticleShareBar";
import ArticleCard from "@/components/ArticleCard";

type Props = { params: { id: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const res = await api.getArticle(params.id);
  if ("error" in res) return { title: "Article not found — AI Daily" };

  const title = res.seo_title || res.headline;
  const description = res.seo_description || res.summary;
  const url = `${SITE_URL}/articles/${res.id}`;

  return {
    title: `${title} — AI Daily`,
    description,
    alternates: { canonical: url },
    openGraph: {
      title,
      description,
      url,
      type: "article",
      publishedTime: res.published_at ?? undefined,
      siteName: "AI Daily",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  };
}

export default async function ArticleDetailPage({ params }: Props) {
  const res = await api.getArticle(params.id);
  if ("error" in res) {
    return (
      <div style={{ maxWidth: 800, margin: "60px auto", textAlign: "center" }}>
        <h2 style={{ fontSize: 24, color: "var(--bad)" }}>Article Not Found</h2>
        <p style={{ color: "var(--muted)", marginBottom: 24 }}>
          The requested news article could not be located in the database.
        </p>
        <Link href="/articles" className="header-cta-btn">
          ← Return to Newsroom
        </Link>
      </div>
    );
  }

  const article = res;
  const cat = categoryByLabel(article.category);
  const label = article.category || "Other";
  const pageUrl = `${SITE_URL}/articles/${article.id}`;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: article.headline,
    description: article.seo_description || article.summary,
    articleSection: article.category || undefined,
    datePublished: article.published_at || undefined,
    dateModified: article.published_at || undefined,
    author: { "@type": "Organization", name: "AI Daily Newsroom" },
    publisher: { "@type": "Organization", name: "AI Daily Media" },
    mainEntityOfPage: { "@type": "WebPage", "@id": pageUrl },
  };

  return (
    <>
      <ReadingProgressBar />
      <article className="article-layout">
        <script
          type="application/ld+json"
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />

        {/* ARTICLE HEADER & BREADCRUMBS */}
        <header className="article-header">
          <div className="article-breadcrumb">
            <Link href="/">Home</Link>
            <span>/</span>
            <Link href={`/category/${cat.slug}`} style={{ color: cat.color }}>
              {label}
            </Link>
            <span>/</span>
            <span>Article #{article.id}</span>
          </div>

          <h1 className="article-title">{article.headline}</h1>

          {article.summary && <div className="article-deck">{article.summary}</div>}

          {/* AUTHOR BYLINE CARD */}
          <div className="article-byline-card">
            <div className="byline-left">
              <div className="byline-avatar">AI</div>
              <div className="byline-info">
                <span className="byline-name">AI Newsroom Reporter</span>
                <span className="byline-meta">
                  Published {formatDate(article.published_at)} · {formatDateTime(article.published_at)}
                </span>
              </div>
            </div>
            <div className="byline-pill">
              ⏱ {readTime(article.full_content, article.summary)}
            </div>
          </div>
        </header>

        {/* GENERATIVE HERO COVER HEADER */}
        <div className="article-cover">
          <div
            className="article-cover-bg"
            style={{
              background: `linear-gradient(135deg, ${cat.color} 0%, #0f172a 90%)`,
            }}
          >
            <span className="article-cover-caption">
              ⚡ Autonomous AI Newsroom — Fact-Checked Editorial Coverage
            </span>
          </div>
        </div>

        {/* KEY TAKEAWAYS BOX */}
        {(article.key_takeaways?.length > 0 || article.summary) && (
          <div className="takeaways-box">
            <div className="takeaways-title">
              <span>⚡ Key Takeaways</span>
            </div>
            {article.key_takeaways?.length > 0 ? (
              <ul className="takeaways-list">
                {article.key_takeaways.map((point, i) => (
                  <li key={i}>{point}</li>
                ))}
              </ul>
            ) : (
              <div className="takeaways-body">{article.summary}</div>
            )}
          </div>
        )}

        {/* MAIN BODY WITH STICKY SOCIAL SHARE */}
        <div className="article-main-container">
          <ArticleShareBar title={article.headline} url={pageUrl} />

          <div>
            {article.full_content ? (
              <div
                className="article-content"
                dangerouslySetInnerHTML={{ __html: article.full_content }}
              />
            ) : (
              <div className="article-content">
                <p>{article.summary}</p>
              </div>
            )}

            {/* SOURCES & REFERENCES CARD */}
            {article.sources.length > 0 && (
              <div className="sources-card">
                <div className="sources-title">Originally Reported & Verified By</div>
                <ul className="sources-list">
                  {article.sources.map((s, i) => (
                    <li key={i}>
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="source-item-link"
                      >
                        <span>🔗</span>
                        <span>{s.source}</span>
                      </a>
                      <span style={{ color: "var(--muted)", fontSize: 13.5, marginLeft: 6 }}>
                        — {s.title}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* AI TRANSPARENCY DISCLOSURE */}
            <div className="ai-note-box">
              <span style={{ fontSize: 18 }}>✨</span>
              <span>
                <strong>Autonomous Newsroom Disclosure:</strong> This story was researched, synthesized, written,
                and verified by AI agents. Sources were cross-referenced against multiple industry publications.
              </span>
            </div>
          </div>
        </div>

        {/* RELATED STORIES GRID */}
        {article.related && article.related.length > 0 && (
          <section className="related-section">
            <div className="section-head">
              <div className="section-head-title">
                <span className="section-accent-dot" style={{ background: cat.color }} />
                <h2>More from {label}</h2>
              </div>
              <Link href={`/category/${cat.slug}`}>View desk →</Link>
            </div>
            <div className="article-grid">
              {article.related.map((r) => (
                <ArticleCard key={r.id} article={r} />
              ))}
            </div>
          </section>
        )}

        <div style={{ marginTop: 40, textAlign: "center" }}>
          <Link href="/articles" className="header-cta-btn" style={{ background: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)" }}>
            ← All Published Articles
          </Link>
        </div>
      </article>
    </>
  );
}
