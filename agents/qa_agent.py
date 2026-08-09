"""
QA Tester Agent - Autonomous quality assurance for newsletter
Validates dates, checks links, verifies content quality
"""
import anthropic
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, DB_PATH, LOOKBACK_HOURS, ABSOLUTE_CUTOFF_DATE, TOP_N_STORIES
from agents.base_agent import Agent
from agents.message_router import register_agent

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

QA_AGENT_PROMPT = """You are the QA Tester for an AI news agency. Your job is to validate the quality of the newsletter before it goes out.

You will receive:
1. A list of articles with their published dates and URLs
2. The current date and time
3. The configured date filters (LOOKBACK_HOURS and ABSOLUTE_CUTOFF_DATE)

Your responsibilities:
1. Check if ANY articles are older than the ABSOLUTE_CUTOFF_DATE
2. Check if ANY articles are outside the LOOKBACK_HOURS window
3. Identify suspicious patterns (same article appearing multiple times, broken URLs, etc.)
4. Provide a PASS/FAIL verdict with specific issues found

Respond ONLY with valid JSON in this format:
{{
  "verdict": "PASS" or "FAIL",
  "issues": [
    {{"type": "old_article", "severity": "critical", "article_title": "...", "published_date": "...", "reason": "..."}},
    {{"type": "duplicate", "severity": "warning", "article_title": "...", "reason": "..."}}
  ],
  "summary": "Brief summary of QA results",
  "recommendation": "What action should be taken (publish, fix, reject)"
}}

Severity levels:
- "critical": Must fix before publishing (e.g., very old articles)
- "warning": Should investigate but not blocking (e.g., minor issues)
- "info": FYI only

Be thorough and strict. Better to catch issues now than send bad content.
"""


class QAAgent(Agent):
    def __init__(self):
        super().__init__("QAAgent")
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def validate_clusters_for_digest(self, clusters: List[Dict], min_count: int = TOP_N_STORIES) -> Dict:
        """
        Task 1.5: Deterministic cluster-level validation for the Editor <-> QA backup loop.
        Returns {verdict: PASS|PARTIAL|FAIL, valid_clusters, rejected, backup_request}
        - PASS: every cluster is valid
        - PARTIAL: some rejected but enough (or a partial set) remain; backup_request set if under min_count
        - FAIL: no clusters valid at all
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
        valid, rejected = [], []

        for cluster in clusters:
            articles = cluster.get("articles", [])
            reasons = []
            if not articles:
                reasons.append("no articles")
            if not cluster.get("headline") or not cluster.get("summary"):
                reasons.append("missing headline/summary")
            for a in articles:
                pub = a.get("published_at") or ""
                if not pub:
                    reasons.append(f"article missing published_at: {a.get('title', '')[:40]}")
                elif pub < ABSOLUTE_CUTOFF_DATE or pub < cutoff:
                    reasons.append(f"article too old: {a.get('title', '')[:40]}")

            if reasons:
                rejected.append({"cluster_id": cluster.get("id"), "headline": cluster.get("headline"), "reasons": reasons})
            else:
                valid.append(cluster)

        if len(valid) == len(clusters) and valid:
            verdict = "PASS"
        elif valid:
            verdict = "PARTIAL"
        else:
            verdict = "FAIL"

        shortfall = max(0, min_count - len(valid))
        backup_request = {"needed": shortfall, "exclude_ids": [c.get("id") for c in clusters]} if shortfall > 0 else None

        result = {"verdict": verdict, "valid_clusters": valid, "rejected": rejected, "backup_request": backup_request}
        self.logger.log_action(
            "validate_clusters_for_digest",
            input_data={"count": len(clusters)},
            output_data={"verdict": verdict, "valid": len(valid), "rejected": len(rejected)},
            success=verdict != "FAIL",
        )
        print(f"🤖 QA Agent verdict: {verdict} ({len(valid)}/{len(clusters)} valid"
              + (f", requesting {shortfall} backups)" if shortfall else ")"))
        return result

    def handle_message(self, message: Dict) -> Dict:
        """Message-router entrypoint: {type: 'validate_clusters', payload: {clusters, min_count}}"""
        payload = message.get("payload", {})
        if message["type"] == "validate_clusters":
            return self.validate_clusters_for_digest(payload["clusters"], payload.get("min_count", TOP_N_STORIES))
        return {"error": f"unknown message type {message['type']}"}

    def gather_articles_for_review(self):
        """Collect all articles that will be in the digest"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
        
        # Get clusters that will be in digest
        clusters = conn.execute("""
            SELECT id, headline, summary, created_at FROM clusters
            WHERE summary IS NOT NULL 
                  AND included_in_digest = 0
                  AND created_at >= ?
            ORDER BY importance_score DESC
        """, (cutoff,)).fetchall()
        
        articles_data = []
        for cluster in clusters:
            articles = conn.execute("""
                SELECT source, title, url, published_at, fetched_at
                FROM articles WHERE cluster_id = ?
            """, (cluster["id"],)).fetchall()
            
            for article in articles:
                articles_data.append({
                    "cluster_headline": cluster["headline"],
                    "source": article["source"],
                    "title": article["title"],
                    "url": article["url"],
                    "published_at": article["published_at"],
                    "fetched_at": article["fetched_at"]
                })
        
        conn.close()
        return articles_data
    
    def build_review_context(self, articles):
        """Format articles for LLM review"""
        now = datetime.now(timezone.utc).isoformat()
        
        context = f"""Current Date/Time: {now}
ABSOLUTE_CUTOFF_DATE: {ABSOLUTE_CUTOFF_DATE}
LOOKBACK_HOURS: {LOOKBACK_HOURS} (cutoff: {(datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()})

Articles to Review ({len(articles)} total):

"""
        for idx, article in enumerate(articles, 1):
            context += f"""{idx}. [{article['source']}] {article['title'][:80]}
   Published: {article['published_at'] or 'NO DATE'}
   Fetched: {article['fetched_at'][:19]}
   URL: {article['url']}
   Cluster: {article['cluster_headline'] or 'N/A'}

"""
        return context
    
    def run_qa_check(self):
        """Execute full QA validation"""
        print("\n" + "="*70)
        print("🤖 QA TESTER AGENT - Running Quality Assurance")
        print("="*70)
        
        articles = self.gather_articles_for_review()
        
        if not articles:
            print("✅ No articles to review (digest is empty)")
            return {"verdict": "PASS", "issues": [], "summary": "No articles in digest", "recommendation": "Nothing to publish"}
        
        print(f"\n📋 Reviewing {len(articles)} articles across all clusters...")
        
        context = self.build_review_context(articles)
        
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=QA_AGENT_PROMPT,
                messages=[{"role": "user", "content": context}]
            )
            
            import json
            result_text = response.content[0].text.strip()
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(result_text)
            
            # Display results
            print(f"\n{'='*70}")
            print(f"VERDICT: {result['verdict']}")
            print(f"{'='*70}")
            print(f"\n{result['summary']}")
            
            if result['issues']:
                print(f"\n📝 ISSUES FOUND ({len(result['issues'])}):\n")
                for issue in result['issues']:
                    severity_emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(issue['severity'], "•")
                    print(f"{severity_emoji} [{issue['severity'].upper()}] {issue['type']}")
                    if 'article_title' in issue:
                        print(f"   Article: {issue['article_title'][:60]}")
                    if 'published_date' in issue:
                        print(f"   Published: {issue['published_date']}")
                    print(f"   Reason: {issue['reason']}\n")
            else:
                print("\n✅ No issues found!")
            
            print(f"\n💡 RECOMMENDATION: {result['recommendation']}")
            print("="*70)
            
            return result
            
        except Exception as e:
            print(f"\n❌ QA Agent failed: {e}")
            return {
                "verdict": "FAIL",
                "issues": [{"type": "agent_error", "severity": "critical", "reason": str(e)}],
                "summary": "QA Agent encountered an error",
                "recommendation": "Manual review required"
            }
    
    def auto_fix_issues(self, qa_result):
        """Attempt to automatically fix critical issues"""
        if qa_result['verdict'] == "PASS":
            return True
        
        critical_issues = [i for i in qa_result['issues'] if i['severity'] == 'critical']
        
        if not critical_issues:
            print("\n⚠️  Only warnings found, proceeding with caution...")
            return True
        
        print(f"\n🔧 QA Agent attempting to auto-fix {len(critical_issues)} critical issues...")
        
        # Auto-fix: Remove clusters with old articles
        conn = sqlite3.connect(DB_PATH)
        
        for issue in critical_issues:
            if issue['type'] == 'old_article' and 'article_title' in issue:
                # Find and mark cluster as sent (exclude from digest)
                article_title = issue['article_title']
                result = conn.execute("""
                    UPDATE clusters 
                    SET included_in_digest = 1 
                    WHERE id IN (
                        SELECT cluster_id FROM articles 
                        WHERE title LIKE ? AND cluster_id IS NOT NULL
                    )
                """, (f"%{article_title[:30]}%",))
                
                if result.rowcount > 0:
                    print(f"   ✓ Excluded cluster containing: {article_title[:60]}")
        
        conn.commit()
        conn.close()
        
        print("✅ Auto-fix completed. Rerun digest generation.")
        return False  # Signal that digest needs regeneration


def run_qa_validation():
    """Main entry point for QA validation"""
    agent = QAAgent()
    result = agent.run_qa_check()
    
    if result['verdict'] == "FAIL":
        print("\n" + "="*70)
        print("❌ QA VALIDATION FAILED")
        print("="*70)
        
        # Attempt auto-fix
        fixed = agent.auto_fix_issues(result)
        
        if not fixed:
            print("\n⚠️  Some issues were auto-fixed. Please regenerate digest:")
            print("   python -c 'from digest import build_digest_html; build_digest_html()'")
            return False
    else:
        print("\n✅ QA VALIDATION PASSED - Newsletter ready to send!")
    
    return result['verdict'] == "PASS"


qa_agent = QAAgent()
register_agent("qa", qa_agent.handle_message)


if __name__ == "__main__":
    run_qa_validation()
