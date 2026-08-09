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
    ("Anthropic", "https://rsshub.bestblogs.dev/anthropic/news"),
    # ("Mistral AI", "https://rsshub.bestblogs.dev/mistral/blog"),
    ("Cohere", "https://rsshub.bestblogs.dev/cohere/blog"),
    ("Perplexity", "https://rsshub.bestblogs.dev/perplexity/blog"),
    ("Groq", "https://rsshub.bestblogs.dev/groq/news"),
    ("Stability AI", "https://rsshub.bestblogs.dev/stability/news"),
    ("Cursor", "https://rsshub.bestblogs.dev/cursor/blog"),
    
    # 2. AI Research
    ("arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI"),
    ("arXiv cs.LG", "https://export.arxiv.org/rss/cs.LG"),
    ("arXiv cs.CL", "https://export.arxiv.org/rss/cs.CL"),
    ("Papers with Code", "https://www.paperswithcode.com/api/paper/featured/latest/rss/"),
    ("Semantic Scholar", "https://www.semanticscholar.org/rss"),
    
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
    ("Reddit LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/.rss"),
    ("Reddit MachineLearning", "https://www.reddit.com/r/MachineLearning/.rss"),
    ("Reddit Artificial", "https://www.reddit.com/r/artificial/.rss"),
    
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
]

# --- Pipeline settings ---
LOOKBACK_HOURS = 24          # how far back to pull articles each run
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
