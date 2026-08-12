"""
Enhanced Fact-Checker Agent (Task 2.5): heuristic validation of clusters with a
0.0-1.0 confidence score, flagging inconsistencies before a story reaches QA/Editor.
"""
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

from config import ABSOLUTE_CUTOFF_DATE, LOOKBACK_HOURS
from agents.base_agent import Agent
from agents.message_router import register_agent

# Sources considered higher-reputation for corroboration weighting.
REPUTABLE_SOURCES = {
    "OpenAI", "Google DeepMind", "Anthropic", "Hugging Face", "TechCrunch AI",
    "The Verge AI", "Ars Technica AI", "MIT Technology Review AI", "VentureBeat AI",
    "Microsoft AI Blog", "AWS ML Blog", "NVIDIA Developer",
}

# validate_cluster() above only checks dates/sources/URLs on the *editorial brief* -
# it has no way to catch a generated claim that misattributes wrongdoing to a real,
# named person or company. That's a distinct risk (defamation exposure, not story
# quality) and needs the actual generated text checked against the source material,
# which is what check_defamation_risk() below does.
DEFAMATION_CHECK_PROMPT = """You are the legal/compliance reviewer for an AI industry news site. Your ONLY \
job here is to catch content that could expose the publisher to a defamation claim — you are not grading \
writing quality, style, or factual completeness.

Read the GENERATED CONTENT below and compare every claim it makes about a specific, identifiable person or \
organization against the SOURCE MATERIAL it was supposed to be built from.

Flag a claim if it:
- States or implies a named person or organization committed a crime, fraud, deception, or other \
wrongdoing, or is incompetent, dishonest, or unethical — and the sources do not explicitly say that.
- Reports an accusation, lawsuit, or investigation as an established fact rather than an allegation, when \
the sources describe it only as an allegation/claim/lawsuit that hasn't been adjudicated.
- Attributes a quote, statement, or specific number to a named person/org that doesn't appear in the sources.
- Makes a negative characterization ("failed", "mismanaged", "covered up", "lied") about a named party \
beyond what the sources support.

Do NOT flag ordinary, well-sourced reporting (a company announced layoffs, a startup raised funding, a \
lawsuit was filed and the sources say so, a product shipped with a known bug) — only claims that go beyond, \
or distort, what the sources actually say.

HEADLINE: {headline}

GENERATED CONTENT:
{generated_text}

SOURCE MATERIAL (ground truth — the only facts allowed):
{sources_block}

Respond ONLY with valid JSON, no other text:
{{"verdict": "PASS" or "FAIL", "flagged": [{{"claim": "...", "reason": "..."}}]}}
"""


class FactCheckerAgent(Agent):
    def __init__(self):
        super().__init__("FactCheckerAgent")

    def validate_cluster(self, cluster: Dict, articles: List[Dict]) -> Dict:
        """
        Heuristic validation returning a confidence score (0.0-1.0) plus flags/recommendation.
        Checks: date consistency, source reputation, multi-source corroboration, URL sanity.
        """
        flags: List[str] = []
        score = 1.0

        if not articles:
            return {"confidence": 0.0, "flags": ["no articles in cluster"], "recommendation": "reject"}

        # 1. Date consistency: all dates present, plausible, and clustered close together
        dates = [a.get("published_at") for a in articles if a.get("published_at")]
        if len(dates) < len(articles):
            missing = len(articles) - len(dates)
            flags.append(f"{missing} article(s) missing published_at")
            score -= 0.15 * missing / len(articles)

        for d in dates:
            if d < ABSOLUTE_CUTOFF_DATE:
                flags.append(f"article predates ABSOLUTE_CUTOFF_DATE: {d}")
                score -= 0.3

        if len(dates) >= 2:
            try:
                parsed = sorted(datetime.fromisoformat(d.replace("Z", "+00:00")) for d in dates)
                spread_days = (parsed[-1] - parsed[0]).days
                if spread_days > 14:
                    flags.append(f"source dates span {spread_days} days — may not be the same story")
                    score -= 0.2
            except Exception:
                flags.append("could not parse one or more dates")
                score -= 0.1

        # 2. Source reputation
        sources = {a.get("source") for a in articles}
        reputable_count = len(sources & REPUTABLE_SOURCES)
        if reputable_count == 0:
            flags.append("no reputable/primary source corroborates this story")
            score -= 0.15

        # 3. Multi-source corroboration
        if len(sources) == 1:
            flags.append("single-source story (no corroboration)")
            score -= 0.1
        else:
            score += min(0.1, 0.03 * (len(sources) - 1))  # small bonus, capped

        # 4. URL sanity
        for a in articles:
            url = a.get("url", "")
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                flags.append(f"malformed URL: {url[:60]}")
                score -= 0.1

        # 5. Cluster completeness
        if not cluster.get("headline") or not cluster.get("summary"):
            flags.append("cluster missing headline or summary")
            score -= 0.2

        score = round(max(0.0, min(1.0, score)), 2)
        recommendation = "publish" if score >= 0.6 else ("review" if score >= 0.35 else "reject")

        result = {"confidence": score, "flags": flags, "recommendation": recommendation}
        self.logger.log_action(
            "validate_cluster", input_data={"cluster_id": cluster.get("id")},
            output_data=result, success=True,
        )
        return result

    def check_defamation_risk(self, headline: str, generated_text: str, articles: List[Dict]) -> Dict:
        """
        LLM grounding pass run once per cluster, right before it goes live (publish.py) or
        into an email (digest.py): checks the Writer/Reporter's generated text for claims
        about named people/orgs (wrongdoing, crime, lawsuits stated as settled fact,
        fabricated quotes) that the source material doesn't actually support.

        Fails closed: if the LLM can't be reached (providers down/circuit open) or returns
        something unparseable, this returns FAIL rather than PASS - callers must not publish
        a story just because the verifier itself was unavailable to check it.
        """
        sources_block = "\n".join(
            f"- [{a.get('source')}] {a.get('title')}\n  {(a.get('summary_raw') or '')[:1500]}"
            for a in articles
        ) or "(no source material available)"

        prompt = DEFAMATION_CHECK_PROMPT.format(
            headline=headline or "", generated_text=(generated_text or "")[:6000],
            sources_block=sources_block[:6000],
        )
        response = self.call_llm(prompt, max_tokens=700, json_mode=True)
        parsed = self.parse_json(response)

        if parsed and parsed.get("verdict") in ("PASS", "FAIL"):
            result = {"verdict": parsed["verdict"], "flagged": parsed.get("flagged") or []}
        else:
            result = {
                "verdict": "FAIL",
                "flagged": [{"claim": "(compliance check unavailable)",
                             "reason": "verifier LLM unreachable or returned invalid output - failing closed"}],
            }

        self.logger.log_action(
            "check_defamation_risk", input_data={"headline": headline},
            output_data={"verdict": result["verdict"], "flagged_count": len(result["flagged"])},
            success=result["verdict"] == "PASS",
        )
        return result

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        if message["type"] == "validate_cluster":
            return self.validate_cluster(payload["cluster"], payload.get("articles", []))
        if message["type"] == "check_defamation_risk":
            return self.check_defamation_risk(
                payload.get("headline"), payload.get("generated_text"), payload.get("articles", []),
            )
        return {"error": f"unknown message type {message['type']}"}


fact_checker_agent = FactCheckerAgent()
register_agent("fact_checker", fact_checker_agent.handle_message)
