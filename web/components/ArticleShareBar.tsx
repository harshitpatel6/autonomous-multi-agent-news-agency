"use client";

import { useState } from "react";

type Props = {
  title: string;
  url: string;
};

export default function ArticleShareBar({ title, url }: Props) {
  const [copied, setCopied] = useState(false);

  const encodedUrl = encodeURIComponent(url);
  const encodedTitle = encodeURIComponent(title);

  const twitterUrl = `https://twitter.com/intent/tweet?text=${encodedTitle}&url=${encodedUrl}`;
  const linkedinUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`;
  const facebookUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`;

  function handleCopy() {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  }

  return (
    <div className="sticky-share-bar">
      <a
        href={twitterUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="share-btn"
        title="Share on X / Twitter"
      >
        𝕏
      </a>
      <a
        href={linkedinUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="share-btn"
        title="Share on LinkedIn"
      >
        in
      </a>
      <a
        href={facebookUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="share-btn"
        title="Share on Facebook"
      >
        f
      </a>
      <button
        onClick={handleCopy}
        className="share-btn"
        title="Copy Link"
        style={{ position: "relative" }}
      >
        {copied ? "✓" : "🔗"}
      </button>
    </div>
  );
}
