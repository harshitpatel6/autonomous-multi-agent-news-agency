"""
One-time (re-runnable) audit + fix for already-published articles that predate the
originality guardrail (utils/similarity.py - see config.py's SIMILARITY_* comment for
the article-537 backstory). Scans every published cluster with full_content, flags the
ones that fail the same strict gate agents/writer_agent.py now enforces on new stories,
and regenerates them through that (now content-type-aware, self-checking) Writer Agent
path - clearing the cached full_content/key_takeaways first so ensure_full_article()
does a real rewrite instead of its normal no-op (it early-returns once both columns are
already populated).

A cluster that still can't clear the gate after MAX_ORIGINALITY_REWRITE_ATTEMPTS internal
tries is left with full_content/key_takeaways NULL - not re-published with old content,
and not deleted. The article page falls back to rendering the short `summary` until
publish.py's normal retry_missing_full_content self-heals it on a later cycle.

Run: python rewrite_at_risk_articles.py [--limit N] [--dry-run]
"""
import argparse
import time
from datetime import datetime, timezone

from db import init_db, get_connection
from utils.textclean import strip_html
from utils.similarity import similarity_report
from agents.writer_agent import ensure_full_article

RATE_LIMIT_DELAY = 0.5  # mirrors summarize.py's pacing between LLM calls


def find_at_risk(limit=None):
    """Read-only scan (no LLM calls) - deterministic, so safe to run as often as wanted."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, full_content FROM clusters
        WHERE published_at IS NOT NULL AND full_content IS NOT NULL
        ORDER BY published_at ASC
    """).fetchall()

    at_risk = []
    for r in rows:
        articles = conn.execute(
            "SELECT full_text FROM articles WHERE cluster_id = ?", (r["id"],)
        ).fetchall()
        source_texts = [a["full_text"] for a in articles if a["full_text"]]
        if not source_texts:
            continue  # nothing to compare against (all sources were TEASER ONLY) - can't judge this one
        report = similarity_report(strip_html(r["full_content"]), source_texts)
        if report["flagged"]:
            at_risk.append({"id": r["id"], "score": report["score"], "max_run": report["max_verbatim_run_words"]})
        if limit and len(at_risk) >= limit:
            break
    conn.close()
    return at_risk


def rewrite_cluster(cluster_id: int) -> str:
    conn = get_connection()
    cluster = conn.execute(
        "SELECT id, headline, category, summary, importance_score, content_type FROM clusters WHERE id = ?",
        (cluster_id,),
    ).fetchone()
    conn.close()
    if not cluster:
        return "not found"

    conn = get_connection()
    conn.execute("UPDATE clusters SET full_content = NULL, key_takeaways = NULL WHERE id = ?", (cluster_id,))
    conn.commit()
    conn.close()

    ok = ensure_full_article(dict(cluster))
    return "rewritten" if ok else "failed"


def run(limit=None, dry_run=False):
    init_db()
    print("=" * 70)
    print("🔍 Scanning published corpus for near-copy articles (utils/similarity.py)")
    print("=" * 70)
    at_risk = find_at_risk(limit=limit)
    print(f"\nFound {len(at_risk)} at-risk article(s) out of the checked corpus.")

    if dry_run:
        for a in at_risk:
            print(f"  - cluster {a['id']}: score={a['score']:.2f}, longest verbatim run={a['max_run']} words")
        return at_risk

    if not at_risk:
        print("Nothing to rewrite.")
        return at_risk

    print("\nRewriting through the Writer Agent's originality-gated path...")
    results = {"rewritten": 0, "failed": 0}
    for i, a in enumerate(at_risk, 1):
        outcome = rewrite_cluster(a["id"])
        results[outcome] = results.get(outcome, 0) + 1
        print(f"  [{i}/{len(at_risk)}] cluster {a['id']} (was score={a['score']:.2f}, run={a['max_run']}w) -> {outcome}")
        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n✅ Done. Rewritten: {results.get('rewritten', 0)}, still failed: {results.get('failed', 0)}")
    if results.get("failed"):
        print("   (failed ones are left without full_content - not republished with the old copy - and")
        print("    self-heal on a later publish.py cycle via retry_missing_full_content)")
    return at_risk


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="cap how many at-risk articles to process")
    parser.add_argument("--dry-run", action="store_true", help="scan and report only, no rewrites")
    args = parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run)
