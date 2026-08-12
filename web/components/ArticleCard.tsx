import Link from "next/link";
import { ArticleSummary } from "@/lib/api";
import { categoryByLabel } from "@/lib/categories";
import { timeAgo, readTime } from "@/lib/format";
import ArticleThumb from "./ArticleThumb";

type Props = {
  article: ArticleSummary;
  variant?: "hero" | "standard" | "compact" | "trending";
  rank?: number;
};

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
        <ArticleThumb article={article} color={cat.color} label={label} />
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
      <ArticleThumb article={article} color={cat.color} label={label} />
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
