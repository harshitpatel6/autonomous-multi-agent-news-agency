import Link from "next/link";
import { ArticleSummary } from "@/lib/api";
import { categoryByLabel } from "@/lib/categories";
import { timeAgo, readTime } from "@/lib/format";

type Props = {
  article: ArticleSummary;
  variant?: "hero" | "standard" | "compact" | "trending";
  rank?: number;
};

/** Generates a deterministic high-tech SVG graphic background pattern using category color & article ID */
function ArticleGraphicHeader({ color, label, id }: { color: string; label: string; id: number }) {
  // Deterministic angle & circles based on article ID
  const seed = id * 37;
  const cx1 = (seed * 13) % 80 + 10;
  const cy1 = (seed * 17) % 80 + 10;
  const cx2 = (seed * 23) % 80 + 10;
  const cy2 = (seed * 29) % 80 + 10;

  return (
    <div className="ac-thumb-container">
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 400 225"
        preserveAspectRatio="xMidYMid slice"
        style={{ position: "absolute", inset: 0 }}
      >
        <defs>
          <linearGradient id={`grad-${id}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.8" />
            <stop offset="100%" stopColor="#0f172a" stopOpacity="0.95" />
          </linearGradient>
          <pattern id={`grid-${id}`} width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255, 255, 255, 0.05)" strokeWidth="1" />
          </pattern>
        </defs>

        {/* Background gradient */}
        <rect width="400" height="225" fill={`url(#grad-${id})`} />
        <rect width="400" height="225" fill={`url(#grid-${id})`} />

        {/* Tech abstract vector shapes */}
        <circle cx={`${cx1}%`} cy={`${cy1}%`} r="120" fill={color} opacity="0.25" style={{ filter: "blur(30px)" }} />
        <circle cx={`${cx2}%`} cy={`${cy2}%`} r="80" fill="#60a5fa" opacity="0.15" style={{ filter: "blur(20px)" }} />
        
        {/* Geometric accent lines */}
        <line x1="0" y1="225" x2="400" y2="0" stroke="rgba(255, 255, 255, 0.08)" strokeWidth="1.5" />
        <line x1="0" y1="180" x2="300" y2="0" stroke="rgba(255, 255, 255, 0.05)" strokeWidth="1" />
      </svg>
      <div className="ac-thumb-bg">
        <div className="ac-thumb-overlay" />
        <span className="ac-category-badge">{label}</span>
      </div>
    </div>
  );
}

export default function ArticleCard({ article, variant = "standard", rank }: Props) {
  const cat = categoryByLabel(article.category);
  const label = article.category || "Other";

  // Numbered Trending Rank Variant (TechCrunch / YourStory style)
  if (variant === "trending" && rank !== undefined) {
    return (
      <Link href={`/articles/${article.id}`} className="ac--trending">
        <span className="ac-rank-num">{String(rank).padStart(2, "0")}</span>
        <div className="ac-trending-content">
          <div className="ac-tag" style={{ color: cat.color }}>
            {label}
          </div>
          <h4>{article.headline}</h4>
          <div className="ac-footer-meta" style={{ borderTop: "none", paddingTop: 0 }}>
            <span>{timeAgo(article.published_at)}</span>
          </div>
        </div>
      </Link>
    );
  }

  // Compact List Item
  if (variant === "compact") {
    return (
      <Link href={`/articles/${article.id}`} className="ac ac--compact">
        <div className="ac-body">
          <div className="ac-tag" style={{ color: cat.color }}>
            {label}
          </div>
          <h3>{article.headline}</h3>
          <div className="ac-footer-meta" style={{ borderTop: "none", paddingTop: 0 }}>
            <span>{timeAgo(article.published_at)}</span>
          </div>
        </div>
      </Link>
    );
  }

  // Hero Lead Article Variant
  if (variant === "hero") {
    return (
      <Link href={`/articles/${article.id}`} className="ac ac--hero">
        <ArticleGraphicHeader color={cat.color} label={label} id={article.id} />
        <div className="ac-body">
          <div className="ac-tag" style={{ color: cat.color }}>
            {label}
          </div>
          <h2>{article.headline}</h2>
          <p>{article.summary}</p>
          <div className="ac-footer-meta">
            <div className="ac-author">
              <div className="ac-author-avatar">AI</div>
              <span>AI Newsroom Desk</span>
            </div>
            <span>
              {timeAgo(article.published_at)} · {readTime(null, article.summary)}
            </span>
          </div>
        </div>
      </Link>
    );
  }

  // Standard Grid Article Variant
  return (
    <Link href={`/articles/${article.id}`} className="ac">
      <ArticleGraphicHeader color={cat.color} label={label} id={article.id} />
      <div className="ac-body">
        <div className="ac-tag" style={{ color: cat.color }}>
          {label}
        </div>
        <h3>{article.headline}</h3>
        <p>{article.summary}</p>
        <div className="ac-footer-meta">
          <div className="ac-author">
            <div className="ac-author-avatar">AI</div>
            <span>Reporter Desk</span>
          </div>
          <span>{timeAgo(article.published_at)}</span>
        </div>
      </div>
    </Link>
  );
}
