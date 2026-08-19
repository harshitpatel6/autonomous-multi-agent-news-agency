import Link from "next/link";
import { FeatureSummary, InsightFormat } from "@/lib/api";
import { timeAgo } from "@/lib/format";

// Insights-desk formats (agents/insight_agent.py) - these are structural labels, not
// the section's own brand name (that's chosen by the LLM itself, see
// api.getInsightsBrand / Header.tsx).
const FORMAT_META: Record<InsightFormat, { label: string; color: string; icon: string }> = {
  roundup: { label: "Roundup", color: "#0891b2", icon: "\u{1F9ED}" },
  explainer: { label: "Explainer", color: "#7c3aed", icon: "\u{1F4A1}" },
  weekly_synthesis: { label: "Weekly Synthesis", color: "#2563eb", icon: "\u{1F9F5}" },
  opinion: { label: "Opinion", color: "#dc2626", icon: "\u{1F5E3}️" },
  fun: { label: "Just for Fun", color: "#d97706", icon: "✨" },
};

export function formatMeta(format: InsightFormat) {
  return FORMAT_META[format] ?? { label: format, color: "#6b7280", icon: "✦" };
}

type Props = { feature: FeatureSummary; variant?: "standard" | "hero" };

export default function FeatureCard({ feature, variant = "standard" }: Props) {
  const meta = formatMeta(feature.format);
  const isHero = variant === "hero";

  return (
    <Link href={`/insights/${feature.id}`} className="ac">
      <div style={{ height: 5, background: meta.color, flexShrink: 0 }} />
      <div className="ac-body">
        <div className="ac-tag" style={{ color: meta.color }}>
          {meta.icon} {meta.label}
        </div>
        <h3 style={isHero ? { fontSize: 24, WebkitLineClamp: 3 } : undefined}>{feature.title}</h3>
        <p style={isHero ? { WebkitLineClamp: 4 } : undefined}>{feature.teaser}</p>
        <div className="ac-footer-meta">
          <div className="ac-author">
            <div className="ac-author-avatar">AI</div>
            <span>Insights Desk</span>
          </div>
          <span>{timeAgo(feature.published_at)}</span>
        </div>
      </div>
    </Link>
  );
}
