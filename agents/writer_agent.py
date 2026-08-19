"""
Staff Writer Agent: expands an already-approved, fact-checked cluster (headline +
short summary + source articles) into a full-length article for the website.

Only called for stories that already survived Reporter -> Fact-Checker -> Editor -> QA,
and only once per cluster (result is cached in clusters.full_content), so this doesn't
multiply LLM cost across the whole pipeline.
"""
import difflib
import json
from typing import Dict, List, Optional, Tuple

from config import MAX_ORIGINALITY_REWRITE_ATTEMPTS
from db import get_connection
from utils.fulltext import get_full_text
from utils.textclean import strip_html
from utils.similarity import similarity_report
from agents.base_agent import Agent
from agents.message_router import register_agent

# Floor below which generated full_content is treated as a failure rather than published.
# Well under the smallest word_range floor (400 words for minor stories) so it never
# rejects a legitimately short article - it only catches degenerate output (an empty/near-
# empty body, or the LLM echoing the one-paragraph editorial brief back as "the article").
MIN_ARTICLE_WORDS = 120

# Above this SequenceMatcher ratio, full_content's plain text is considered a near-duplicate
# of the short summary it was built from rather than a genuine expansion of it - exactly the
# failure mode that caused a real article to render the same paragraph 3 times on the site
# (deck, "Key Takeaways" fallback, and body all falling back to the same short text).
SUMMARY_DUPLICATE_RATIO = 0.75

# Injected into the prompt only for content_type == "tutorial_or_reference" (Reporter
# Agent's classification - see agents/reporter_agent.py). Replaces the default "extract
# every detail" instruction, which is exactly what turned cluster 537 (KDNuggets' "Building
# an End-to-End Data Science Portfolio Project") into a near-copy: for a how-to/listicle,
# the ordered steps/field names/structure ARE the source's protected expression, not just
# facts, so "extract everything" and "reconstruct the tutorial" are the same instruction.
TUTORIAL_MODE_INSTRUCTIONS = """
This source is a TUTORIAL, GUIDE, LISTICLE, OR REFERENCE PIECE, not a news event - treat it \
differently from ordinary reporting:
- Do NOT reconstruct its exact step list, field/variable/parameter names, code, or item-by-item \
structure. Reproducing the specific ordered detail of a how-to guide is real copying no matter how \
you rephrase the sentences around it.
- Describe the APPROACH at a conceptual level instead: what problem it solves, why the idea is useful, \
roughly how it's organized (e.g. "a multi-stage pipeline covering data prep through deployment" rather \
than naming every stage and field). Round off enumerated lists into prose about the shape of the thing.
- Spend real space on independent commentary that isn't in the source at all: how this compares to how \
people usually approach the same problem, who it's actually useful for, a practical caveat, or a \
skeptical angle - your own added value, not a summary of theirs.
- End by sending the reader to the original source for the actual step-by-step walkthrough - you are \
the map, not the terrain.
"""

# Injected only when the cluster has exactly one source (no corroboration to synthesize across).
# A mandatory, source-independent section is the most direct way to make a single-source piece
# genuinely transformative rather than a rewrite of the one article it's based on.
SINGLE_SOURCE_MODE_INSTRUCTIONS = """
This story has exactly ONE source. Because of that, you MUST include a dedicated "Our Take" <h3> \
section (in addition to the other required sections) containing analysis that does NOT appear in the \
source at all - your own read on why this matters, how it compares to alternatives or prior approaches, \
who should actually care, or a practical/skeptical angle. One throwaway sentence is not enough; this \
section is what earns the piece the right to be published as more than a rewrite of its one source.
"""

# Injected only on internal rewrite retries (see write_full_article's loop below), after an
# attempt failed utils.similarity's strict originality gate. Escalates rather than repeating
# the same instructions verbatim, since a plain retry of an unchanged prompt tends to regenerate
# something close to the same text.
ORIGINALITY_ESCALATION = """
REWRITE REQUIRED - READ THIS FIRST: your previous draft was flagged as too textually close to a \
source (a long run of words matched the source nearly verbatim, or the piece leaned too heavily on \
its exact phrasing throughout). Start over with a different structure and your own sentence \
constructions from scratch - do not reuse the source's phrasing, clause order, or sentence rhythm even \
when covering the same fact. Compress or generalize any step-by-step or listed detail instead of \
reproducing it near-verbatim, and lean harder into independent analysis/commentary that isn't in the \
source at all.

Most often this specific flag means ONE sentence or quote in an otherwise original draft was copied \
intact (9+ words in a row matching a source), not that the whole piece read as a rewrite. If you're \
including a direct quote from a source, either keep it under 9 words with quotation marks, or convert \
it to indirect speech in your own words instead of quoting it. Do not reuse a source's headline-style \
phrase or descriptive clause around a product/paper name even if the name itself is fine to repeat.
"""

ARTICLE_PROMPT_TEMPLATE = """{originality_note}You are a senior staff writer at a professional AI industry \
news site (think the editorial quality of TechCrunch or The Information). You've been given an already \
fact-checked story to write up in full for the website. Do not invent facts, quotes, or numbers that \
aren't in the sources below — only elaborate on, contextualize, and explain what's actually there.

LEGAL/DEFAMATION RULE — this overrides "add depth" anywhere below: never state or imply that a specific, \
named person or organization committed a crime, fraud, or other wrongdoing, or is incompetent, dishonest, \
or unethical, unless the sources say so explicitly and unambiguously. If a source reports an accusation, \
lawsuit, investigation, or allegation, present it as exactly that — attributed to who is making the claim \
("X alleges...", "according to the lawsuit...") — never restated as settled fact. If you're not sure a \
negative characterization of a named party is directly supported, cut it rather than include it; a shorter, \
duller sentence is always the safer choice than a punchier one you can't ground in the sources.

ORIGINALITY RULE — this is a hard requirement, not a style preference: never lift a run of the source's \
wording into your draft. Every sentence must be your own construction — reorganize, don't transcribe. \
This site does not republish or lightly paraphrase other outlets' work; it reports independently on what \
they described. When two ways of saying something are equally clear, pick the one that reads least like \
the source's own sentence.

VERBATIM RUN LIMIT — the specific, mechanically-checked version of the rule above: your draft is scanned \
against every source and automatically rejected if ANY stretch of 9 or more consecutive words matches a \
source exactly, even a single such run inside an otherwise fully original piece. This is the failure mode \
that usually slips through: not the whole piece reading copied (that's a separate, coarser check), but one \
untouched sentence, clause, product tagline, or quote hiding inside an otherwise original draft. Concretely:
- Quotes: never carry a source's quoted statement verbatim if it runs 9+ words. Either paraphrase it as \
indirect speech ("X said the update was aimed at...") or, if the exact wording matters enough to quote \
directly, trim it to a short fragment under 9 words inside quotation marks with clear attribution.
- Named things (product names, paper/report titles, feature names) are fine to reuse exactly since they're \
not the source's "expression" - but do NOT chain one straight into the surrounding descriptive clause the \
source used around it; write your own sentence around the name instead.
- Before finalizing, mentally check any sentence that felt easy to write, especially the lede and any line \
built around a striking phrase from a source - those are the ones most likely to have copied a run intact \
without you noticing while focused on getting the facts right.
{mode_instructions}
HEADLINE: {headline}
CATEGORY: {category}
EDITORIAL BRIEF (already-approved short summary): {summary}

SOURCE ARTICLES (marked FULL TEXT where the actual article body was fetched, or TEASER ONLY where \
only a short RSS blurb was available):
{sources_block}

Write a full article, {word_range} words, in clean HTML using only <p>, <h3>, <ul>/<li>, and <strong> tags \
(no <html>/<body>/inline styles/markdown). Structure:
1. A strong lede paragraph (2-3 sentences) that leads with what actually happened — the single most \
important fact first, not a throat-clearing setup.
2. A "Why it matters" <h3> section: the practical or strategic implication for someone who builds with \
or invests in AI. Go beyond the obvious — cover second-order effects (competitors, pricing, ecosystem) \
where the sources support it.
3. A "The details" <h3> section: the concrete specifics — names, numbers, dates, what changed technically \
or commercially. Pull out EVERY name, figure, and fact the sources contain, not just the headline number — \
if a source lists multiple companies, deals, or examples, name them individually instead of summarizing \
them away as "various" or "several." If sources disagree on a fact or framing, say so plainly instead of \
glossing over it.
4. A "Background" <h3> section: the context a reader needs to understand why this story matters now — \
prior related moves, market position, or history, grounded only in what the sources state or clearly imply.
5. A short closing paragraph on what to watch next, grounded only in what the sources imply, not speculation \
you're inventing.

Use the full length to add depth and grounded context, not to pad with repetition or restate the same point \
in different words. If a source is TEASER ONLY and the sources collectively don't support the low end of \
{word_range} words of real substance, write what's actually supported rather than inventing filler — but \
exhaust every concrete detail across ALL sources before concluding that.

Then write KEY TAKEAWAYS: 3-5 short, standalone bullet points (each one sentence, no trailing period-less \
fragments) that a reader could scan without reading the article. Each one must carry a distinct, concrete fact \
or number from the sources — not a restatement of the editorial brief above, and not the same claim reworded \
twice. Do not write a generic "why this matters" bullet; every bullet needs a specific detail (a name, a \
number, a date, a concrete change) in it.

Voice — this is the part most AI-generated news writing gets wrong, so follow it precisely:
- Write with a point of view, like a reporter who has covered this beat for years and knows what's actually \
notable here versus routine. Don't just restate facts in order; tell the reader why this specific development \
stands out (or, if it's minor, say so instead of manufacturing false urgency).
- Never write sentences that just restate importance in the abstract — banned patterns: "this is significant \
because...", "this could indicate...", "this may reflect growing interest in...", "highlights the growing \
trend of...", "underscores the importance of...". Replace every one of those with an actual, specific claim \
about what changes for the reader.
- If the sources don't give you a detail (a dollar figure, a name, a date), do not write a sentence announcing \
that it's missing ("specific details ... are not provided," "it remains unclear whether..."). Just don't \
mention it — write confidently with what you do have instead of narrating the gaps.
- No hedge-closer paragraphs that restate the whole article in vaguer language. Every sentence should add a \
new fact or a new angle, or it shouldn't be there.
- No hype words ("game-changing", "revolutionary", "groundbreaking") and no filler ("in conclusion", "it \
remains to be seen", "only time will tell").

Respond ONLY with valid JSON, no other text: \
{{"full_content": "<p>...</p>...", "key_takeaways": ["...", "...", "..."]}}
"""


class WriterAgent(Agent):
    """Expands approved clusters into full website articles."""

    def __init__(self):
        super().__init__("Writer")

    @staticmethod
    def _gather_sources(articles: List[Dict]) -> Tuple[str, List[str]]:
        """Builds the prompt's sources_block AND collects the raw full texts used, in one
        pass - the latter is what agents/utils/similarity.py's originality gate below
        compares the generated article back against, so it must be the SAME material the
        Writer actually saw (not a re-fetch, and not summary_raw when full text was used)."""
        lines = []
        full_texts = []
        for a in articles:
            full_text = get_full_text(a["id"], a.get("url"), a.get("source")) if a.get("id") else ""
            if full_text:
                lines.append(f"- [{a['source']}] {a['title']} (FULL TEXT)\n  {full_text[:3000]}")
                full_texts.append(full_text)
            else:
                snippet = (a.get("summary_raw") or "")[:1200]
                lines.append(f"- [{a['source']}] {a['title']} (TEASER ONLY)\n  {snippet}")
        return "\n".join(lines), full_texts

    @staticmethod
    def _target_word_range(importance_score: Optional[int], content_type: Optional[str], is_single_source: bool) -> str:
        """Scale target article length to how big the story actually is, instead of forcing
        every cluster (a minor tools release and a major funding round alike) into the same
        800-1000 word band.

        Single-source tutorial/reference content is capped low regardless of importance:
        forcing 700-1200 words out of one thin how-to source is exactly the length pressure
        that drove the Writer to over-extract the source's own step-by-step detail (see
        config.py's SIMILARITY_* comment) - there usually isn't that much genuinely original
        material to say about someone else's single guide."""
        if content_type == "tutorial_or_reference" and is_single_source:
            return "350-500"
        try:
            score = int(importance_score)
        except (TypeError, ValueError):
            return "800-1000"
        if score >= 8:
            return "1000-1200"
        if score >= 5:
            return "700-900"
        return "400-600"

    @staticmethod
    def _quality_reason(parsed: Optional[Dict], summary: str) -> Optional[str]:
        """
        Returns None if the parsed Writer output is a genuine full article, or a short
        reason string if it's degenerate and should be treated as a failure rather than
        published. Layered on top of the existing "did the LLM return JSON at all" check,
        since a technically-successful call can still return output that's too thin, missing
        the mandated section structure, or just the short summary echoed back - none of which
        parse_json() alone can catch, and all of which produce the same broken page (the
        short summary rendered 3 times: deck, "Key Takeaways" fallback, and body).
        """
        if not parsed or not parsed.get("full_content"):
            return "no full_content in response"

        body_text = strip_html(parsed["full_content"]).split()
        if len(body_text) < MIN_ARTICLE_WORDS:
            return f"full_content too short ({len(body_text)} words < {MIN_ARTICLE_WORDS})"

        if "<h3" not in parsed["full_content"]:
            return "full_content missing the mandated <h3> section structure"

        if len(parsed.get("key_takeaways") or []) < 3:
            return "fewer than 3 key_takeaways"

        if summary:
            body_plain = strip_html(parsed["full_content"]).strip().lower()
            ratio = difflib.SequenceMatcher(None, body_plain, summary.strip().lower()).ratio()
            if ratio >= SUMMARY_DUPLICATE_RATIO:
                return f"full_content is a near-duplicate of the summary (similarity {ratio:.2f})"

        return None

    @staticmethod
    def _similarity_reason(full_content_html: str, source_full_texts: List[str]) -> Tuple[Optional[str], float, str]:
        """The check article 537 shipped without: compares the generated body against the
        ACTUAL source text (not the internal summary - see SUMMARY_DUPLICATE_RATIO above,
        which is a different check for a different bug). Returns (reason_or_None, score,
        copied_phrase) - score is stored on the cluster regardless of outcome, for the admin
        UI; copied_phrase is the actual matched text behind the longest verbatim run (empty
        unless that's what tripped the flag), fed back into the next attempt's prompt by
        write_full_article() below so the retry targets the specific phrase instead of
        guessing at what to avoid."""
        if not source_full_texts:
            return None, 0.0, ""  # nothing to compare against (all sources were TEASER ONLY)
        report = similarity_report(strip_html(full_content_html), source_full_texts)
        if report["flagged"]:
            reason = (
                f"too similar to a source (jaccard={report['max_jaccard']:.3f}, "
                f"verbatim_run={report['max_verbatim_run_words']} words)"
            )
            return reason, report["score"], report.get("max_verbatim_run_text", "")
        return None, report["score"], ""

    @staticmethod
    def _build_originality_note(attempt: int, copied_phrase: str) -> str:
        """Prompt prefix for a given retry attempt. Attempt 1 gets nothing (the base prompt's
        ORIGINALITY RULE / VERBATIM RUN LIMIT sections are enough for a first try). Attempt 2+
        gets ORIGINALITY_ESCALATION, and - this is the part that actually breaks repeat
        failures - if the previous attempt's flag was specifically a verbatim run, the literal
        copied phrase is quoted back so the model has something concrete to avoid instead of a
        generic "don't copy" reminder it's already seen once and failed to act on."""
        if attempt <= 1:
            return ""
        note = ORIGINALITY_ESCALATION
        if copied_phrase:
            note += (
                f'\nThe exact phrase your last draft copied from a source was: "{copied_phrase}". This precise '
                "wording (or anything close to it word-for-word) must not appear anywhere in the new draft - "
                "express that idea with completely different words and sentence structure.\n"
            )
        return note

    def write_full_article(
        self, headline: str, category: str, summary: str, articles: List[Dict],
        importance_score: Optional[int] = None, content_type: Optional[str] = None,
    ) -> Optional[Dict]:
        """Returns {"full_content": "<html>", "key_takeaways": [...], "similarity_score": float,
        "originality_attempts": int}, or None on failure.

        Runs up to MAX_ORIGINALITY_REWRITE_ATTEMPTS internal generations, escalating the
        anti-copying instruction each time a draft fails the originality gate (utils.similarity),
        before giving up. This is deliberately a hard, unattended gate with no "publish anyway,
        flag for review" fallback - per product decision (2026-08-15), the site would rather not
        publish a single-source/tutorial story than risk it reading as copied, and a human
        reviewer was never actually catching this class of problem in practice (see
        agents/fact_checker_agent.py's single-source handling, which caps at "review" for
        corroboration reasons, not originality ones)."""
        if not articles:
            return None

        is_single_source = len({a.get("source") for a in articles}) <= 1
        mode_instructions = ""
        if content_type == "tutorial_or_reference":
            mode_instructions += TUTORIAL_MODE_INSTRUCTIONS
        if is_single_source:
            mode_instructions += SINGLE_SOURCE_MODE_INSTRUCTIONS

        sources_block, source_full_texts = self._gather_sources(articles)
        word_range = self._target_word_range(importance_score, content_type, is_single_source)

        best_score = None
        copied_phrase = ""  # set after a flagged attempt; fed into the NEXT attempt's prompt
        for attempt in range(1, MAX_ORIGINALITY_REWRITE_ATTEMPTS + 1):
            prompt = ARTICLE_PROMPT_TEMPLATE.format(
                originality_note=self._build_originality_note(attempt, copied_phrase),
                mode_instructions=mode_instructions,
                headline=headline,
                category=category or "General",
                summary=summary,
                sources_block=sources_block,
                word_range=word_range,
            )
            response = self.call_llm(prompt, max_tokens=2200, json_mode=True)
            parsed = self.parse_json(response)
            fail_reason = self._quality_reason(parsed, summary)

            similarity_score = None
            copied_phrase = ""
            if fail_reason is None:
                fail_reason, similarity_score, copied_phrase = self._similarity_reason(parsed["full_content"], source_full_texts)
                if similarity_score is not None:
                    best_score = similarity_score if best_score is None else min(best_score, similarity_score)

            success = fail_reason is None
            self.logger.log_action(
                "write_full_article", input_data={"headline": headline, "attempt": attempt, "content_type": content_type},
                output_data={
                    "chars": len(parsed["full_content"]),
                    "takeaways": len(parsed.get("key_takeaways") or []),
                    "similarity_score": similarity_score,
                } if success else {"similarity_score": similarity_score},
                success=success,
                error_message=fail_reason,
            )
            if success:
                return {
                    "full_content": parsed["full_content"],
                    "key_takeaways": parsed.get("key_takeaways") or [],
                    "similarity_score": similarity_score,
                    "originality_attempts": attempt,
                }
            # Only worth retrying if the failure was specifically an originality flag - a
            # thin/malformed draft (_quality_reason failing) won't be fixed by the escalation
            # text, so don't burn the retry budget on it; let the normal publish.py retry-next-
            # cycle path handle that instead.
            if "too similar to a source" not in (fail_reason or ""):
                break

        return None

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        if message["type"] == "write_full_article":
            result = self.write_full_article(
                payload.get("headline"), payload.get("category"),
                payload.get("summary"), payload.get("articles", []),
                payload.get("importance_score"),
            )
            return {"result": result}
        return {"error": f"unknown message type {message['type']}"}


writer_agent = WriterAgent()
register_agent("writer", writer_agent.handle_message)


def _pick_cluster_image(cluster_id: int) -> Optional[Dict]:
    """
    The lead image for a cluster's card/hero: the first available image among its
    source articles (populated by ingest.py from the RSS entry, or by
    utils/fulltext.py's og:image scrape - normally already run as a side effect of the
    get_full_text() calls in _gather_sources, by the time this is called from
    ensure_full_article() below). image_credit/image_credit_url identify the original
    publisher, since we hotlink rather than re-host the image.

    If no source article has a cached image yet, makes one on-demand scrape attempt
    per article before giving up, instead of assuming get_full_text() must already have
    run. That assumption doesn't always hold - backfill_missing_images() below calls
    this for already-published clusters independently of full_content status, precisely
    to cover the case where get_full_text() never ran for them (e.g. the Writer call
    failed before ever reaching that step, back when the cluster was first published).
    """
    conn = get_connection()
    row = conn.execute(
        """SELECT source, url, image_url FROM articles
           WHERE cluster_id = ? AND image_url IS NOT NULL AND image_url != ''
           LIMIT 1""",
        (cluster_id,),
    ).fetchone()
    if row:
        conn.close()
        return {"image_url": row["image_url"], "image_credit": row["source"], "image_credit_url": row["url"]}

    articles = conn.execute(
        "SELECT id, source, url FROM articles WHERE cluster_id = ?", (cluster_id,)
    ).fetchall()
    conn.close()
    for a in articles:
        if a["url"]:
            get_full_text(a["id"], a["url"], a["source"])  # side effect: caches image_url too

    conn = get_connection()
    row = conn.execute(
        """SELECT source, url, image_url FROM articles
           WHERE cluster_id = ? AND image_url IS NOT NULL AND image_url != ''
           LIMIT 1""",
        (cluster_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"image_url": row["image_url"], "image_credit": row["source"], "image_credit_url": row["url"]}


def backfill_missing_images(limit: int = 15) -> int:
    """
    Already-published clusters with no lead image, independent of full_content status.
    Fetching/attaching an image is cheap (an HTTP fetch + meta-tag parse, no LLM call)
    and shouldn't be gated behind full_content ever being (re)generated - but
    ensure_full_article() below only ever calls _pick_cluster_image() once, at the
    moment full_content is first written, and its early-return means a cluster that
    already has full_content never gets revisited even if none of its articles had a
    cached image back then. Run alongside retry_missing_full_content() (publish.py)
    so a story doesn't show the gradient placeholder forever just because its one
    shot at an image happened before any of its sources had one cached.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT id FROM clusters
        WHERE published_at IS NOT NULL AND (image_url IS NULL OR image_url = '')
        ORDER BY published_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    filled = 0
    for row in rows:
        image = _pick_cluster_image(row["id"])
        if not image:
            continue
        conn = get_connection()
        conn.execute(
            "UPDATE clusters SET image_url = ?, image_credit = ?, image_credit_url = ? WHERE id = ?",
            (image["image_url"], image["image_credit"], image["image_credit_url"], row["id"]),
        )
        conn.commit()
        conn.close()
        filled += 1
    return filled


def ensure_full_article(cluster: Dict) -> bool:
    """
    Generate + cache a full website article (body + key takeaways) for a cluster, if it
    doesn't have both yet. Shared by digest.py (email pipeline) and publish.py (site
    pipeline) so both write through the same cache instead of duplicating this logic.

    Requiring *both* columns (not just full_content) makes this self-backfilling: articles
    published before key_takeaways existed get picked back up here (and by publish.py's
    retry_missing_full_content) and re-run through the Writer Agent, which regenerates the
    whole article in one LLM call - a one-time cost per pre-existing article.

    Returns True if the cluster has (or now has) both columns populated, False if generation
    failed - callers that gate publishing on this (publish.py) must not go live on False, or
    the site renders the raw summary three times over instead of a real article (deck, "Key
    Takeaways" fallback, and body all fall back to the same short summary independently).
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT full_content, key_takeaways FROM clusters WHERE id = ?", (cluster["id"],)
    ).fetchone()
    if row and row["full_content"] and row["key_takeaways"]:
        conn.close()
        return True

    source_articles = conn.execute(
        "SELECT id, source, title, url, summary_raw FROM articles WHERE cluster_id = ?",
        (cluster["id"],),
    ).fetchall()
    conn.close()

    if not source_articles:
        return False

    try:
        result = writer_agent.write_full_article(
            cluster.get("headline"), cluster.get("category"), cluster.get("summary"),
            [dict(a) for a in source_articles], cluster.get("importance_score"),
            cluster.get("content_type"),
        )
    except Exception as e:
        print(f"  [error] Writer Agent failed for cluster {cluster['id']}: {str(e)[:100]}")
        result = None

    if not result:
        # Even a failed attempt (originality gate exhausted, or a thin/malformed draft)
        # is worth recording - the admin UI can otherwise never distinguish "never tried"
        # from "tried and couldn't clear the originality bar."
        conn = get_connection()
        conn.execute(
            "UPDATE clusters SET originality_attempts = COALESCE(originality_attempts, 0) + 1 WHERE id = ?",
            (cluster["id"],),
        )
        conn.commit()
        conn.close()
        return False

    image = _pick_cluster_image(cluster["id"])
    conn = get_connection()
    if image:
        conn.execute(
            """UPDATE clusters SET full_content = ?, key_takeaways = ?, similarity_score = ?,
               originality_attempts = ?, image_url = ?, image_credit = ?, image_credit_url = ? WHERE id = ?""",
            (
                result["full_content"], json.dumps(result["key_takeaways"]),
                result.get("similarity_score"), result.get("originality_attempts"),
                image["image_url"], image["image_credit"], image["image_credit_url"],
                cluster["id"],
            ),
        )
    else:
        conn.execute(
            """UPDATE clusters SET full_content = ?, key_takeaways = ?, similarity_score = ?,
               originality_attempts = ? WHERE id = ?""",
            (result["full_content"], json.dumps(result["key_takeaways"]),
             result.get("similarity_score"), result.get("originality_attempts"), cluster["id"]),
        )
    conn.commit()
    conn.close()
    return True
