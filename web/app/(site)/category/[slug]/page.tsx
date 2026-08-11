import type { Metadata } from "next";
import Link from "next/link";
import { api, SITE_URL } from "@/lib/api";
import { categoryBySlug } from "@/lib/categories";
import ArticleCard from "@/components/ArticleCard";

type Props = { params: { slug: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const category = categoryBySlug(params.slug);
  if (!category) return { title: "Section Not Found — AI Daily" };

  const url = `${SITE_URL}/category/${category.slug}`;
  return {
    title: `${category.label} — AI Daily`,
    description: category.blurb,
    alternates: { canonical: url },
    openGraph: { title: `${category.label} — AI Daily`, description: category.blurb, url, siteName: "AI Daily" },
  };
}

export default async function CategoryPage({ params }: Props) {
  const category = categoryBySlug(params.slug);
  if (!category) {
    return (
      <div style={{ textAlign: "center", padding: "60px 0" }}>
        <h2>Section Not Found</h2>
        <Link href="/" className="header-cta-btn">← Return to Homepage</Link>
      </div>
    );
  }

  let articles: Awaited<ReturnType<typeof api.getArticles>> | null = null;
  let error: string | null = null;
  try {
    articles = await api.getArticles(category.label, 60);
  } catch (e) {
    error = String(e);
  }

  const [lead, ...rest] = articles || [];

  return (
    <div>
      {/* CATEGORY HERO BANNER */}
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderLeft: `6px solid ${category.color}`,
          borderRadius: "var(--radius-lg)",
          padding: "36px 40px",
          marginBottom: 40,
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: 1.5, color: category.color, marginBottom: 8 }}>
          News Desk Section
        </div>
        <h1 style={{ fontFamily: "var(--sans)", fontSize: 36, fontWeight: 800, margin: "0 0 12px 0", letterSpacing: "-0.5px" }}>
          {category.label}
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 16, margin: 0, maxWidth: 680, lineHeight: 1.6 }}>
          {category.blurb}
        </p>
      </div>

      {error && <div style={{ color: "var(--bad)", padding: 20 }}>{error}</div>}
      {articles && articles.length === 0 && (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--muted)" }}>
          No published stories in this desk section yet. Check back soon for automated updates.
        </div>
      )}

      {lead && <ArticleCard article={lead} variant="hero" />}

      <div className="article-grid" style={{ marginTop: lead ? 32 : 0 }}>
        {rest?.map((a) => (
          <ArticleCard key={a.id} article={a} />
        ))}
      </div>
    </div>
  );
}
