"""
Small shared text helpers used by agents that need to reason about generated HTML as
plain text (word counts, similarity checks, LLM prompts) without pulling in a full HTML
parser dependency.
"""
import re


def strip_html(html: str) -> str:
    """Crude but sufficient tag stripper for our own agent-generated HTML (a handful of
    <p>/<h3>/<ul>/<li>/<strong> tags, never arbitrary third-party markup)."""
    return re.sub(r"<[^>]+>", " ", html or "")
