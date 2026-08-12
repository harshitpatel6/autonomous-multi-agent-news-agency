"""
Stage 1: Ingest.
Pulls every feed in config.FEEDS, inserts new articles into the DB.
Dedup is by URL (UNIQUE constraint) so re-running this is always safe.
Filters out articles older than LOOKBACK_HOURS AND ABSOLUTE_CUTOFF_DATE.
"""
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import feedparser
import requests
from config import FEEDS, LOOKBACK_HOURS, ABSOLUTE_CUTOFF_DATE
from db import get_connection

# feedparser.parse(url) has no timeout parameter and, given a URL, fetches it itself
# via urllib with none set either - one unresponsive feed can hang the socket read
# forever, freezing this entire step (and everything after it in publish.py) for as
# long as the process happens to live. Fetching with requests first and handing
# feedparser the downloaded bytes gives every feed a hard ceiling instead.
FEED_FETCH_TIMEOUT = 15  # seconds
FEED_FETCH_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIDailyBot/1.0; +https://github.com)"}

# Unlike the LLM calls in summarize.py, these are independent network requests to
# ~250+ different hosts - no shared rate limit to burst past, so concurrency here is
# pure upside: without it, one run's wall-clock ingest time is the *sum* of every
# feed's fetch time (a handful of slow/rsshub-proxy feeds each taking close to
# FEED_FETCH_TIMEOUT adds up to minutes of the rest of the run just waiting). With
# it, it's closer to the *slowest single feed's* fetch time.
FEED_FETCH_WORKERS = 12


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


def extract_rss_image(entry):
    """
    Best-effort lead image straight from the RSS/Atom entry, before we ever hit the
    article page. Many feeds (esp. company blogs) embed this via media:thumbnail,
    media:content, or an image enclosure - checking here first means those never need
    the og:image scrape in utils/fulltext.py at all. Returns "" if none found (most
    feeds, especially GitHub Releases/Atom feeds, don't carry one).
    """
    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail:
        url = media_thumbnail[0].get("url", "")
        if url:
            return url

    media_content = entry.get("media_content")
    if media_content:
        for m in media_content:
            if (m.get("medium") == "image" or (m.get("type") or "").startswith("image/")) and m.get("url"):
                return m["url"]

    for enc in entry.get("enclosures", []):
        if (enc.get("type") or "").startswith("image/") and enc.get("href"):
            return enc["href"]

    return ""


def _fetch_one_feed(source_name, feed_url):
    """Runs in a worker thread: network fetch + parse only, no DB access (sqlite3
    connections aren't safe to share across threads) - insertion happens back on the
    main thread in fetch_feeds() once this returns. Returns (parsed_feed, error_str);
    exactly one of the two is set."""
    try:
        resp = requests.get(feed_url, timeout=FEED_FETCH_TIMEOUT, headers=FEED_FETCH_HEADERS)
        resp.raise_for_status()
        return feedparser.parse(resp.content), None
    except Exception as e:
        return None, str(e)


def fetch_feeds():
    conn = get_connection()
    new_count = 0
    error_count = 0
    old_count = 0
    per_source_counts = {}

    with ThreadPoolExecutor(max_workers=FEED_FETCH_WORKERS) as pool:
        futures = {pool.submit(_fetch_one_feed, name, url): (name, url) for name, url in FEEDS}
        for future in as_completed(futures):
            source_name, feed_url = futures[future]
            source_new = 0
            source_old = 0
            try:
                parsed, fetch_error = future.result()
            except Exception as e:
                parsed, fetch_error = None, str(e)

            if fetch_error is not None:
                print(f"  [error] {source_name}: fetch failed - {fetch_error[:100]}")
                error_count += 1
                per_source_counts[source_name] = (0, 0)
                continue

            if parsed.bozo and not parsed.entries:
                print(f"  [warn] could not parse {source_name} ({feed_url})")
                error_count += 1
                per_source_counts[source_name] = (0, 0)
                continue

            try:
                for entry in parsed.entries:
                    title = entry.get("title", "").strip()
                    url = entry.get("link", "").strip()
                    summary = entry.get("summary", entry.get("description", ""))
                    published = entry.get("published", entry.get("updated", ""))
                    image_url = extract_rss_image(entry)

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
                               (source, title, url, summary_raw, published_at, fetched_at, image_url)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                source_name,
                                title,
                                url,
                                summary,
                                published,
                                datetime.now(timezone.utc).isoformat(),
                                image_url or None,
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
