"use client";

import { useState } from "react";
import { ArticleSummary } from "@/lib/api";

/** Generates a deterministic high-tech SVG graphic background pattern using category color & article ID.
 * Used whenever an article has no real image (image_url is null), or its hotlinked image fails to load
 * (source site went down, blocked hotlinking, URL rotted) - so a card never shows a broken image icon.
 * Also reused (with hideBadge) for the article-detail page's hero cover, so a genuinely imageless story
 * gets the same polished per-article graphic there instead of a flatter, less distinctive gradient. */
export function ArticleGraphicHeader({
  color, label, id, hideBadge,
}: { color: string; label: string; id: number; hideBadge?: boolean }) {
  // Deterministic angle & circles based on article ID
  const seed = id * 37;
  const cx1 = (seed * 13) % 80 + 10;
  const cy1 = (seed * 17) % 80 + 10;
  const cx2 = (seed * 23) % 80 + 10;
  const cy2 = (seed * 29) % 80 + 10;

  return (
    <>
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
        {!hideBadge && <span className="ac-category-badge">{label}</span>}
      </div>
    </>
  );
}

type Props = {
  article: Pick<ArticleSummary, "id" | "image_url" | "image_credit">;
  color: string;
  label: string;
};

/** Real photo pulled from the article's original source (see utils/fulltext.py), with a graceful
 * fallback to the abstract SVG graphic if there's no image, or the hotlink fails to load. */
export default function ArticleThumb({ article, color, label }: Props) {
  const [errored, setErrored] = useState(false);
  const showPhoto = !!article.image_url && !errored;

  return (
    <div className="ac-thumb-container">
      {showPhoto ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={article.image_url!}
            alt=""
            loading="lazy"
            className="ac-thumb-photo"
            onError={() => setErrored(true)}
          />
          <div className="ac-thumb-overlay" />
          <span className="ac-category-badge">{label}</span>
          {article.image_credit && <span className="ac-photo-credit">Photo: {article.image_credit}</span>}
        </>
      ) : (
        <ArticleGraphicHeader color={color} label={label} id={article.id} />
      )}
    </div>
  );
}
