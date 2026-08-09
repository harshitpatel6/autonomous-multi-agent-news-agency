// Single source of truth for the site's category taxonomy — used by the header nav,
// category chips, category landing pages, and article card tag colors. Keep this list
// in sync with the enum the Reporter Agent classifies into (agents/reporter_agent.py).
export type Category = {
  label: string;
  slug: string;
  color: string;
  blurb: string;
};

export const CATEGORIES: Category[] = [
  { label: "Company News", slug: "company-news", color: "#2563eb", blurb: "Product launches, partnerships, and moves from the major AI labs." },
  { label: "Business & Enterprise AI", slug: "business-enterprise-ai", color: "#0891b2", blurb: "AI going to work inside real companies — SaaS AI, enterprise tools, adoption." },
  { label: "Funding & Investment", slug: "funding-investment", color: "#16a34a", blurb: "Funding rounds, valuations, M&A, and IPOs across the AI industry." },
  { label: "Startup Launches", slug: "startup-launches", color: "#d97706", blurb: "New AI startups and products making their debut." },
  { label: "Research & Models", slug: "research-models", color: "#7c3aed", blurb: "New models, papers, benchmarks, and technical breakthroughs." },
  { label: "Tools & Engineering", slug: "tools-engineering", color: "#4f46e5", blurb: "Libraries, frameworks, developer tools, and infra releases." },
  { label: "Policy & Regulation", slug: "policy-regulation", color: "#dc2626", blurb: "Government policy, regulation, and legal developments in AI." },
  { label: "Other", slug: "other", color: "#6b7280", blurb: "Everything else worth knowing." },
];

const OTHER = CATEGORIES[CATEGORIES.length - 1];

export function categoryBySlug(slug: string): Category | undefined {
  return CATEGORIES.find((c) => c.slug === slug);
}

export function categoryByLabel(label: string | null | undefined): Category {
  return CATEGORIES.find((c) => c.label === label) ?? OTHER;
}
