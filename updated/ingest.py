"""
Stage 1: Ingest.
Pulls every feed in config.FEEDS, inserts new articles into the DB.
Dedup is by URL (UNIQUE constraint) so re-running this is always safe.
"""
from datetime import datetime, timezone
import feedparser
from config import FEEDS
from db import get_connection


def fetch_feeds():
    conn = get_connection()
    new_count = 0
    error_count = 0
    per_source_counts = {}

    for source_name, feed_url in FEEDS:
        source_new = 0
        try:
            parsed = feedparser.parse(feed_url)
            if parsed.bozo and not parsed.entries:
                print(f"  [warn] could not parse {source_name} ({feed_url})")
                error_count += 1
                per_source_counts[source_name] = 0
                continue

            for entry in parsed.entries:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                summary = entry.get("summary", entry.get("description", ""))
                published = entry.get("published", entry.get("updated", ""))

                if not title or not url:
                    continue

                try:
                    conn.execute(
                        """INSERT INTO articles
                           (source, title, url, summary_raw, published_at, fetched_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            source_name,
                            title,
                            url,
                            summary,
                            published,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    new_count += 1
                    source_new += 1
                except Exception:
                    # URL already exists -> already ingested, skip silently
                    pass

            conn.commit()
            per_source_counts[source_name] = source_new
        except Exception as e:
            print(f"  [error] {source_name}: {e}")
            error_count += 1
            per_source_counts[source_name] = 0

    conn.close()
    print("Per-source new article counts:")
    for name, count in per_source_counts.items():
        flag = "  <-- check this feed URL" if count == 0 else ""
        print(f"  {name}: {count}{flag}")
    print(f"Ingest done: {new_count} new articles, {error_count} feed errors.")
    return new_count


if __name__ == "__main__":
    from db import init_db
    init_db()
    fetch_feeds()