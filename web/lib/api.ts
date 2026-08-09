const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  sent_at: string | null;
};

export type ArticleSource = {
  source: string;
  title: string;
  url: string;
  published_at: string | null;
};

export type ArticleDetail = ArticleSummary & {
  full_content: string | null;
  sources: ArticleSource[];
  related: ArticleSummary[];
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
  getArticles: (category?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString();
    return apiFetch<ArticleSummary[]>(`/api/articles${qs ? `?${qs}` : ""}`);
  },
  getArticle: (id: number | string) => apiFetch<ArticleDetail | { error: string }>(`/api/articles/${id}`),
};

export { API_URL };
