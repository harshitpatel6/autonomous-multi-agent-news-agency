"use client";

import { useState } from "react";

/**
 * Visual signup box matching the reference sites' pattern. There is no subscriber
 * capture backend yet (the pipeline currently emails a single DIGEST_RECIPIENT, not a
 * subscriber list — see config.py), so this intentionally does not pretend to store the
 * email; it says so honestly. Wiring this up to real capture is future work.
 */
export default function NewsletterCTA() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="sidebar-widget newsletter-box">
      <h3>Get the daily digest</h3>
      {submitted ? (
        <p>Thanks! Signups aren&apos;t open to the public yet — check back soon.</p>
      ) : (
        <>
          <p>The day&apos;s most important AI stories, written by our AI newsroom, in your inbox every morning.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted(true);
            }}
          >
            <input
              type="email"
              required
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <button type="submit">Subscribe</button>
          </form>
          <div className="fine-print">No spam. Unsubscribe anytime.</div>
        </>
      )}
    </div>
  );
}
