// Shared date/time formatting helpers for the public site (previously duplicated
// inline in app/articles/page.tsx and app/articles/[id]/page.tsx).
function parseUtc(iso: string): Date {
  return new Date(iso.endsWith("Z") ? iso : iso + "Z");
}

export function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const mins = Math.floor((Date.now() - parseUtc(iso).getTime()) / 60000);
  if (mins < 60) return `${Math.max(mins, 1)}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return parseUtc(iso).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
}

export function readTime(html: string | null, fallback: string | null): string {
  const text = (html || fallback || "").replace(/<[^>]+>/g, " ");
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return `${Math.max(1, Math.round(words / 200))} min read`;
}
