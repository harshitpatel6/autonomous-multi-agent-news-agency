"use client";

import { useState } from "react";

export default function NewsletterCTA() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="sidebar-widget newsletter-card">
      <div className="sidebar-widget-title">
        <span>⚡ Daily AI Briefing</span>
      </div>
      {submitted ? (
        <p style={{ color: "#4ade80", fontWeight: 600 }}>
          ✓ Welcome to AI Daily! You are on the early reader list.
        </p>
      ) : (
        <>
          <p>
            Get the day&apos;s essential AI breakthroughs, model launches, and funding news delivered to your inbox every morning.
          </p>
          <form
            className="newsletter-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (email.trim()) setSubmitted(true);
            }}
          >
            <input
              type="email"
              required
              className="newsletter-input"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <button type="submit" className="newsletter-submit-btn">
              Subscribe Free
            </button>
          </form>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 10 }}>
            🔒 Zero spam. Unsubscribe anytime.
          </div>
        </>
      )}
    </div>
  );
}
