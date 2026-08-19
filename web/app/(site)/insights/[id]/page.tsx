import Link from "next/link";
import type { Metadata } from "next";
import { api, SITE_URL } from "@/lib/api";
import { formatDate } from "@/lib/format";
import ReadingProgressBar from "@/components/ReadingProgressBar";
import ArticleShareBar from "@/components/ArticleShareBar";
import { formatMeta } from "@/components/FeatureCard";

type Props = { params: { id: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const res = await api.getInsight(params.id);
  if ("error" in res) return { title: "Not found" };

  const url = `${SITE_URL}/insights/${res.id}`;
  return {
    title: res.title,
    description: res.teaser,
    alternates: { canonical: url },
    openGraph: { title: res.title, description: res.teaser, url, type: "article" },
  };
}

export default async function InsightDetailPage({ params }: Props) {
  const res = await api.getInsight(params.id);
  if ("error" in res) {
    return (
      <div style={{ maxWidth: 800, margin: "60px auto", textAlign: "center" }}>
        <h2 style={{ fontSize: 24, color: "var(--bad)" }}>Not Found</h2>
        <p style={{ color: "var(--muted)", marginBottom: 24 }}>This piece doesn&apos;t exist (or hasn&apos;t published yet).</p>
        <Link href="/insights" className="header-cta-btn">← Back to the desk</Link>
      </div>
    );
  }

  const feature = res;
  const meta = formatMeta(feature.format);
  const pageUrl = `${SITE_URL}/insights/${feature.id}`;

  return (
    <>
      <ReadingProgressBar />
      <article className="article-layout">
        <header className="article-header">
          <div className="article-breadcrumb">
            <Link href="/">Home</Link>
            <span>/</span>
            <Link href="/insights" style={{ color: meta.color }}>Insights Desk</Link>
            <span>/</span>
            <span>{meta.label}</span>
          </div>

          <div
            style={{
              display: "inline-block", fontSize: 11, fontWeight: 800, textTransform: "uppercase",
              letterSpacing: 1, color: "#fff", background: meta.color, padding: "4px 10px",
              borderRadius: 4, marginBottom: 14,
            }}
          >
            {meta.icon} {meta.label} · Not News — Original Commentary
          </div>

          <h1 className="article-title">{feature.title}</h1>
          {feature.teaser && <div className="article-deck">{feature.teaser}</div>}

          <div className="article-byline-card">
            <div className="byline-left">
              <div className="byline-avatar">AI</div>
              <div className="byline-info">
                <span className="byline-name">Insights Desk</span>
                <span className="byline-meta">Published {formatDate(feature.published_at)}</span>
              </div>
            </div>
          </div>
        </header>

        <div className="article-main-container">
          <ArticleShareBar title={feature.title} url={pageUrl} />

          <div>
            <div className="article-content" dangerouslySetInnerHTML={{ __html: feature.body_html }} />

            {feature.sources.length > 0 && (
              <div className="sources-card">
                <div className="sources-title">
                  {feature.format === "weekly_synthesis" || feature.format === "explainer"
                    ? "From Our Own Coverage This Week"
                    : "Mentioned In This Piece"}
                </div>
                <ul className="sources-list">
                  {feature.sources.map((s, i) => (
                    <li key={i}>
                      <a
                        href={s.url.startsWith("/") ? s.url : s.url}
                        target={s.url.startsWith("/") ? undefined : "_blank"}
                        rel={s.url.startsWith("/") ? undefined : "noopener noreferrer"}
                        className="source-item-link"
                      >
                        <span>🔗</span>
                        <span>{s.name}</span>
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="ai-note-box">
              <span style={{ fontSize: 18 }}>✨</span>
              <span>
                <strong>Autonomous Newsroom Disclosure:</strong> This piece is original commentary/analysis
                written by AI agents for the Insights Desk — not a news report, and not a rewrite of any
                single outside source. It reflects the desk&apos;s own take, checked for tone and factual
                grounding before publishing.
              </span>
            </div>
          </div>
        </div>
      </article>
    </>
  );
}
