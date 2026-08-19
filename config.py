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
    # Third-party news/media outlets removed entirely (not just disabled) - copyright/
    # reprint risk on syndicated journalism, as opposed to a company's own blog posts.
    # ("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed/"),
    # ("VentureBeat AI", "https://venturebeat.com/ai/feed/"),

    # 5. Developer Communities
    # Hacker News AI (hnrss keyword query) removed entirely - copyright/reprint risk on
    # syndicated journalism it links out to, same as the Technology News sources above.
    # ("Reddit LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/.rss"),
    # ("Reddit MachineLearning", "https://www.reddit.com/r/MachineLearning/.rss"),
    # ("Reddit Artificial", "https://www.reddit.com/r/artificial/.rss"),
    
    # 6. Big Tech AI
    ("Microsoft AI Blog", "https://www.microsoft.com/en-us/research/feed/"),
    ("AWS ML Blog", "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("NVIDIA Developer", "https://developer.nvidia.com/blog/feed/"),
    ("Meta Research", "https://research.facebook.com/feed/"),
    
    # 7. Additional Quality Sources
    ("Towards Data Science", "https://towardsdatascience.com/feed"),
    ("AI Trends", "https://www.aitrends.com/feed/"),

    # 8. Business, Funding & Startups
    # Feeds AI companies' new products/enterprise adoption, funding rounds, and new
    # startup launches. Classification into "Business & Enterprise AI" /
    # "Funding & Investment" / "Startup Launches" happens per-cluster by the Reporter
    # Agent's LLM prompt (agents/reporter_agent.py), not per-feed.


    #9.USA VC and accelerators
    ("National Venture Capital Association", "https://nvca.org/feed/"),
    ("Brad Feld / Foundry", "https://feld.com/feed"),
    ("Gust", "https://gust.com/blog/feed"),
    ("VC Cafe", "https://vccafe.com/feed/"),
    ("LifeSciVC", "https://lifescivc.com/feed/"),
    ("AVC / Fred Wilson", "https://avc.com/feed/"),

    # US VC / Accelerator Medium feeds
    ("Boost VC", "https://medium.com/feed/boost-vc"),
    ("Aleph VC", "https://medium.com/feed/aleph-vc"),
    ("500 Global", "https://500.co/feed/"),

    # UK / Europe
    ("Playfair Capital", "https://medium.com/feed/playfair-capital-blog"),
    ("Northstar Ventures", "https://northstarventures.co.uk/feed"),
    ("Peak Capital", "https://peak.capital/rss"),

    # Individual VC / Investor feeds
    ("Tomasz Tunguz", "https://tomtunguz.com/index.xml"),
    ("Hunter Walk", "https://hunterwalk.com/feed"),
    ("David G. Cohen", "https://feeds.feedburner.com/DavidGCohen"),
    ("Christoph Janz", "https://christophjanz.blogspot.com/feeds/posts/default"),
    ("David Teten", "https://teten.com/feed"),
    ("Gotham Gal", "https://gothamgal.com/feed"),

    ("Latitud", "https://latitudlatam.substack.com/feed"),

    # Individual VC / Investor feeds
    ("Maverick Ventures Israel", "https://maverick.vc/blog-feed.xml"),
    ("Vintage Investment Partners", "https://vintage-ip.com/feed"),
    ("Viola Group", "https://viola-group.com/feed"),
    ("Team8", "https://team8.vc/feed"),
    ("Fusion VC", "https://blog.fusion-vc.com/feed"),
    ("TLV Partners", "https://tlv.partners/feed"),
    ("Moneta Venture Capital", "https://monetavc.com/category/blog/feed"),
    ("Elron Ventures", "https://elronventures.com/feed"),
    ("Qumra Capital", "https://qumracapital.com/feed"),
    ("BRM Group", "https://brm.com/feed"),

    # Individual VC / Investor feeds
    ("Inflection Point Ventures", "https://ipventures.in/feed"),

    # Canada
    ("Vanedge Capital", "https://vanedgecapital.com/news/feed"),
    ("iGan Partners", "https://iganpartners.com/feed"),
    ("Concrete Ventures", "https://concrete.vc/feed"),


    # Japan
    ("Rebright Partners", "https://rebrightpartners.com/feed"),


    # New Zealand
    ("Matū", "https://matu.co.nz/feed"),
    ("Enterprise Angels", "https://enterpriseangels.co.nz/feed"),

    ("Y Combinator", "https://www.ycombinator.com/blog/rss"),


    # Company / Startup RSS
    ("GitHub", "https://github.blog/feed/"),
    ("Cloudflare", "https://blog.cloudflare.com/rss/"),
    ("Mozilla", "https://blog.mozilla.org/feed/"),
    ("Docker", "https://www.docker.com/feed/"),
    ("Twilio", "https://www.twilio.com/blog/feed"),
    ("Elastic", "https://www.elastic.co/blog/feed"),
    ("MongoDB", "https://www.mongodb.com/blog/rss"),
    ("HashiCorp", "https://www.hashicorp.com/blog/feed.xml"),
    ("Vercel", "https://vercel.com/atom"),
    ("Heroku", "https://blog.heroku.com/feed"),
    ("Stripe", "https://stripe.com/blog/feed.rss"),
    ("Intercom", "https://www.intercom.com/blog/feed"),
    ("Zapier", "https://zapier.com/blog/rss/"),
    ("Airtable", "https://blog.airtable.com/feed/"),
    ("GitLab", "https://about.gitlab.com/atom.xml"),
    ("Postman", "https://blog.postman.com/feed/"),
    ("Prisma", "https://www.prisma.io/blog/rss.xml"),
    ("Rust", "https://blog.rust-lang.org/feed.xml"),
    ("Python", "https://blog.python.org/rss.xml"),

    # Developer tools / infrastructure

    ("Tailscale", "https://tailscale.com/blog/index.xml"),
    ("DuckDB", "https://duckdb.org/feed.xml"),
    ("Fly.io", "https://fly.io/blog/feed.xml"),
    ("Sourcegraph", "https://sourcegraph.com/blog/rss.xml"),
    ("Astral", "https://astral.sh/blog/rss.xml"),
    ("Pulumi", "https://www.pulumi.com/blog/rss.xml"),
    ("Snyk", "https://snyk.io/blog/feed/"),
    ("JFrog", "https://jfrog.com/blog/feed/"),
    ("Grafana Labs", "https://grafana.com/blog/index.xml"),
    ("Prometheus", "https://prometheus.io/blog/feed.xml"),

    # SaaS / productivity

    ("Webflow", "https://webflow.com/blog/rss.xml"),
    ("Ghost", "https://ghost.org/changelog/rss/"),
    ("Buffer", "https://buffer.com/resources/feed/"),

    # Security / cybersecurity

    ("Malwarebytes", "https://www.malwarebytes.com/blog/feed"),
    ("Tenable", "https://www.tenable.com/blog/feed"),
    ("Okta", "https://sec.okta.com/rss.xml"),

    # Fintech / payments / financial technology

    ("Modern Treasury", "https://www.moderntreasury.com/journal/rss.xml"),

    # Ecommerce / marketplace / consumer

    ("Gorgias", "https://www.gorgias.com/blog/rss.xml"),
    ("Recharge", "https://rechargepayments.com/blog/feed/"),

    ("PlanetScale", "https://planetscale.com/blog/rss.xml"),
    ("Neon", "https://neon.com/blog/rss.xml"),

    ("AWS Architecture Blog", "https://aws.amazon.com/blogs/architecture/feed/"),
    ("Red Hat Developer", "https://developers.redhat.com/blog/feed"),
    ("VMware", "https://blogs.vmware.com/feed/"),

    ("SAP", "https://news.sap.com/feed/"),
    ("DocuSign", "https://www.docusign.com/blog/feed"),
    ("Coursera", "https://blog.coursera.org/feed/"),

    ("Reddit", "https://www.redditinc.com/blog/rss.xml"),
    ("Snap", "https://newsroom.snap.com/feed"),
    ("Spotify", "https://newsroom.spotify.com/feed/"),
    ("Discord", "https://discord.com/blog/rss.xml"),

    ("Samsung Electronics", "https://news.samsung.com/global/feed"),

    ("Rust Foundation", "https://foundation.rust-lang.org/feed/"),
    ("CNCF", "https://www.cncf.io/blog/feed/"),
    ("KDE", "https://kde.org/announcements/index.xml"),
    ("Python Software Foundation", "https://pyfound.blogspot.com/feeds/posts/default"),

    ("Meta Engineering", "https://engineering.fb.com/feed/"),
    ("Spotify Engineering", "https://engineering.atspotify.com/feed"),
    ("Dropbox Tech", "https://dropbox.tech/feed"),
    ("JetBrains", "https://blog.jetbrains.com/feed/"),
    ("Stack Overflow", "https://stackoverflow.blog/feed/"),
    ("Microsoft Security", "https://www.microsoft.com/en-us/security/blog/feed/"),
    ("Cisco Security", "https://blogs.cisco.com/security/feed"),
    ("Palo Alto Networks Unit 42", "https://unit42.paloaltonetworks.com/feed/"),
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
LOOKBACK_HOURS = 24         # how far back to pull articles each run (72 hours = 3 days)
ABSOLUTE_CUTOFF_DATE = "2026-07-01T00:00:00+00:00"  # HARD CUTOFF: Never process articles older than this
CLUSTER_SIMILARITY_THRESHOLD = 0.28   # 0-1, higher = stricter matching for "same story"
TOP_N_STORIES = 12           # how many stories make it into the EMAIL digest only (site has no cap)
MIN_IMPORTANCE_SCORE = 3     # drop clusters scored below this (1-10 scale)
SUMMARIZE_BATCH_SIZE = 150   # max clusters summarized per pipeline run (site runs every 15 min via publish.py)

# Publish-candidate retry cap (cost control): a cluster that keeps failing Writer /
# defamation-check used to get re-run through the full LLM pipeline every single
# 15-min cycle forever, with no limit - an unbounded backlog silently turned into a
# retry storm that burned through provider quota reprocessing the same stuck stories.
# Now each cluster gets at most MAX_PUBLISH_ATTEMPTS tries (spaced out by the normal
# 15-min cycle) before being marked validation_status='rejected' and left alone.
# PUBLISH_CANDIDATE_BATCH_SIZE bounds how many candidates one run will even attempt,
# same pattern as SUMMARIZE_BATCH_SIZE/SEO's SWEEP_BATCH_SIZE.
MAX_PUBLISH_ATTEMPTS = 5
PUBLISH_CANDIDATE_BATCH_SIZE = 30

# Same retry-storm problem as MAX_PUBLISH_ATTEMPTS above, but on the already-published
# side: publish.py::retry_missing_full_content() re-attempts every published cluster
# still missing full_content on every 15-min cycle, with clusters.originality_attempts
# (bumped once per ensure_full_article() failure - see agents/writer_agent.py) as the
# only signal of how many times a given cluster has already failed. Discovered
# 2026-08-15 clearing the corpus-wide originality backlog: a genuinely thin, hard-to-
# transform single source (its Writer draft keeps tripping utils/similarity.py's gate
# even after 3 escalating in-attempt rewrites) will never pass no matter how many times
# it's retried, so without a cap it burns ~3 Gemini calls per cycle forever. Capped at
# the same value as MAX_PUBLISH_ATTEMPTS for consistency; a cluster that hits this limit
# just keeps rendering its short summary (safe fallback, not copied content) instead of
# a full article - no different from what it's already showing today.
MAX_FULL_CONTENT_RETRY_ATTEMPTS = 5

# The email digest (main.py) used to only be triggered by launchd at two fixed
# clock times (7:00/17:00). If the machine was asleep, off, or not logged in at
# that exact minute, launchd simply skipped the run with no catch-up - on a laptop
# that's only awake in the evenings, that meant the digest often never fired at
# all. main.py is now triggered on a short recurring interval instead (like
# publish.py already is) and self-guards with this: skip running again if the last
# digest went out less than this many hours ago, so a Mac that's on continuously
# for a while doesn't send duplicates. `main.py --force` bypasses this guard.
DIGEST_MIN_INTERVAL_HOURS = 6

# Same cost-control problem, one stage earlier: before this, a cluster that could
# never be summarized (bad/garbled source text, a prompt that reliably trips every
# provider's safety filter, etc.) had NO cap - summarize_clusters()'s query only
# checked `summary IS NULL`, so it re-entered the batch and burned a fresh
# Claude -> Groq -> Gemini attempt sequence every single 15-min cycle, forever,
# with nobody aware it was happening. Now a cluster gets at most
# MAX_AUTO_SUMMARIZE_ATTEMPTS automatic tries (tracked via clusters.summarize_attempts,
# see db.py) before the pipeline stops picking it up on its own; it's surfaced on the
# Processing History page instead, where a human can hit "Re-process" - a deliberate,
# rate-limited, one-cluster-at-a-time action (see summarize.py::reprocess_cluster) -
# once they believe the failure is worth spending another round of tokens on.
MAX_AUTO_SUMMARIZE_ATTEMPTS = 3
# Floor between reprocess attempts on the same cluster (auto or manual), so a
# double-click or a page left open in two tabs can't fire two LLM calls back-to-back
# for the same cluster.
SUMMARIZE_RETRY_COOLDOWN_SECONDS = 60

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

# --- Gemini API (third fallback tier, see agents/base_agent.py::call_llm) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# NOTE: both "gemini-2.0-flash" and "gemini-2.5-flash-lite" return 404 "no longer
# available to new users" on this key's project (Google blocks new keys from pinned
# versions of models it's since rolled forward) even though they still show up in
# ListModels - the "-latest" rolling aliases route around that and actually work.
GEMINI_MODEL = "gemini-flash-lite-latest"

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

# --- Originality / anti-plagiarism guardrail (utils/similarity.py) ---
# Added 2026-08-15 after a published article (cluster 537, KDNuggets' "Building an
# End-to-End Data Science Portfolio Project" - a single-source, tutorial-style piece)
# was found to closely mirror its one source's structure and specifics. Root cause:
# agents/writer_agent.py's prompt told the Writer to "pull out EVERY name/figure/example"
# from its sources, which for a tutorial (where the specific steps ARE the source's
# protected expression, not just facts) is nearly indistinguishable from a rewrite -
# and nothing in the pipeline ever compared generated text back against the actual
# source text to catch it (the one existing check, SUMMARY_DUPLICATE_RATIO in
# writer_agent.py, compares against the internal one-paragraph brief, not the source).
#
# Deliberately strict per product decision: the site would rather regenerate (or, after
# MAX_ORIGINALITY_REWRITE_ATTEMPTS, simply not publish) a story than ship one that reads
# as copied - no manual review step, this has to hold the line on its own. Thresholds
# were sanity-checked against cluster 537's actual generated/source text pair, which
# scored well above both cutoffs below; ordinary grounded-but-original writing (sharing
# names/numbers/terminology with its source without reusing its phrasing) scores well
# under them.
SIMILARITY_SHINGLE_SIZE = 6            # compare overlap in runs of 6 words at a time
SIMILARITY_JACCARD_THRESHOLD = 0.15    # >=15% of 6-word phrases shared with a source -> flagged
SIMILARITY_VERBATIM_RUN_WORDS = 9      # any run of 9+ consecutive words copied verbatim -> flagged
MAX_ORIGINALITY_REWRITE_ATTEMPTS = 3   # forced in-place rewrites (escalating instructions) before giving up

# --- Insights desk (agents/insight_agent.py) ---
# A second, separate content lane from the News desk above: original explainers,
# research roundups, synthesis, and opinion pieces, not tied to any one external
# source the way a `clusters` news story is. Its own table (`features`, see db.py)
# rather than reusing `clusters`/`articles`, deliberately - that schema assumes "N
# sources reporting one event," which is exactly the assumption that produced the
# over-extraction bug above; forcing evergreen/creative content through it would
# just recreate the same failure mode in a new place.
INSIGHTS_PER_RUN = 2                   # how many features to generate per insights.py run

