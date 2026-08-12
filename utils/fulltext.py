"""
Full-article text + lead-image fetching. RSS feeds only give a short teaser in
summary_raw - e.g. Inc42's feed cuts off at ~400 chars mid-sentence ("...This
marks&#8230;") - which isn't enough source material for the Writer/Reporter agents to
produce real coverage, no matter how the prompt is worded. This fetches and extracts
the actual article body from the source URL so they have something real to work from,
and - piggybacking on that same download - the article's own og:image/twitter:image,
so the site can show the real photo the original publisher used for that story instead
of a generic placeholder.

Best-effort: many sites will fail (paywalls, bot-blocking, timeouts, non-article
pages) and callers should fall back to summary_raw when this returns "".
"""
import html
import json as _json

import trafilatura
from lxml import html as lxml_html

from db import get_connection

MAX_CHARS = 6000  # bound LLM input cost; article bodies rarely need more than this
MIN_CHARS = 200    # shorter than this isn't meaningfully better than the RSS teaser

# Priority order for the page's lead image. og:image is the de facto standard; the
# twitter:* and <link rel="image_src"> variants are older/alternate spellings some
# sites use instead of (or as well as) it. Checked via XPath rather than a regex
# because <meta> ATTRIBUTE ORDER isn't standardized - e.g. Anthropic's Webflow-hosted
# blog emits <meta content="...jpg" property="og:image"/> (content before property),
# which used to slip past a regex anchored on "property=...content=" even though the
# page unambiguously has a valid image. XPath attribute lookups don't care about order.
_META_IMAGE_XPATHS = (
    '//meta[@property="og:image"]/@content',
    '//meta[@name="og:image"]/@content',
    '//meta[@property="twitter:image"]/@content',
    '//meta[@name="twitter:image"]/@content',
    '//meta[@name="twitter:image:src"]/@content',
    '//link[@rel="image_src"]/@href',
)

# Several active feeds (config.py's "AI Engineering & Open Source" section) are GitHub
# Releases/Atom feeds - e.g. vLLM, Ollama, LangChain, Groq. Their entries link to a
# specific release tag, not an editorial article, so there's no body text to extract
# (handled fine below - it just stays ""). GitHub *does* put an og:image on every
# release page (either the repo's own social-preview banner, or an auto-generated
# card), so the normal extraction below usually finds one there directly. This map is
# also used for non-GitHub sources confirmed to carry no per-post image at all (e.g.
# PyTorch's blog posts have zero og:image/twitter:image/JSON-LD image metadata,
# verified directly - not a scraping gap, the pages just don't have one) - it re-tries
# against a stable page for that source that's confirmed to always have a social-
# preview image, instead of leaving these sources with no image at all.
SOURCE_REPO_FALLBACK = {
    "Groq": "https://github.com/groq/groq-python",
    "Stability AI": "https://github.com/stability-ai/stablelm",
    "Papers with Code": "https://github.com/paperswithcode/paperswithcode-data",
    "Semantic Scholar": "https://github.com/allenai/s2orc",
    "LangChain": "https://github.com/langchain-ai/langchain",
    "LlamaIndex": "https://github.com/run-llama/llama_index",
    "vLLM": "https://github.com/vllm-project/vllm",
    "Ollama": "https://github.com/ollama/ollama",
    "LiteLLM": "https://github.com/BerriAI/litellm",
    "Open WebUI": "https://github.com/open-webui/open-webui",
    "ComfyUI": "https://github.com/comfyanonymous/ComfyUI",
    "Mistral Inference": "https://github.com/mistralai/mistral-inference",
    "PyTorch Blog": "https://pytorch.org/",
    # Anthropic's blog sets og:image/twitter:image to content="" (present but empty) on
    # some posts - a genuine no-image case at the source, not a scrape failure. Falls
    # back to the blog index page's own social-preview card, verified non-empty.
    "Anthropic": "https://claude.com/blog",
}


def _clean_image_url(raw: str) -> str:
    # The attribute value is raw HTML source (e.g. "...&amp;h=900..."); browsers
    # unescape that automatically when parsing markup, but here we hand the string
    # straight to React as a src prop, which sets it as a literal DOM attribute value
    # with no HTML-entity decoding - so "&amp;" would end up in the actual request URL
    # unless unescaped here first.
    url = html.unescape((raw or "").strip())
    return url if url.startswith("http") else ""


def _first_jsonld_image_url(image) -> str:
    """schema.org's "image" field can be a URL string, a list of URL strings, or an
    ImageObject with its own "url" field - normalize all three shapes to one URL."""
    if isinstance(image, str):
        return _clean_image_url(image)
    if isinstance(image, dict):
        return _first_jsonld_image_url(image.get("url"))
    if isinstance(image, list) and image:
        return _first_jsonld_image_url(image[0])
    return ""


def _iter_jsonld_nodes(data):
    """Yields every dict node in a JSON-LD payload, including ones nested under
    "@graph" (the shape most WordPress SEO plugins, e.g. Yoast, actually emit)."""
    if isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                yield from _iter_jsonld_nodes(node)
    elif isinstance(data, list):
        for node in data:
            yield from _iter_jsonld_nodes(node)


def _extract_image_meta(page_html: str) -> str:
    if not page_html:
        return ""
    try:
        doc = lxml_html.fromstring(page_html)
    except Exception:
        return ""

    for xpath in _META_IMAGE_XPATHS:
        try:
            values = doc.xpath(xpath)
        except Exception:
            continue
        for value in values:
            url = _clean_image_url(value)
            if url:
                return url

    # Last resort: JSON-LD structured data. Several blog platforms (WordPress, Ghost)
    # populate an Article/NewsArticle/BlogPosting "image" field here even on pages
    # that skip social-preview meta tags entirely.
    try:
        scripts = doc.xpath('//script[@type="application/ld+json"]/text()')
    except Exception:
        scripts = []
    for script in scripts:
        try:
            data = _json.loads(script)
        except Exception:
            continue
        for node in _iter_jsonld_nodes(data):
            url = _first_jsonld_image_url(node.get("image"))
            if url:
                return url

    return ""


def _fetch_image_only(url: str) -> str:
    try:
        downloaded = trafilatura.fetch_url(url)
    except Exception:
        return ""
    return _extract_image_meta(downloaded) if downloaded else ""


def _extract(url: str, source: str = "") -> tuple:
    """Returns (body_text, image_url) - either half can be "" independently of the other."""
    if not url:
        return "", ""
    try:
        downloaded = trafilatura.fetch_url(url)
    except Exception:
        downloaded = None

    text = ""
    if downloaded:
        try:
            extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False) or ""
            text = extracted[:MAX_CHARS] if len(extracted) >= MIN_CHARS else ""
        except Exception:
            text = ""

    image_url = _extract_image_meta(downloaded) if downloaded else ""
    if not image_url and source in SOURCE_REPO_FALLBACK:
        image_url = _fetch_image_only(SOURCE_REPO_FALLBACK[source])

    return text, image_url


def get_full_text(article_id: int, url: str, source: str = "") -> str:
    """
    Cached full-text fetch for one article row: articles.full_text is NULL until the
    first attempt, then always a string ("" on failure). Caching failures too means a
    dead/blocked URL only gets tried once, not re-fetched on every summarize/write pass
    or self-healing retry cycle.

    Piggybacks the same download onto image_url (see module docstring) - passing
    `source` lets it fall back to a known repo page for GitHub-release feeds that have
    no article image of their own. image_url is only ever set here if it isn't already
    (ingest.py may have already found one straight from the RSS entry - that wins).

    image_url is intentionally *not* covered by the full_text cache: full_text caches
    forever (even ""), but a row with text and no image just means the image scrape
    came up empty on that attempt (or predates this feature) - not a permanent fact
    about the page. So a cached-text row with no image_url still gets one lightweight
    image-only retry per call here, self-healing old rows without re-running the (more
    expensive) text extraction.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT full_text, image_url FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    if row and row["full_text"] is not None:
        conn.close()
        cached_text = row["full_text"]
        if row["image_url"]:
            return cached_text
        image_url = _fetch_image_only(url)
        if not image_url and source in SOURCE_REPO_FALLBACK:
            image_url = _fetch_image_only(SOURCE_REPO_FALLBACK[source])
        if image_url:
            conn = get_connection()
            conn.execute(
                "UPDATE articles SET image_url = ? WHERE id = ?", (image_url, article_id)
            )
            conn.commit()
            conn.close()
        return cached_text
    conn.close()

    text, image_url = _extract(url, source)

    conn = get_connection()
    conn.execute(
        "UPDATE articles SET full_text = ?, image_url = COALESCE(image_url, ?) WHERE id = ?",
        (text, image_url or None, article_id),
    )
    conn.commit()
    conn.close()
    return text
