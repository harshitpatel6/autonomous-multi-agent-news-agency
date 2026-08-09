"""
Scout Agent (Task 5.1): discovers new RSS/Atom sources, validates feed quality,
and prunes dead feeds. Persists its findings to data/scout_sources.json, which
config.py merges into FEEDS at import time — so a discovered source shows up in
the next ingest run without editing config.py by hand.
"""
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import feedparser

from config import FEEDS
from agents.base_agent import Agent
from agents.message_router import register_agent, router

SOURCES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "scout_sources.json")

DISCOVERY_PROMPT = """You are a research scout for an AI industry newsletter. Suggest {n} \
candidate RSS or Atom feed URLs for AI/ML news that are NOT already in this list:

{existing}

Good candidates: company engineering blogs, research lab blogs, GitHub releases.atom feeds \
for popular AI open-source projects, and reputable tech-news RSS feeds. Prefer feeds you are \
confident actually exist and are still active.

Respond ONLY with valid JSON:
{{"candidates": [{{"name": "...", "url": "..."}}]}}
"""


def _load_sources() -> List[Dict]:
    if not os.path.exists(SOURCES_FILE):
        return []
    try:
        with open(SOURCES_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save_sources(sources: List[Dict]):
    os.makedirs(os.path.dirname(SOURCES_FILE), exist_ok=True)
    with open(SOURCES_FILE, "w") as f:
        json.dump(sources, f, indent=2)


class ScoutAgent(Agent):
    def __init__(self):
        super().__init__("ScoutAgent")

    def validate_feed_url(self, url: str) -> Tuple[bool, str]:
        """Fetch and parse a candidate feed URL; reject dead/empty/malformed feeds."""
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            return False, f"parse error: {e}"

        if parsed.bozo and not parsed.entries:
            return False, f"malformed feed: {getattr(parsed, 'bozo_exception', 'unknown error')}"
        if not parsed.entries:
            return False, "feed parsed but has zero entries"
        return True, f"ok ({len(parsed.entries)} entries)"

    def add_source(self, name: str, url: str) -> bool:
        """Validate then persist a new source. Returns True if added."""
        existing_urls = {u for _, u in FEEDS} | {s["url"] for s in _load_sources()}
        if url in existing_urls:
            self.logger.log_action("add_source", input_data={"url": url}, success=False,
                                    error_message="duplicate", level="INFO")
            return False

        ok, detail = self.validate_feed_url(url)
        if not ok:
            self.logger.log_action("add_source", input_data={"url": url}, success=False,
                                    error_message=detail, level="WARNING")
            print(f"🔍 Scout: rejected candidate {name} ({url}) — {detail}")
            return False

        sources = _load_sources()
        sources.append({"name": name, "url": url, "added_at": datetime.now(timezone.utc).isoformat(), "status": "active"})
        _save_sources(sources)
        self.logger.log_action("add_source", input_data={"name": name, "url": url}, output_data={"detail": detail}, success=True)
        print(f"✅ Scout: added new source {name} ({url}) — {detail}")
        return True

    def remove_dead_source(self, url: str) -> bool:
        """Mark a scout-added source as dead (feed no longer valid) and drop it from active rotation."""
        sources = _load_sources()
        found = False
        for s in sources:
            if s["url"] == url:
                s["status"] = "dead"
                s["removed_at"] = datetime.now(timezone.utc).isoformat()
                found = True
        if found:
            _save_sources(sources)
            self.logger.log_action("remove_dead_source", input_data={"url": url}, success=True, level="WARNING")
            print(f"🗑️  Scout: marked source dead — {url}")
        return found

    def audit_existing_sources(self) -> Dict:
        """Re-validate every scout-added active source; auto-remove ones that now fail."""
        sources = _load_sources()
        removed = []
        for s in sources:
            if s.get("status") != "active":
                continue
            ok, detail = self.validate_feed_url(s["url"])
            if not ok:
                self.remove_dead_source(s["url"])
                removed.append(s["url"])
        result = {"audited": len(sources), "removed": removed}
        self.logger.log_action("audit_existing_sources", output_data=result, success=True)
        return result

    def discover_sources(self, n: int = 5) -> List[Dict]:
        """Ask the LLM for candidate feeds, validate each, persist the good ones."""
        existing_names = "\n".join(f"- {name}" for name, _ in FEEDS)
        prompt = DISCOVERY_PROMPT.format(n=n, existing=existing_names)
        response = self.call_llm(prompt, max_tokens=600, json_mode=True)
        parsed = self.parse_json(response, default={"candidates": []})

        added = []
        for candidate in parsed.get("candidates", []):
            name, url = candidate.get("name"), candidate.get("url")
            if name and url and self.add_source(name, url):
                added.append(candidate)

        self.logger.log_action("discover_sources", output_data={"added": len(added)}, success=True)
        return added

    def run_weekly_scout(self) -> Dict:
        """Full weekly cycle: audit existing sources, then discover new ones, then report to CEO."""
        print("\n🔭 Scout Agent: starting weekly source discovery run")
        audit = self.audit_existing_sources()
        discovered = self.discover_sources()

        summary = {
            "removed_dead": audit["removed"],
            "added": [c["name"] for c in discovered],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        router.send("scout", "ceo", "report", {
            "title": "Weekly Scout Report",
            "summary": f"Removed {len(summary['removed_dead'])} dead feeds, added {len(summary['added'])} new sources.",
            "details": summary,
        })
        return summary

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        mtype = message["type"]
        if mtype == "discover":
            return {"added": self.discover_sources(payload.get("n", 5))}
        if mtype == "audit":
            return self.audit_existing_sources()
        if mtype == "run_weekly":
            return self.run_weekly_scout()
        return {"error": f"unknown message type {mtype}"}


scout_agent = ScoutAgent()
register_agent("scout", scout_agent.handle_message)


if __name__ == "__main__":
    scout_agent.run_weekly_scout()
