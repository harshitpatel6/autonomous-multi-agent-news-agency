// Shared date/time formatting helpers for the public site (previously duplicated
// inline in app/articles/page.tsx and app/articles/[id]/page.tsx).
//
// Timestamps from the backend (Python's datetime.isoformat()) already carry an
// explicit UTC offset, e.g. "2026-08-08T15:42:29.829258+00:00" - never a "Z" suffix.
// Only append "Z" when a string genuinely has no timezone designator, otherwise
// `new Date()` gets an invalid string like "...+00:00Z" and silently returns
// Invalid Date, which then renders as "NaNm ago" everywhere below.
function parseUtc(iso: string): Date {
  const hasTimezone = /Z$|[+-]\d{2}:\d{2}$/.test(iso);
  return new Date(hasTimezone ? iso : iso + "Z");
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

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return parseUtc(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function readTime(html: string | null, fallback: string | null): string {
  const text = (html || fallback || "").replace(/<[^>]+>/g, " ");
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return `${Math.max(1, Math.round(words / 200))} min read`;
}
