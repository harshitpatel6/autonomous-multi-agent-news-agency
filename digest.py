"""
Stage 4: Build digest using Multi-Agent System
Agents validate, curate, and format the newsletter
"""
from datetime import date, datetime, timezone
from config import DB_PATH, SITE_BASE_URL
from db import get_connection

# Import agent coordinator and state manager
try:
    from agents.agent_coordinator import coordinator
    from agents.state_manager import StateManager
    from agents.qa_agent import qa_agent
    from agents.editor_agent import editor_agent
    from agents.writer_agent import ensure_full_article
    from agents.fact_checker_agent import fact_checker_agent
    AGENTS_AVAILABLE = True
except ImportError:
    AGENTS_AVAILABLE = False
    print("⚠️  Agent system not available, using fallback mode")

# Initialize state manager
state_manager = StateManager()

HTML_WRAPPER = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      line-height: 1.6;
      color: #1a1a1a;
      max-width: 680px;
      margin: 0 auto;
      padding: 0;
      background-color: #f4f5f7;
    }}
    .wrap {{
      background-color: #ffffff;
    }}
    .header {{
      background: linear-gradient(135deg, #4338ca 0%, #6d28d9 100%);
      padding: 36px 28px 28px;
      color: #ffffff;
    }}
    .header .eyebrow {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      opacity: 0.85;
      margin: 0 0 10px 0;
    }}
    .header h1 {{
      font-size: 30px;
      font-weight: 800;
      margin: 0 0 10px 0;
      letter-spacing: -0.5px;
      color: #ffffff;
    }}
    .header .date {{
      font-size: 14px;
      opacity: 0.9;
      font-weight: 500;
    }}
    .agent-badge {{
      display: inline-block;
      font-size: 11px;
      color: #ffffff;
      margin-top: 12px;
      background: rgba(255,255,255,0.18);
      padding: 4px 10px;
      border-radius: 999px;
    }}
    .hero {{
      margin: 0;
      padding: 24px 28px;
      background: #fafaff;
      border-bottom: 1px solid #eceefb;
    }}
    .hero-label {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
      color: #6d28d9;
      margin: 0 0 10px 0;
    }}
    .hero-headline {{
      font-size: 23px;
      font-weight: 800;
      margin: 0 0 10px 0;
      line-height: 1.3;
      color: #111;
    }}
    .hero-headline a, .story-headline a {{
      color: inherit;
      text-decoration: none;
    }}
    .hero-headline a:hover, .story-headline a:hover {{
      text-decoration: underline;
    }}
    .hero-summary {{
      font-size: 15.5px;
      line-height: 1.75;
      color: #333;
      margin: 0 0 10px 0;
    }}
    .content {{
      padding: 8px 28px 4px;
    }}
    .section {{
      margin-bottom: 34px;
    }}
    .section-title {{
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: #4338ca;
      margin: 0 0 16px 0;
      padding-bottom: 8px;
      border-bottom: 2px solid #ede9fe;
    }}
    .story {{
      margin-bottom: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid #f0f0f0;
    }}
    .story:last-child {{
      border-bottom: none;
    }}
    .story-headline {{
      font-size: 18.5px;
      font-weight: 700;
      margin: 0 0 10px 0;
      line-height: 1.35;
      color: #111;
    }}
    .impact-badge {{
      display: inline-block;
      font-size: 10.5px;
      font-weight: 700;
      color: #b45309;
      background: #fef3c7;
      padding: 2px 8px;
      border-radius: 999px;
      margin-left: 8px;
      vertical-align: middle;
    }}
    .story-summary {{
      font-size: 15px;
      line-height: 1.7;
      margin: 0 0 10px 0;
      color: #333;
    }}
    .story-meta {{
      font-size: 12.5px;
      color: #888;
    }}
    .story-meta a {{
      color: #4338ca;
      text-decoration: none;
      font-weight: 500;
    }}
    .story-meta a:hover {{
      text-decoration: underline;
    }}
    .footer {{
      margin-top: 12px;
      padding: 24px 28px 32px;
      border-top: 1px solid #eee;
      font-size: 12px;
      color: #999;
      text-align: center;
      background: #fafafa;
    }}
    .footer .agents-row {{
      margin-top: 8px;
      font-size: 11.5px;
      color: #aaa;
    }}
    @media only screen and (max-width: 600px) {{
      .header, .hero, .content, .footer {{
        padding-left: 18px;
        padding-right: 18px;
      }}
      .header h1 {{
        font-size: 24px;
      }}
      .story-headline, .hero-headline {{
        font-size: 18px;
      }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="eyebrow">Issue #{issue_number}</div>
    <h1>{title}</h1>
    <div class="date">{date_str} · {count} stories from {source_count} sources</div>
    <div class="agent-badge">{badge_text}</div>
  </div>

  {hero_html}

  <div class="content">
  {sections_html}
  </div>

  <div class="footer">
    Written, fact-checked, edited and QA'd end-to-end by autonomous AI agents — no human editor in the loop.
    <div class="agents-row">Reporter → Fact-Checker → Editor → QA</div>
  </div>
</div>
</body>
</html>
"""

HERO_TEMPLATE = """\
<div class="hero">
  <div class="hero-label">🔥 Top Story</div>
  <div class="hero-headline">{headline}</div>
  <p class="hero-summary">{summary}</p>
  <div class="story-meta">Originally reported by {sources}</div>
</div>
"""

# Task 5.3: per-mode header copy. Weekly mode signals its stricter "Best of" curation bar.
MODE_HEADER = {
    "daily": {"title": "AI Daily", "badge_text": "✨ Curated by AI Agents"},
    "weekly": {"title": "AI Weekly — Best of the Week", "badge_text": "✨ Best-of curation by AI Agents"},
}

SECTION_TEMPLATE = """\
<div class="section">
  <div class="section-title">{section_title}</div>
  {stories_html}
</div>
"""

STORY_TEMPLATE = """\
<div class="story">
  <h2 class="story-headline">{headline}{impact_badge}</h2>
  <p class="story-summary">{summary}</p>
  <div class="story-meta">Originally reported by {sources}</div>
</div>
"""


def _next_issue_number():
    """Issue # = how many digests have been sent so far, +1 for this one."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM digest_log").fetchone()
        return (row["n"] or 0) + 1
    except Exception:
        return 1
    finally:
        conn.close()


def build_digest_html():
    """
    Build digest using multi-agent validation pipeline
    Agents handle quality assurance, curation, and formatting
    """
    
    if AGENTS_AVAILABLE:
        from config import TOP_N_STORIES, USE_LANGGRAPH_ORCHESTRATION

        if USE_LANGGRAPH_ORCHESTRATION:
            # Task 5.2: graph-based orchestration already runs the QA<->Editor backup
            # loop internally via conditional edges, so there's nothing left to do here.
            print("\n🤖 Using LangGraph orchestration for digest generation")
            from agents.orchestration_graph import run_langgraph_pipeline
            success, selected_clusters, report = run_langgraph_pipeline()
            print(report)
            if not success or not selected_clusters:
                print("Digest: No valid stories after agent validation.")
                return None, []
        else:
            print("\n🤖 Using Multi-Agent System for digest generation")

            # Run full agent validation pipeline
            success, selected_clusters, report = coordinator.run_full_validation_pipeline()

            print(report)

            if not success or not selected_clusters:
                print("Digest: No valid stories after agent validation.")
                return None, []

            # Task 1.5: QA <-> Editor backup loop. QA validates the selection; if some
            # clusters are rejected, Editor fetches backups and QA re-validates them,
            # so the pipeline can still ship a full digest instead of failing outright.
            qa_result = qa_agent.validate_clusters_for_digest(selected_clusters, min_count=TOP_N_STORIES)
            selected_clusters = qa_result["valid_clusters"]

            backup_request = qa_result["backup_request"]
            attempts = 0
            while backup_request and backup_request["needed"] > 0 and attempts < 3:
                attempts += 1
                backups = editor_agent.fetch_backup_stories(
                    backup_request["exclude_ids"], backup_request["needed"]
                )
                if not backups:
                    break
                backup_qa = qa_agent.validate_clusters_for_digest(backups, min_count=backup_request["needed"])
                selected_clusters.extend(backup_qa["valid_clusters"])
                backup_request["exclude_ids"].extend(c["id"] for c in backups)
                backup_request["needed"] = max(0, TOP_N_STORIES - len(selected_clusters))

            if not selected_clusters:
                print("Digest: No valid stories after QA/backup validation.")
                return None, []

            print(f"✓ QA/Editor backup loop: shipping {len(selected_clusters)} validated stories")

        # Defamation-risk gate: the email goes straight to subscribers' inboxes, so a
        # hallucinated claim about a named person/company here is at least as much legal
        # exposure as one on the site (arguably more - it's actively pushed, not just
        # hosted). Drop anything the grounding check can't clear rather than send it.
        cleared_clusters = []
        for cluster in selected_clusters:
            compliance = fact_checker_agent.check_defamation_risk(
                cluster.get("headline"), cluster.get("summary"), cluster.get("articles", []),
            )
            if compliance.get("verdict") == "PASS":
                cleared_clusters.append(cluster)
            else:
                print(f"  [blocked] cluster {cluster.get('id')} failed defamation-risk check: "
                      f"{compliance.get('flagged')}")
        selected_clusters = cleared_clusters

        if not selected_clusters:
            print("Digest: No valid stories after defamation-risk check.")
            return None, []

        # Writer Agent: expand each selected, already-fact-checked story into a full
        # website article (cached in clusters.full_content so it only runs once per story).
        print(f"\n✍️  Writer Agent: generating full articles for {len(selected_clusters)} stories")
        for cluster in selected_clusters:
            ensure_full_article(cluster)

        # Sort by importance so the strongest stories lead each section (and the hero).
        selected_clusters = sorted(
            selected_clusters, key=lambda c: c.get('importance_score') or 0, reverse=True
        )

        # Build HTML from agent-selected clusters
        sections = {}
        cluster_ids = []
        all_source_names = set()
        hero = None

        for cluster in selected_clusters:
            category = cluster.get('category') or 'Other'
            if category not in sections:
                sections[category] = []

            articles = cluster['articles']
            sources_linked = ", ".join(
                f'<a href="{a["url"]}">{a["source"]}</a>' for a in articles
            )

            for a in articles:
                all_source_names.add(a['source'])

            score = cluster.get('importance_score') or 0
            headline_text = cluster['headline'] or (articles[0]['title'] if articles else "Untitled")
            article_url = f"{SITE_BASE_URL}/articles/{cluster['id']}"
            story_entry = {
                "headline": f'<a href="{article_url}">{headline_text}</a>',
                "summary": cluster['summary'],
                "sources": sources_linked,
                "score": score,
            }

            # The single highest-scoring story across the whole digest leads as the hero
            # and isn't repeated in its section.
            if hero is None or score > hero["score"]:
                if hero is not None:
                    sections[hero["category"]].append(hero)
                hero = {**story_entry, "category": category}
            else:
                sections[category].append(story_entry)

            cluster_ids.append(cluster['id'])

        hero_html = ""
        if hero:
            hero_html = HERO_TEMPLATE.format(
                headline=hero["headline"], summary=hero["summary"], sources=hero["sources"]
            )

        # Build HTML sections
        section_order = [
            "Company News", "Business & Enterprise AI", "Funding & Investment", "Startup Launches",
            "Research & Models", "Tools & Engineering", "Policy & Regulation", "Other",
        ]
        sections_html_parts = []

        for section_title in section_order:
            if section_title in sections and sections[section_title]:
                stories_html = "\n".join([
                    STORY_TEMPLATE.format(
                        headline=story["headline"],
                        impact_badge=' <span class="impact-badge">HIGH IMPACT</span>' if story["score"] >= 8 else "",
                        summary=story["summary"],
                        sources=story["sources"]
                    )
                    for story in sections[section_title]
                ])

                sections_html_parts.append(
                    SECTION_TEMPLATE.format(
                        section_title=section_title,
                        stories_html=stories_html
                    )
                )

        from utils.mode_state import get_mode
        header = MODE_HEADER.get(get_mode(), MODE_HEADER["daily"])
        total_stories = sum(len(stories) for stories in sections.values()) + (1 if hero else 0)
        html = HTML_WRAPPER.format(
            title=header["title"],
            badge_text=header["badge_text"],
            issue_number=_next_issue_number(),
            date_str=date.today().strftime("%B %d, %Y"),
            count=total_stories,
            source_count=len(all_source_names),
            hero_html=hero_html,
            sections_html="\n".join(sections_html_parts),
        )

        print(f"\n✅ Digest generated: {len(sections)} sections, {total_stories} stories")
        return html, cluster_ids
    
    else:
        # Fallback mode without agents
        print("\n⚠️  Building digest in fallback mode (agents not available)")
        return None, []


def mark_as_sent(cluster_ids):
    """
    Mark clusters as sent after digest generation.
    Uses StateManager to track sent content and prevent duplicates.
    """
    if not cluster_ids:
        return
    
    # Generate digest ID: YYYY-MM-DD-<mode>
    from utils.mode_state import get_mode
    digest_id = f"{date.today().isoformat()}-{get_mode()}"
    
    # Use StateManager to mark as sent
    state_manager.mark_as_sent(cluster_ids, digest_id)
    
    # Also update the legacy included_in_digest flag for backwards compatibility
    conn = get_connection()
    conn.executemany(
        "UPDATE clusters SET included_in_digest = 1 WHERE id = ?",
        [(cid,) for cid in cluster_ids],
    )
    conn.commit()
    conn.close()
