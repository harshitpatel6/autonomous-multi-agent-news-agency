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


def parse_published_date(published_str):
    """
    Parse a feed entry's published/updated string into an aware UTC datetime.

    Feeds in this project's FEEDS list come in two date flavors: RFC-2822
    (classic RSS <pubDate>, e.g. "Fri, 14 Aug 2026 18:56:45 +0000") and
    ISO-8601 (Atom <updated>/<published>, e.g. "2026-08-14T19:18:00Z" or with
    fractional seconds) - GitHub releases.atom, GitLab's atom.xml, Blogger
    feeds, and Vercel's /atom feed are all ISO-8601.

    Returns None if the string is empty or matches neither format. Callers
    must NOT fail open on None (treat-as-recent) for every caller - that was
    the actual bug here: is_article_recent() used to only try RFC-2822 via
    parsedate_to_datetime, which raises on ISO-8601, and the bare except
    treated every single ISO-dated Atom entry as "recent" regardless of true
    age. Vercel's /atom feed returns its full changelog history, so this
    silently re-admitted ~1450 multi-year-old "new" articles on every single
    15-min run (verified against run.log: same ~1449 count, every run) -
    ingest and cleanup_old_articles() then raced each other pointlessly:
    cleanup's DELETE happens to compare correctly for ISO-vs-ISO strings, so
    it deleted almost the exact same rows right back out next step, making
    every dashboard cycle report "1961 ingested" for near-zero real signal.
    """
    if not published_str:
        return None

    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(published_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        pass

    try:
        dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def is_article_recent(pub_date):
    """
    Check if a parsed published datetime is within LOOKBACK_HOURS AND after
    ABSOLUTE_CUTOFF_DATE. pub_date is the output of parse_published_date():
    an aware datetime, or None if the entry had no date or one in neither
    format this project's feeds actually use - genuinely dateless entries are
    still treated as recent (assume new from the feed), same as before; the
    fix is that this path is now reserved for real "no date" cases instead of
    silently swallowing every unparsed ISO-8601 date too.
    """
    if pub_date is None:
        return True  # No usable date = assume it's recent

    absolute_cutoff = datetime.fromisoformat(ABSOLUTE_CUTOFF_DATE)
    if pub_date < absolute_cutoff:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    return pub_date >= cutoff


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

                    # Filter out old articles. pub_dt is the parsed datetime (or None
                    # for a genuinely dateless entry) - reused below so published_at
                    # is always stored in one canonical ISO-8601 format regardless of
                    # what format the source feed used. Storing the raw feed string
                    # here (the previous behavior) is what let RFC-2822 and ISO-8601
                    # dates mix in the same TEXT column, which every later >=/< date
                    # comparison in dedup.py/summarize.py does as a plain string
                    # comparison - broken in both directions for mixed formats (see
                    # parse_published_date's docstring).
                    pub_dt = parse_published_date(published)
                    if not is_article_recent(pub_dt):
                        source_old += 1
                        old_count += 1
                        continue

                    published_at = pub_dt.isoformat() if pub_dt else datetime.now(timezone.utc).isoformat()

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
                                published_at,
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
