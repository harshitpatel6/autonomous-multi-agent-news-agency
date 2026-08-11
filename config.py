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
    # ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    # ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    # ("Ars Technica AI", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    # ("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed/"),
    # ("VentureBeat AI", "https://venturebeat.com/ai/feed/"),
    # ("MarkTechPost", "https://www.marktechpost.com/feed/"),
    
    # 5. Developer Communities
    # NOTE: this is a broad keyword query over ALL new HN posts (not a curated AI section),
    # so it pulls in off-topic submissions whose title/URL just happens to contain "AI",
    # "LLM", or "agent" somewhere. Worse, for link posts to twitter.com/x.com, utils/fulltext.py's
    # trafilatura scrape of the linked page can grab a different tweet than the one the HN
    # title is actually about (X's non-JS HTML is unreliable for isolating one specific status) -
    # so the "source" title shown on an article can look completely unrelated to the story text,
    # even though the story text itself is accurately summarized from whatever got scraped.
    # Seen in the wild: cluster 237 ("AI Agent Finds Workaround") cited HN post "I built the AI
    # platform for a company crucial to a small nation's food safety" as its only source.
    # ("Hacker News AI", "https://hnrss.org/newest?q=AI+OR+LLM+OR+agent"),
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
    # ("TechCrunch Startups", "https://techcrunch.com/category/startups/feed/"),
    # ("Crunchbase News", "https://news.crunchbase.com/feed/"),
    # ("Inc42", "https://inc42.com/feed/"),
    # ("Sifted", "https://sifted.eu/feed/"),
    # ("YourStory", "https://yourstory.com/feed"),


    #9.USA VC and accelerators
    ("Andreessen Horowitz", "https://a16z.com/feed/"),
    ("Sequoia Capital", "https://www.sequoiacap.com/feed/"),
    ("First Round Review", "https://review.firstround.com/feed.xml"),
    ("National Venture Capital Association", "https://nvca.org/feed/"),
    ("Brad Feld / Foundry", "https://feld.com/feed"),
    ("Gust", "https://gust.com/blog/feed"),
    ("VC Cafe", "https://vccafe.com/feed/"),
    ("LifeSciVC", "https://lifescivc.com/feed/"),
    ("AVC / Fred Wilson", "https://avc.com/feed/"),
    ("Both Sides of the Table", "https://bothsidesofthetable.com/feed"),
    ("Seth Levine / Foundry", "https://www.sethlevine.com/feed/"),

    # US VC / Accelerator Medium feeds
    ("Boost VC", "https://medium.com/feed/boost-vc"),
    ("Aleph VC", "https://medium.com/feed/aleph-vc"),
    ("500 Global", "https://500.co/feed/"),

    # UK / Europe
    ("Playfair Capital", "https://medium.com/feed/playfair-capital-blog"),
    ("Northstar Ventures", "https://northstarventures.co.uk/feed"),
    ("Peak Capital", "https://peak.capital/rss"),
    ("Octopus Ventures", "https://octopusventures.com/blog/feed"),
    ("Molten Ventures", "https://www.moltenventures.com/insights/feed"),
    ("Fuel Ventures", "https://fuel.ventures/news/feed"),

    # Individual VC / Investor feeds
    ("Tomasz Tunguz", "https://tomtunguz.com/index.xml"),
    ("Hunter Walk", "https://hunterwalk.com/feed"),
    ("David G. Cohen", "https://feeds.feedburner.com/DavidGCohen"),
    ("Jalak Jobanputra", "https://thebarefootvc.com/feed"),
    ("Christoph Janz", "https://christophjanz.blogspot.com/feeds/posts/default"),
    ("David Teten", "https://teten.com/feed"),
    ("Gotham Gal", "https://gothamgal.com/feed"),
    ("Paul Graham", "https://paulgraham.com/rss.xml"),

    ("Latitud", "https://latitudlatam.substack.com/feed"),
    ("Rockstart", "https://rockstart.pr.co/en/releases/rss"),

    # Individual VC / Investor feeds
    ("Maverick Ventures Israel", "https://maverick.vc/blog-feed.xml"),
    ("Vintage Investment Partners", "https://vintage-ip.com/feed"),
    ("Viola Group", "https://viola-group.com/feed"),
    ("OurCrowd", "https://blog.ourcrowd.com/feed"),
    ("Team8", "https://team8.vc/feed"),
    ("Fusion VC", "https://blog.fusion-vc.com/feed"),
    ("TLV Partners", "https://tlv.partners/feed"),
    ("Moneta Venture Capital", "https://monetavc.com/category/blog/feed"),
    ("NFX", "https://nfx.com/feed"),
    ("F2 Venture Capital", "https://f2vc.com/feed"),
    ("Elron Ventures", "https://elronventures.com/feed"),
    ("Vertex Ventures Israel", "https://vertexventures.co.il/feed"),
    ("Qumra Capital", "https://qumracapital.com/feed"),
    ("BRM Group", "https://brm.com/feed"),
    ("Grove Ventures", "https://grovevc.com/feed"),
    ("MizMaa Ventures", "https://mizmaa.com/feed"),
    ("Glilot Capital Partners", "https://glilotcapital.com/feed"),

    # Individual VC / Investor feeds
    ("Blume Ventures", "https://blume.vc/rss-feed"),
    ("Inflection Point Ventures", "https://ipventures.in/feed"),

    # Hong Kong
    ("Hong Kong Cyberport", "OFFICIAL RSS/XML — Cyberport Event feed"),
    ("CP Ventures", "https://cp.ventures/feed"),

    # Canada
    ("Georgian", "https://georgian.io/feed"),
    ("Vanedge Capital", "https://vanedgecapital.com/news/feed"),
    ("iGan Partners", "https://iganpartners.com/feed"),
    ("Concrete Ventures", "https://concrete.vc/feed"),
    ("Brightspark", "https://brightspark.com/blog/feed"),


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
    ("DigitalOcean", "https://www.digitalocean.com/blog/rss.xml"),
    ("Twilio", "https://www.twilio.com/blog/feed"),
    ("Elastic", "https://www.elastic.co/blog/feed"),
    ("Datadog", "https://www.datadoghq.com/blog/feed/"),
    ("MongoDB", "https://www.mongodb.com/blog/rss"),
    ("Redis", "https://redis.io/blog/rss.xml"),
    ("HashiCorp", "https://www.hashicorp.com/blog/feed.xml"),
    ("Vercel", "https://vercel.com/atom"),
    ("Netlify", "https://www.netlify.com/blog/feed/"),
    ("Heroku", "https://blog.heroku.com/feed"),
    ("Stripe", "https://stripe.com/blog/feed.rss"),
    ("Shopify", "https://www.shopify.com/blog.atom"),
    ("HubSpot", "https://blog.hubspot.com/rss.xml"),
    ("Atlassian", "https://www.atlassian.com/blog/feed"),
    ("Slack", "https://slack.com/intl/en-in/blog/feed"),
    ("Intercom", "https://www.intercom.com/blog/feed"),
    ("Zapier", "https://zapier.com/blog/rss/"),
    ("Notion", "https://www.notion.com/blog/rss.xml"),
    ("Figma", "https://www.figma.com/blog/feed/"),
    ("Canva", "https://www.canva.com/newsroom/feed/"),
    ("Airtable", "https://blog.airtable.com/feed/"),
    ("Asana", "https://asana.com/guide/feed"),
    ("GitLab", "https://about.gitlab.com/atom.xml"),
    ("Sentry", "https://blog.sentry.io/rss/"),
    ("Postman", "https://blog.postman.com/feed/"),
    ("Supabase", "https://supabase.com/blog/rss.xml"),
    ("Prisma", "https://www.prisma.io/blog/rss.xml"),
    ("Deno", "https://deno.com/blog/rss.xml"),
    ("Rust", "https://blog.rust-lang.org/feed.xml"),
    ("Python", "https://blog.python.org/rss.xml"),

    # Developer tools / infrastructure

    ("Tailscale", "https://tailscale.com/blog/index.xml"),
    ("DuckDB", "https://duckdb.org/feed.xml"),
    ("Fly.io", "https://fly.io/blog/feed.xml"),
    ("Sourcegraph", "https://sourcegraph.com/blog/rss.xml"),
    ("Astral", "https://astral.sh/blog/rss.xml"),
    ("Dagger", "https://dagger.io/blog/rss.xml"),
    ("Pulumi", "https://www.pulumi.com/blog/rss.xml"),
    ("CircleCI", "https://circleci.com/blog/feed/"),
    ("Snyk", "https://snyk.io/blog/feed/"),
    ("JFrog", "https://jfrog.com/blog/feed/"),
    ("Grafana Labs", "https://grafana.com/blog/index.xml"),
    ("Prometheus", "https://prometheus.io/blog/feed.xml"),
    ("Grafbase", "https://grafbase.com/blog/rss.xml"),
    ("Caddy", "https://caddyserver.com/blog/index.xml"),

    # SaaS / productivity

    ("Linear", "https://linear.app/changelog/rss.xml"),
    ("1Password", "https://blog.1password.com/rss/"),
    ("Obsidian", "https://obsidian.md/blog/rss.xml"),
    ("Todoist", "https://todoist.com/inspiration/feed"),
    ("Miro", "https://miro.com/blog/feed/"),
    ("ClickUp", "https://clickup.com/blog/feed/"),
    ("Monday.com", "https://monday.com/blog/feed/"),
    ("Loom", "https://www.loom.com/blog/rss.xml"),
    ("Calendly", "https://calendly.com/blog/rss.xml"),
    ("Typeform", "https://www.typeform.com/blog/feed/"),
    ("Webflow", "https://webflow.com/blog/rss.xml"),
    ("Framer", "https://www.framer.com/blog/rss.xml"),
    ("Ghost", "https://ghost.org/changelog/rss/"),
    ("Buffer", "https://buffer.com/resources/feed/"),

    # Security / cybersecurity

    ("Malwarebytes", "https://www.malwarebytes.com/blog/feed"),
    ("Tenable", "https://www.tenable.com/blog/feed"),
    ("Rapid7", "https://www.rapid7.com/blog/rss.xml"),
    ("Okta", "https://sec.okta.com/rss.xml"),
    ("Akamai", "https://www.akamai.com/blog/rss"),

    # Fintech / payments / financial technology

    ("Mercury", "https://mercury.com/blog/rss.xml"),
    ("Plaid", "https://plaid.com/blog/feed/"),
    ("Brex", "https://www.brex.com/journal/rss.xml"),
    ("Ramp", "https://ramp.com/blog/rss.xml"),
    ("Modern Treasury", "https://www.moderntreasury.com/journal/rss.xml"),
    ("Lithic", "https://blog.lithic.com/rss.xml"),
    ("Marqeta", "https://www.marqeta.com/blog/feed"),
    ("Unit", "https://www.unit.co/blog/rss.xml"),
    ("Treasury Prime", "https://www.treasuryprime.com/blog/rss.xml"),
    ("Moov", "https://moov.io/blog/feed/"),

    # Ecommerce / marketplace / consumer

    ("Faire", "https://www.faire.com/blog/rss.xml"),
    ("Gorgias", "https://www.gorgias.com/blog/rss.xml"),
    ("Klaviyo", "https://www.klaviyo.com/blog/rss.xml"),
    ("Recharge", "https://rechargepayments.com/blog/feed/"),
    ("Yotpo", "https://www.yotpo.com/blog/feed/"),
    ("Gumroad", "https://gumroad.com/blog/rss"),
    ("Vinted", "https://company.vinted.com/newsroom/rss.xml"),
    ("Depop", "https://news.depop.com/rss"),
    ("DoorDash", "https://doordash.news/rss.xml"),
    ("Instacart", "https://instacart.corporate-newsroom.com/rss"),

    ("Bun", "https://bun.com/blog/rss.xml"),
    ("Zed", "https://zed.dev/blog/rss.xml"),
    ("Warp", "https://www.warp.dev/blog/rss.xml"),
    ("Raycast", "https://www.raycast.com/blog/rss.xml"),
    ("Temporal", "https://temporal.io/blog/rss.xml"),
    ("PlanetScale", "https://planetscale.com/blog/rss.xml"),
    ("Neon", "https://neon.com/blog/rss.xml"),
    ("Convex", "https://www.convex.dev/blog/rss.xml"),
    ("Turso", "https://turso.tech/blog/rss.xml"),
    ("Drizzle", "https://orm.drizzle.team/rss.xml"),

    ("AWS Architecture Blog", "https://aws.amazon.com/blogs/architecture/feed/"),
    ("Google Cloud", "https://cloud.google.com/feeds/blog.xml"),
    ("IBM", "https://www.ibm.com/blogs/think/feed/"),
    ("Oracle", "https://blogs.oracle.com/feed"),
    ("Red Hat Developer", "https://developers.redhat.com/blog/feed"),
    ("VMware", "https://blogs.vmware.com/feed/"),
    ("OpenStack", "https://www.openstack.org/blog/feed"),

    ("SAP", "https://news.sap.com/feed/"),
    ("ServiceNow", "https://www.servicenow.com/blogs/rss.xml"),
    ("Workday", "https://blog.workday.com/en-us/feed.xml"),
    ("DocuSign", "https://www.docusign.com/blog/feed"),
    ("Zendesk", "https://www.zendesk.com/blog/feed/"),
    ("Freshworks", "https://www.freshworks.com/blog/feed/"),
    ("Twilio Segment", "https://segment.com/blog/feed/"),
    ("DataCamp", "https://www.datacamp.com/blog/rss.xml"),
    ("Udemy", "https://blog.udemy.com/feed/"),
    ("Coursera", "https://blog.coursera.org/feed/"),

    ("Reddit", "https://www.redditinc.com/blog/rss.xml"),
    ("Pinterest", "https://newsroom.pinterest.com/en/feed"),
    ("Snap", "https://newsroom.snap.com/feed"),
    ("Spotify", "https://newsroom.spotify.com/feed/"),
    ("TikTok Newsroom", "https://newsroom.tiktok.com/en-us/rss"),
    ("Discord", "https://discord.com/blog/rss.xml"),
    ("Telegram", "https://telegram.org/blog/rss"),

    ("AMD", "https://community.amd.com/s/feed/0D5xx000008TnJbCAK"),
    ("Qualcomm", "https://www.qualcomm.com/news/onq/rss.xml"),
    ("Arm", "https://newsroom.arm.com/rss.xml"),
    ("TSMC", "https://pr.tsmc.com/english/rss"),
    ("ASML", "https://www.asml.com/en/news/stories.rss"),
    ("Samsung Electronics", "https://news.samsung.com/global/feed"),
    ("Sony", "https://www.sony.com/en/SonyInfo/News/rss/"),
    ("Micron", "https://investors.micron.com/rss/news-releases.xml"),

    ("Rust Foundation", "https://foundation.rust-lang.org/feed/"),
    ("Linux Foundation", "https://www.linuxfoundation.org/blog/feed"),
    ("CNCF", "https://www.cncf.io/blog/feed/"),
    ("KDE", "https://kde.org/announcements/index.xml"),
    ("GNOME", "https://release.gnome.org/rss.xml"),
    ("Python Software Foundation", "https://pyfound.blogspot.com/feeds/posts/default"),

    ("Google", "https://blog.google/feed/"),
    ("Meta Engineering", "https://engineering.fb.com/feed/"),
    ("Spotify Engineering", "https://engineering.atspotify.com/feed"),
    ("Dropbox Tech", "https://dropbox.tech/feed"),
    ("JetBrains", "https://blog.jetbrains.com/feed/"),
    ("Stack Overflow", "https://stackoverflow.blog/feed/"),
    ("IBM Research", "https://research.ibm.com/blog/rss.xml"),
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
LOOKBACK_HOURS = 72          # how far back to pull articles each run (72 hours = 3 days)
ABSOLUTE_CUTOFF_DATE = "2026-07-01T00:00:00+00:00"  # HARD CUTOFF: Never process articles older than this
CLUSTER_SIMILARITY_THRESHOLD = 0.28   # 0-1, higher = stricter matching for "same story"
TOP_N_STORIES = 12           # how many stories make it into the EMAIL digest only (site has no cap)
MIN_IMPORTANCE_SCORE = 3     # drop clusters scored below this (1-10 scale)
SUMMARIZE_BATCH_SIZE = 150   # max clusters summarized per pipeline run (site runs every 15 min via publish.py)

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
# NOTE: "gemini-2.0-flash" returns 429/quota=0 on this key's project (blocked for
# new users on that specific model) - "-latest" aliases route around that.
GEMINI_MODEL = "gemini-flash-latest"

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
