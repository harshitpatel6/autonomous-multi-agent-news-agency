"use client";

import Link from "next/link";
import { CATEGORIES } from "@/lib/categories";
import { useState } from "react";

export default function Footer() {
  const year = new Date().getFullYear();
  const [email, setEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleSubscribe(e: React.FormEvent) {
    e.preventDefault();
    if (email.trim()) {
      setSubscribed(true);
    }
  }

  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="site-footer-grid">
          {/* Brand Column */}
          <div className="footer-brand">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  background: "linear-gradient(135deg, #2563eb, #7c3aed)",
                  borderRadius: 8,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  fontWeight: 900,
                  fontSize: 15,
                }}
              >
                AI
              </div>
              <span style={{ fontSize: 20, fontWeight: 800, color: "#fff" }}>
                AI <span style={{ color: "#60a5fa" }}>Daily</span>
              </span>
            </div>
            <p>
              The world&apos;s first digital tech publication powered by autonomous AI agents.
              Every article is researched, written, fact-checked, and edited 24/7 without human intervention.
            </p>
          </div>

          {/* Sections Column 1 */}
          <div className="footer-col">
            <h4>Sections</h4>
            {CATEGORIES.slice(0, 4).map((c) => (
              <Link key={c.slug} href={`/category/${c.slug}`}>
                {c.label}
              </Link>
            ))}
          </div>

          {/* Sections Column 2 */}
          <div className="footer-col">
            <h4>Coverage</h4>
            {CATEGORIES.slice(4).map((c) => (
              <Link key={c.slug} href={`/category/${c.slug}`}>
                {c.label}
              </Link>
            ))}
          </div>

          {/* Newsletter Column */}
          <div className="footer-col">
            <h4>Daily Dispatch</h4>
            <p style={{ fontSize: 13, color: "#94a3b8", marginBottom: 14 }}>
              Get our top AI story breakings delivered to your inbox each morning.
            </p>
            {subscribed ? (
              <p style={{ color: "#4ade80", fontSize: 13, fontWeight: 600 }}>
                ✓ Subscribed! You will receive daily newsroom digests.
              </p>
            ) : (
              <form onSubmit={handleSubscribe} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input
                  type="email"
                  required
                  placeholder="Enter your work email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 6,
                    border: "1px solid #334155",
                    background: "#020617",
                    color: "#fff",
                    fontSize: 13,
                  }}
                />
                <button
                  type="submit"
                  style={{
                    padding: "9px",
                    borderRadius: 6,
                    border: "none",
                    background: "#2563eb",
                    color: "#fff",
                    fontWeight: 700,
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  Subscribe Free
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Footer Bottom */}
        <div className="footer-bottom">
          <span>© {year} AI Daily Media. All rights reserved.</span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 8, height: 8, background: "#10b981", borderRadius: "50%" }} />
            AI Newsroom Status: Online & Publishing
          </span>
          <button onClick={scrollToTop} className="back-to-top-btn">
            Back to Top ↑
          </button>
        </div>
      </div>
    </footer>
  );
}
