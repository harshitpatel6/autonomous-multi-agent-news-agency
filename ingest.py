"""
Stage 1: Ingest.
Pulls every feed in config.FEEDS, inserts new articles into the DB.
Dedup is by URL (UNIQUE constraint) so re-running this is always safe.
Filters out articles older than LOOKBACK_HOURS AND ABSOLUTE_CUTOFF_DATE.
"""
from datetime import datetime, timezone, timedelta
import feedparser
from config import FEEDS, LOOKBACK_HOURS, ABSOLUTE_CUTOFF_DATE
from db import get_connection


def is_article_recent(published_str):
    """
    Check if an article's published date is within LOOKBACK_HOURS AND after ABSOLUTE_CUTOFF_DATE.
    If no published date, treat as recent (assume it's new from the feed).
    """
    if not published_str:
        return True  # No date = assume it's recent
    
    try:
        # Parse the published date (handles multiple formats via feedparser)
        from email.utils import parsedate_to_datetime
        pub_date = parsedate_to_datetime(published_str)
        
        # Make timezone-aware for comparison
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        
        # Check against ABSOLUTE_CUTOFF_DATE first
        absolute_cutoff = datetime.fromisoformat(ABSOLUTE_CUTOFF_DATE)
        if pub_date < absolute_cutoff:
            return False
        
        # Then check against LOOKBACK_HOURS
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
        return pub_date >= cutoff
    except Exception:
        # If parsing fails, treat as recent to be safe
        return True


def fetch_feeds():
    conn = get_connection()
    new_count = 0
    error_count = 0
    old_count = 0
    per_source_counts = {}

    for source_name, feed_url in FEEDS:
        source_new = 0
        source_old = 0
        try:
            parsed = feedparser.parse(feed_url)
            if parsed.bozo and not parsed.entries:
                print(f"  [warn] could not parse {source_name} ({feed_url})")
                error_count += 1
                per_source_counts[source_name] = (0, 0)
                continue

            for entry in parsed.entries:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                summary = entry.get("summary", entry.get("description", ""))
                published = entry.get("published", entry.get("updated", ""))

                if not title or not url:
                    continue
                
                # Filter out old articles
                if not is_article_recent(published):
                    source_old += 1
                    old_count += 1
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
            per_source_counts[source_name] = (source_new, source_old)
        except Exception as e:
            print(f"  [error] {source_name}: {e}")
            error_count += 1
            per_source_counts[source_name] = (0, 0)

    conn.close()
    print("Per-source new article counts (new, old):")
    for name, (new, old) in per_source_counts.items():
        old_flag = f" | {old} old articles filtered" if old > 0 else ""
        print(f"  {name}: {new}{old_flag}")
    print(f"Ingest done: {new_count} new articles, {old_count} old articles filtered, {error_count} feed errors.")
    return {"new": new_count, "old": old_count, "errors": error_count}


if __name__ == "__main__":
    from db import init_db
    init_db()
    fetch_feeds()
