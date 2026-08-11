const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// The site's own public origin, used for canonical URLs / Open Graph / sitemap.xml —
// distinct from API_URL (the FastAPI backend). Set NEXT_PUBLIC_SITE_URL in production.
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");

export type AgentPerformance = {
  agent_name: string;
  total_actions: number;
  success_rate: number | null;
  avg_latency_ms: number | null;
};

export type MetricsReport = {
  agent_performance: AgentPerformance[];
  api_health: Record<string, { total_calls: number; success_rate: number | null }>;
  digest_stats: {
    digests_sent: number;
    stories_sent: number;
    avg_stories_per_digest: number;
    last_sent: string | null;
    window_days: number;
  };
  quality_metrics: {
    avg_quality_score: number | null;
    avg_fact_check_score: number | null;
    backup_stories_used: number;
    backup_rate: number;
    window_days: number;
  };
};

export type DigestSummary = {
  digest_id: string;
  story_count: number;
  sent_at: string | null;
};

export type ConfigInfo = {
  digest_mode: "daily" | "weekly";
  feed_count: number;
  top_n_stories: number;
  lookback_hours: number;
  base_lookback_hours: number;
};

export type ArticleSummary = {
  id: number;
  headline: string;
  category: string | null;
  summary: string;
  importance_score: number | null;
  // When the story went live on the site (set by publish.py). Independent of the
  // email digest's sent_at - a story can be published here well before, or without
  // ever being, included in an email.
  published_at: string | null;
};

export type PipelineRun = {
  id: number;
  started_at: string;
  finished_at: string | null;
  new_articles: number;
  old_articles_filtered: number;
  feed_errors: number;
  clusters_pending: number;
  clusters_summarized_ok: number;
  clusters_summarized_failed: number;
  publish_candidates: number;
  published_count: number;
  published_ids: number[];
  error_summary: { reason: string; count: number }[];
};

export type ArticleSource = {
  source: string;
  title: string;
  url: string;
  published_at: string | null;
};

export type ArticleDetail = ArticleSummary & {
  full_content: string | null;
  // Written by agents/writer_agent.py alongside full_content: 3-5 standalone bullet
  // facts, distinct from `summary` (the deck). Empty on articles published before this
  // field existed, until the pipeline's self-healing retry backfills them.
  key_takeaways: string[];
  sources: ArticleSource[];
  related: ArticleSummary[];
  // Written by agents/seo_agent.py — null until the SEO agent's next sweep picks
  // this article up (or if all LLM providers were unavailable when it tried).
  seo_title: string | null;
  seo_description: string | null;
  seo_keywords: string | null; // JSON-encoded string[]
};

export type SeoRun = {
  id: number;
  run_at: string;
  articles_checked: number;
  avg_score: number | null;
  issues_found: number;
  trend: number | null;
};

export type SeoOverview = {
  runs: SeoRun[];
  latest_site_issues: string[];
  articles_total: number;
  articles_audited: number;
  articles_pending: number;
};

export type SeoIssue = { severity: "bad" | "warn" | "info"; code: string; message: string };

export type SeoPage = {
  id: number;
  headline: string;
  category: string | null;
  seo_title: string | null;
  seo_description: string | null;
  seo_score: number | null;
  seo_audited_at: string | null;
  issues: SeoIssue[];
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  getMetrics: () => apiFetch<MetricsReport>("/api/metrics"),
  getAgentPerformance: () => apiFetch<AgentPerformance[]>("/api/agents/performance"),
  getDigests: () => apiFetch<DigestSummary[]>("/api/digests"),
  getConfig: () => apiFetch<ConfigInfo>("/api/config"),
  setMode: (mode: "daily" | "weekly") =>
    apiFetch<{ success: boolean; mode?: string }>("/api/config/mode", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  ceoStatus: (detailed = false) =>
    apiFetch<{ report: string }>(`/api/ceo/status?detailed=${detailed}`),
  ceoChat: (question: string) =>
    apiFetch<{ answer: string }>("/api/ceo/chat", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  ceoCommand: (command: string) =>
    apiFetch<{ response: string }>("/api/ceo/command", {
      method: "POST",
      body: JSON.stringify({ command }),
    }),
  getArticles: (category?: string, limit?: number, offset?: number) => {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (limit) params.set("limit", String(limit));
    if (offset) params.set("offset", String(offset));
    const qs = params.toString();
    return apiFetch<ArticleSummary[]>(`/api/articles${qs ? `?${qs}` : ""}`);
  },
  getArticlesCount: (category?: string) => {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    const qs = params.toString();
    return apiFetch<{ total: number }>(`/api/articles/count${qs ? `?${qs}` : ""}`);
  },
  getArticle: (id: number | string) => apiFetch<ArticleDetail | { error: string }>(`/api/articles/${id}`),
  getPipelineRuns: (limit = 20) => apiFetch<PipelineRun[]>(`/api/pipeline/runs?limit=${limit}`),
  getSeoOverview: () => apiFetch<SeoOverview>("/api/seo/overview"),
  getSeoPages: (onlyIssues = false) => apiFetch<SeoPage[]>(`/api/seo/pages?only_issues=${onlyIssues}`),
  runSeoAudit: (limit = 15) => apiFetch<{ checked: number; avg_score: number | null }>(`/api/seo/audit?limit=${limit}`, { method: "POST" }),
};

export { API_URL };
