import Link from "next/link";
import { ArticleSummary } from "@/lib/api";
import { categoryByLabel } from "@/lib/categories";
import { timeAgo } from "@/lib/format";

type Props = {
  article: ArticleSummary;
  variant?: "hero" | "standard" | "compact";
  rank?: number;
};

/**
 * No feed currently supplies article images (see plan), so the thumbnail is a
 * deterministic gradient in the article's category color rather than a photo —
 * consistent, on-brand, and never broken/misleading.
 */
function Thumb({ color, label }: { color: string; label: string }) {
  return (
    <div className="ac-thumb" style={{ background: `linear-gradient(135deg, ${color} 0%, #11131a 160%)` }}>
      <span className="ac-thumb-label">{label}</span>
    </div>
  );
}

export default function ArticleCard({ article, variant = "standard", rank }: Props) {
  // categoryByLabel only supplies a color/fallback — the displayed text is always the
  // article's actual category string, so older rows (e.g. a since-renamed category)
  // still show their real label instead of silently becoming "Other".
  const cat = categoryByLabel(article.category);
  const label = article.category || "Other";
  const className = variant === "hero" ? "ac ac--hero" : variant === "compact" ? "ac ac--compact" : "ac";

  return (
    <Link href={`/articles/${article.id}`} className={className}>
      {variant !== "compact" && <Thumb color={cat.color} label={label} />}
      <div className="ac-body">
        {variant === "compact" && rank !== undefined ? (
          <span className="ac-rank">{String(rank).padStart(2, "0")}</span>
        ) : (
          <div className="tag" style={{ color: cat.color }}>{label}</div>
        )}
        {variant === "hero" ? <h2>{article.headline}</h2> : <h3>{article.headline}</h3>}
        <p>{article.summary}</p>
        <div className="ac-meta">{timeAgo(article.sent_at)}</div>
      </div>
    </Link>
  );
}
