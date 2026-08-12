"""
One-time backfill for articles/clusters that were fetched before the og:image
scrape in utils/fulltext.py existed (or whose first scrape attempt came up empty) -
see utils/fulltext.py's get_full_text() docstring for why the full_text cache used
to lock in a missing image_url forever. This walks the existing rows once so
already-published articles pick up an image without waiting for a re-publish.

Safe to re-run: articles/clusters that already have an image are skipped.
"""
from agents.writer_agent import _pick_cluster_image
from db import get_connection
from utils.fulltext import get_full_text

def backfill_article_images():
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, url, source FROM articles
           WHERE full_text IS NOT NULL AND (image_url IS NULL OR image_url = '')"""
    ).fetchall()
    conn.close()

    print(f"[articles] {len(rows)} article(s) missing an image, retrying...")
    found = 0
    for row in rows:
        get_full_text(row["id"], row["url"], row["source"])  # self-heals image_url as a side effect
        conn = get_connection()
        got = conn.execute(
            "SELECT image_url FROM articles WHERE id = ?", (row["id"],)
        ).fetchone()["image_url"]
        conn.close()
        if got:
            found += 1
    print(f"[articles] found images for {found}/{len(rows)}")


def backfill_cluster_images():
    conn = get_connection()
    clusters = conn.execute(
        """SELECT id FROM clusters
           WHERE full_content IS NOT NULL AND full_content != ''
             AND (image_url IS NULL OR image_url = '')"""
    ).fetchall()
    conn.close()

    print(f"[clusters] {len(clusters)} published cluster(s) missing an image, re-picking...")
    updated = 0
    for row in clusters:
        image = _pick_cluster_image(row["id"])
        if not image:
            continue
        conn = get_connection()
        conn.execute(
            """UPDATE clusters SET image_url = ?, image_credit = ?, image_credit_url = ?
               WHERE id = ?""",
            (image["image_url"], image["image_credit"], image["image_credit_url"], row["id"]),
        )
        conn.commit()
        conn.close()
        updated += 1
    print(f"[clusters] updated {updated}/{len(clusters)}")


if __name__ == "__main__":
    backfill_article_images()
    backfill_cluster_images()
