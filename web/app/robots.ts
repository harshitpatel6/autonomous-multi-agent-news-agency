import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/api";

// The internal ops dashboard (app/(admin)/) shares this Next app and lives at
// plain root paths like /dashboard, /ceo, /config — nothing about the route
// itself marks them private, so without this they're fully crawlable and
// indexable. That's an internal tool, not site content; keep it out of search.
const ADMIN_PATHS = ["/dashboard", "/history", "/agents", "/digests", "/ceo", "/config", "/seo"];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ADMIN_PATHS }],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
