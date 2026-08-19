"""
One-time data fix: normalize every existing articles.published_at value to the
same canonical ISO-8601 format ingest.py now writes going forward.

Why this is needed: before this fix, published_at was stored as the feed's raw
date string, so the same column held a mix of RFC-2822 ("Fri, 14 Aug 2026
18:56:45 +0000") and ISO-8601 ("2026-08-14T19:18:00Z") strings. dedup.py and
summarize.py's cleanup_old_articles() both compare this column against an
ISO-8601 cutoff with plain SQL >=/< , which is a lexicographic string compare,
not a date compare - RFC-2822 rows sort as "always newer than the cutoff"
(a letter like 'F' in "Fri, ..." is ASCII-greater than the digit '2' any ISO
cutoff starts with), regardless of true age, so they can never be cleaned up by
age. Rewriting every row to one consistent ISO-8601 format makes that
comparison correct for the whole table, not just rows inserted after the fix.

Safe to re-run: rows already in canonical ISO-8601 form are left untouched.
Run once after deploying the ingest.py fix; not part of the regular pipeline.
"""
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH
from ingest import parse_published_date


def normalize():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, published_at FROM articles").fetchall()

    updated = 0
    unparseable = 0
    for row in rows:
        raw = row["published_at"]
        dt = parse_published_date(raw)
        if dt is None:
            # No usable date on a row that's already in the DB - fall back to
            # "now" like ingest.py does for a fresh insert, rather than leaving
            # a value neither format-parser understands sitting in the column.
            unparseable += 1
            canonical = datetime.now(timezone.utc).isoformat()
        else:
            canonical = dt.isoformat()

        if canonical != raw:
            conn.execute("UPDATE articles SET published_at = ? WHERE id = ?", (canonical, row["id"]))
            updated += 1

    conn.commit()
    conn.close()
    print(f"Checked {len(rows)} articles: normalized {updated}, already-canonical {len(rows) - updated - unparseable}, unparseable/defaulted-to-now {unparseable}")


if __name__ == "__main__":
    normalize()
