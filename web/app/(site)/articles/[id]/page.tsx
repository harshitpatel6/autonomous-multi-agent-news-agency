"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, ArticleDetail } from "@/lib/api";
import { categoryByLabel } from "@/lib/categories";
import { formatDate, readTime } from "@/lib/format";

export default function ArticleDetailPage() {
  const params = useParams();
  const id = params?.id as string;
  const [article, setArticle] = useState<ArticleDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .getArticle(id)
      .then((res) => {
        if ("error" in res) setError("Article not found.");
        else setArticle(res);
      })
      .catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <div className="news-article"><p className="error">{error}</p></div>;
  if (!article) return <div className="news-article"><p className="news-sub">Loading…</p></div>;

  const cat = categoryByLabel(article.category);
  const label = article.category || "Other";

  return (
    <article className="news-article">
      <div className="tag" style={{ color: cat.color }}>{label}</div>
      <h1>{article.headline}</h1>
      <div className="news-byline">
        By the AI Newsroom · {label} Desk · {formatDate(article.sent_at)} ·{" "}
        {readTime(article.full_content, article.summary)}
      </div>

      {article.full_content ? (
        <div className="news-body" dangerouslySetInnerHTML={{ __html: article.full_content }} />
      ) : (
        <p className="news-body-fallback">{article.summary}</p>
      )}

      {article.sources.length > 0 && (
        <div className="news-sources">
          <div className="news-sources-label">Originally reported by</div>
          <ul>
            {article.sources.map((s, i) => (
              <li key={i}>
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  {s.source}
                </a>{" "}
                — {s.title}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="news-agent-note">
        ✨ Researched, written, fact-checked, and edited end-to-end by autonomous AI agents.
      </div>

      {article.related.length > 0 && (
        <div className="news-related">
          <h3>More from {label}</h3>
          <ul>
            {article.related.map((r) => (
              <li key={r.id}>
                <Link href={`/articles/${r.id}`}>{r.headline}</Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Link href="/articles" className="news-back">← All articles</Link>
    </article>
  );
}
