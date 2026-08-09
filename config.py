"""
Central config: sources, thresholds, and settings.
Edit FEEDS to add/remove sources.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- RSS sources ---
# Comprehensive AI news from industry, research, engineering, and community
# Organized by category for easy management
FEEDS = [
    # 1. AI Companies
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Google DeepMind", "https://deepmind.google/blog/feed/basic/"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    # NOTE: Anthropic has no official RSS feed. This is a community-maintained
    # mirror - it can go stale or break without warning, so keep an eye on the
    # per-source counts ingest.py now prints.
    ("Anthropic", "https://tim-hilde.github.io/anthropic-rss/rss.xml"),
    # ("Mistral AI", "https://rsshub.bestblogs.dev/mistral/blog"),
    ("Cohere", "https://rsshub.bestblogs.dev/cohere/blog"),
    # ("Perplexity", "https://rsshub.bestblogs.dev/perplexity/blog"),
    ("Groq", "https://github.com/groq/groq-python/releases.atom"),
    ("Stability AI", "https://github.com/stability-ai/stablelm/releases.atom"),
    ("Cursor", "https://rsshub.bestblogs.dev/cursor/blog"),
    
    # 2. AI Research
    # ("arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI"),
    # ("arXiv cs.LG", "https://export.arxiv.org/rss/cs.LG"),
    # ("arXiv cs.CL", "https://export.arxiv.org/rss/cs.CL"),
    ("Papers with Code", "https://github.com/paperswithcode/paperswithcode-data/releases.atom"),
    ("Semantic Scholar", "https://github.com/allenai/s2orc/releases.atom"),
    
    # 3. AI Engineering & Open Source (GitHub Releases)
    ("LangChain", "https://github.com/langchain-ai/langchain/releases.atom"),
    ("LlamaIndex", "https://github.com/run-llama/llama_index/releases.atom"),
    ("vLLM", "https://github.com/vllm-project/vllm/releases.atom"),
    ("Ollama", "https://github.com/ollama/ollama/releases.atom"),
    ("LiteLLM", "https://github.com/BerriAI/litellm/releases.atom"),
    ("Open WebUI", "https://github.com/open-webui/open-webui/releases.atom"),
    ("ComfyUI", "https://github.com/comfyanonymous/ComfyUI/releases.atom"),
    ("Mistral Inference", "https://github.com/mistralai/mistral-inference/releases.atom"),
    
    # 4. Technology News
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Ars Technica AI", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/ai/feed/"),
    ("MarkTechPost", "https://www.marktechpost.com/feed/"),
    
    # 5. Developer Communities
    ("Hacker News AI", "https://hnrss.org/newest?q=AI+OR+LLM+OR+agent"),
    # ("Reddit LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/.rss"),
    # ("Reddit MachineLearning", "https://www.reddit.com/r/MachineLearning/.rss"),
    # ("Reddit Artificial", "https://www.reddit.com/r/artificial/.rss"),
    
    # 6. Big Tech AI
    ("Google AI Blog", "https://ai.googleblog.com/feeds/posts/default/-/AI?alt=rss"),
    ("Microsoft AI Blog", "https://www.microsoft.com/en-us/research/feed/"),
    ("AWS ML Blog", "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("NVIDIA Developer", "https://developer.nvidia.com/blog/feed/"),
    ("Meta Research", "https://research.facebook.com/feed/"),
    
    # 7. Additional Quality Sources
    ("Towards Data Science", "https://towardsdatascience.com/feed"),
    ("Generalist Research", "https://generalist.com/feed"),
    ("AI Trends", "https://www.aitrends.com/feed/"),

    # 8. Business, Funding & Startups
    # Feeds AI companies' new products/enterprise adoption, funding rounds, and new
    # startup launches. Classification into "Business & Enterprise AI" /
    # "Funding & Investment" / "Startup Launches" happens per-cluster by the Reporter
    # Agent's LLM prompt (agents/reporter_agent.py), not per-feed.
    ("TechCrunch Startups", "https://techcrunch.com/category/startups/feed/"),
    ("Crunchbase News", "https://news.crunchbase.com/feed/"),
    ("Inc42", "https://inc42.com/feed/"),
    ("Sifted", "https://sifted.eu/feed/"),
    ("YourStory", "https://yourstory.com/feed"),
]

# --- Scout Agent discovered sources (Task 5.1) ---
# Merged in from data/scout_sources.json, written by agents/scout_agent.py.
# Kept separate from the hand-curated FEEDS list above so Scout never touches this file.
def _load_scout_sources():
    import json
    path = os.path.join(os.path.dirname(__file__), "data", "scout_sources.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            sources = json.load(f)
        return [(s["name"], s["url"]) for s in sources if s.get("status") == "active"]
    except Exception:
        return []


FEEDS = FEEDS + _load_scout_sources()

# --- Pipeline settings ---
LOOKBACK_HOURS = 72          # how far back to pull articles each run (72 hours = 3 days)
ABSOLUTE_CUTOFF_DATE = "2026-07-01T00:00:00+00:00"  # HARD CUTOFF: Never process articles older than this
CLUSTER_SIMILARITY_THRESHOLD = 0.28   # 0-1, higher = stricter matching for "same story"
TOP_N_STORIES = 12           # how many stories make it into the digest
MIN_IMPORTANCE_SCORE = 3     # drop clusters scored below this (1-10 scale)

# --- Database ---
DB_PATH = os.path.join(os.path.dirname(__file__), "digest.db")

# --- LLM Provider ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude").lower()  # "claude" or "groq"

# --- Claude API ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-6"

# --- Groq API ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Using currently available Groq model. If this fails, try:
# - llama-3.1-8b-instant (small, fast)
# - llama-3.3-70b-versatile (latest stable)
# - gemma2-9b-it (alternative)
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Email (SMTP) ---
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
DIGEST_RECIPIENT = os.getenv("DIGEST_RECIPIENT")  # your own email, for now

# --- Website (Task: full-article site) ---
# Base URL of the public Next.js site (web/). Email headlines link to
# {SITE_BASE_URL}/articles/{id} for the full article instead of an external source.
# Update this to your deployed domain once the site is live.
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "http://localhost:3000")

# --- Testing ---
DIGEST_TEST_MODE = int(os.getenv("DIGEST_TEST_MODE", "1"))  # 1 = save to file, 0 = send email

# --- Orchestration (Task 5.2) ---
# When True, digest.py routes through agents/orchestration_graph.py (LangGraph-based
# StateGraph with conditional QA<->Editor backup edges and parallel fact-checking)
# instead of the linear agents.agent_coordinator call chain. Both produce identical output.
USE_LANGGRAPH_ORCHESTRATION = os.getenv("USE_LANGGRAPH_ORCHESTRATION", "0") == "1"
