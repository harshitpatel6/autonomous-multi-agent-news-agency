"""
Central config: sources, thresholds, and settings.
Edit FEEDS to add/remove sources.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- RSS sources ---
# Add or remove feeds here. Format: (source_name, feed_url)
FEEDS = [
    # NOTE: Anthropic has no official RSS feed. This is a community-maintained
    # mirror - it can go stale or break without warning, so keep an eye on the
    # per-source counts ingest.py now prints.
    ("Anthropic", "https://tim-hilde.github.io/anthropic-rss/rss.xml"),
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("Ars Technica (AI)", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI"),
    ("Hacker News (AI)", "https://hnrss.org/newest?q=AI+OR+LLM+OR+agent"),
]

# --- Pipeline settings ---
LOOKBACK_HOURS = 24          # how far back to pull articles each run
TOP_N_STORIES = 12           # how many stories make it into the digest
MIN_IMPORTANCE_SCORE = 3     # drop clusters scored below this (1-10 scale)

# --- Database ---
DB_PATH = os.path.join(os.path.dirname(__file__), "digest.db")

# --- Claude API ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-6"

# --- Email (SMTP) ---
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
DIGEST_RECIPIENT = os.getenv("DIGEST_RECIPIENT")  # your own email, for now