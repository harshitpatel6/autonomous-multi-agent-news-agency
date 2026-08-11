import type { MetadataRoute } from "next";
import { api, SITE_URL } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";

// Next's file-convention sitemap generator — serves this at /sitemap.xml
// automatically. Static routes always ship even if the API is unreachable at
// request time; article URLs are best-effort so a backend hiccup degrades to a
// smaller sitemap instead of a 500.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [
    { url: SITE_URL, changeFrequency: "hourly", priority: 1 },
    { url: `${SITE_URL}/articles`, changeFrequency: "hourly", priority: 0.8 },
    ...CATEGORIES.map((c) => ({
      url: `${SITE_URL}/category/${c.slug}`,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
  ];

  try {
    const articles = await api.getArticles(undefined, 500);
    for (const a of articles) {
      entries.push({
        url: `${SITE_URL}/articles/${a.id}`,
        lastModified: a.published_at ?? undefined,
        changeFrequency: "weekly",
        priority: 0.6,
      });
    }
  } catch {
    // API unreachable at request time — ship the static routes rather than fail the sitemap entirely.
  }

  return entries;
}
