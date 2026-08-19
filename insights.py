"""
Insights desk job: generates original, non-news editorial content (explainers,
research roundups, weekly synthesis, opinion, and fun/creative formats - see
agents/insight_agent.py's module docstring) and publishes it to the `features` table.

Deliberately a SEPARATE script from publish.py, on its own cadence, rather than folded
into the 15-min news cycle: it doesn't need to run nearly that often (a few pieces a day
is plenty for editorial content, unlike breaking news), and running it independently
means it never competes with the News desk's Reporter/Writer/Fact-Checker calls for the
same per-minute LLM rate limit.

Not currently wired into launchd/cron - run manually (`python insights.py`) or wire up
your own schedule (e.g. a launchd job similar to publish.py's, a few times a day).

Run: python insights.py
"""
from datetime import datetime, timezone

from config import INSIGHTS_PER_RUN
from db import init_db
from agents.insight_agent import insight_agent


def run():
    print("=" * 70)
    print("✨ INSIGHTS DESK - generating original editorial content")
    print("=" * 70)

    init_db()
    started_at = datetime.now(timezone.utc).isoformat()

    brand = insight_agent.get_or_create_brand()
    print(f"\n[1/2] Section brand: \"{brand['name']}\" — {brand.get('tagline', '')}")
    if brand.get("_pending"):
        print("   (LLM unavailable when naming the section — using a temporary placeholder, will retry next run)")

    print(f"\n[2/2] Generating up to {INSIGHTS_PER_RUN} feature(s)...")
    created = insight_agent.run_cycle(INSIGHTS_PER_RUN)

    print(f"\n✅ Published {len(created)} new feature(s): {created}")
    print(f"   (started {started_at})")
    print("=" * 70)
    return created


if __name__ == "__main__":
    run()
