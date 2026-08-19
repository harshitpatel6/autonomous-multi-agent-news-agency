"use client";

import { useEffect, useState } from "react";
import { api, FeatureSummary, InsightsBrand, InsightFormat } from "@/lib/api";
import FeatureCard, { formatMeta } from "@/components/FeatureCard";

const FORMATS: InsightFormat[] = ["roundup", "explainer", "weekly_synthesis", "opinion", "fun"];

export default function InsightsPage() {
  const [brand, setBrand] = useState<InsightsBrand | null>(null);
  const [features, setFeatures] = useState<FeatureSummary[] | null>(null);
  const [activeFormat, setActiveFormat] = useState<InsightFormat | "All">("All");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getInsightsBrand().then(setBrand).catch(() => setBrand(null));
    api
      .getInsights(undefined, 60)
      .then(setFeatures)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div style={{ padding: 40, color: "var(--bad)" }}>Error loading the desk: {error}</div>;
  if (!features) return <div style={{ padding: "60px 0", textAlign: "center", color: "var(--muted)" }}>Loading…</div>;

  const filtered = activeFormat === "All" ? features : features.filter((f) => f.format === activeFormat);
  const [lead, ...rest] = filtered;

  return (
    <div>
      {/* BRAND HERO - name/tagline/mission chosen entirely by the LLM itself
          (agents/insight_agent.py::get_or_create_brand), never hardcoded here. */}
      <div
        style={{
          background: "linear-gradient(135deg, var(--surface) 0%, var(--surface-alt) 100%)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "40px 40px",
          marginBottom: 40,
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: 1.5, color: "var(--accent)", marginBottom: 8 }}>
          Original coverage · Not News
        </div>
        <h1 style={{ fontFamily: "var(--sans)", fontSize: 38, fontWeight: 800, margin: "0 0 10px 0", letterSpacing: "-0.5px" }}>
          {brand?.name || "✨"}
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 16, margin: "0 0 6px 0", maxWidth: 680, lineHeight: 1.6, fontWeight: 600 }}>
          {brand?.tagline}
        </p>
        <p style={{ color: "var(--muted)", fontSize: 14, margin: 0, maxWidth: 680, lineHeight: 1.6 }}>
          {brand?.mission}
        </p>
        {brand?._pending && (
          <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 10, fontStyle: "italic" }}>
            (Section name still being chosen by the newsroom's AI — refresh shortly.)
          </p>
        )}
      </div>

      {/* FORMAT FILTER CHIPS */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 28 }}>
        <button
          onClick={() => setActiveFormat("All")}
          style={{
            padding: "6px 14px", borderRadius: 999, border: "1px solid var(--border)",
            background: activeFormat === "All" ? "var(--accent)" : "var(--surface)",
            color: activeFormat === "All" ? "#fff" : "var(--text-secondary)",
            fontWeight: 600, fontSize: 13, cursor: "pointer",
          }}
        >
          All
        </button>
        {FORMATS.map((f) => {
          const meta = formatMeta(f);
          return (
            <button
              key={f}
              onClick={() => setActiveFormat(f)}
              style={{
                padding: "6px 14px", borderRadius: 999, border: "1px solid var(--border)",
                background: activeFormat === f ? meta.color : "var(--surface)",
                color: activeFormat === f ? "#fff" : "var(--text-secondary)",
                fontWeight: 600, fontSize: 13, cursor: "pointer",
              }}
            >
              {meta.icon} {meta.label}
            </button>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--muted)" }}>
          Nothing published in this format yet — check back soon.
        </div>
      )}

      {lead && (
        <div style={{ marginBottom: 32 }}>
          <FeatureCard feature={lead} variant="hero" />
        </div>
      )}
      <div className="article-grid">
        {rest.map((f) => (
          <FeatureCard key={f.id} feature={f} />
        ))}
      </div>
    </div>
  );
}
