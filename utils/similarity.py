"""
Source-similarity / textual-reuse detector - the guardrail article 537 (KDNuggets'
"Building an End-to-End Data Science Portfolio Project") shipped without. Deliberately
NOT an LLM call: it runs on every Writer/Insight attempt (including internal rewrite
retries), so it needs to be free and instant, and it needs to catch near-verbatim reuse
even when an LLM grader would call the text "well grounded" - grounding and originality
are different axes (see agents/fact_checker_agent.py's check_content_grounding, which
only checks fabrication/defamation against the source, never textual overlap).

Two independent signals, either one enough to flag:
  1. Shingle (n-gram) Jaccard overlap - catches a piece that leans on the source's
     phrasing throughout, even if no single run is very long.
  2. Longest verbatim run - catches a long copied phrase even inside an otherwise
     original piece (a high overlap score can hide in a low Jaccard average).

Compares against each source's ACTUAL fetched text independently (never a concatenated
blob), so a multi-source cluster that leans too hard on just one of its sources still
gets caught - the per-source max is what's reported, not an average that dilutes it.
"""
import re
from difflib import SequenceMatcher
from typing import Dict, List

from config import SIMILARITY_JACCARD_THRESHOLD, SIMILARITY_SHINGLE_SIZE, SIMILARITY_VERBATIM_RUN_WORDS

_WORD_RE = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def _shingles(words: List[str], n: int) -> set:
    if len(words) < n:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _longest_common_run(a_words: List[str], b_words: List[str]) -> tuple:
    """Longest contiguous run of words that appears, in the same order, in both texts.
    Returns (run_length, matched_words) - the actual matched text is what lets a caller
    (writer_agent's retry loop) tell the LLM exactly what it copied instead of just a
    count, which is far more actionable feedback than a generic "don't copy" reminder."""
    if not a_words or not b_words:
        return 0, []
    matcher = SequenceMatcher(None, a_words, b_words, autojunk=False)
    match = matcher.find_longest_match(0, len(a_words), 0, len(b_words))
    return match.size, a_words[match.a:match.a + match.size]


def compare_to_source(generated_text: str, source_text: str) -> Dict:
    """One generated-vs-one-source comparison. Returns raw signals, not a verdict -
    similarity_report() below aggregates across all of a cluster's sources and applies
    the threshold."""
    gen_words = _tokenize(generated_text)
    src_words = _tokenize(source_text)
    gen_shingles = _shingles(gen_words, SIMILARITY_SHINGLE_SIZE)
    src_shingles = _shingles(src_words, SIMILARITY_SHINGLE_SIZE)
    jaccard = _jaccard(gen_shingles, src_shingles)
    run, run_words = _longest_common_run(gen_words, src_words)
    return {"jaccard": round(jaccard, 4), "verbatim_run_words": run, "verbatim_run_text": " ".join(run_words)}


def similarity_report(generated_text: str, source_texts: List[str]) -> Dict:
    """Compares generated_text against each of source_texts independently and reports
    the worst case (max overlap with any single source) plus a flat 0-1 `score` for
    storage/display (clusters.similarity_score). `flagged` is True if EITHER signal
    crosses its strict threshold against ANY source - this is a hard gate, not a
    soft/averaged score, by design (see config.py's SIMILARITY_* constants)."""
    if not generated_text or not source_texts:
        return {
            "score": 0.0, "flagged": False, "max_jaccard": 0.0,
            "max_verbatim_run_words": 0, "max_verbatim_run_text": "", "per_source": [],
        }

    per_source = []
    max_jaccard = 0.0
    max_run = 0
    max_run_text = ""
    for src in source_texts:
        if not src:
            continue
        result = compare_to_source(generated_text, src)
        per_source.append(result)
        max_jaccard = max(max_jaccard, result["jaccard"])
        if result["verbatim_run_words"] > max_run:
            max_run = result["verbatim_run_words"]
            max_run_text = result["verbatim_run_text"]

    flagged = max_jaccard >= SIMILARITY_JACCARD_THRESHOLD or max_run >= SIMILARITY_VERBATIM_RUN_WORDS
    # Flat score for storage: normalize each signal against its own threshold so 1.0
    # roughly means "right at the strict cutoff," not an arbitrary scale.
    score = max(
        max_jaccard / SIMILARITY_JACCARD_THRESHOLD if SIMILARITY_JACCARD_THRESHOLD else 0.0,
        max_run / SIMILARITY_VERBATIM_RUN_WORDS if SIMILARITY_VERBATIM_RUN_WORDS else 0.0,
    )
    return {
        "score": round(min(score, 3.0), 3),  # capped so one wildly-copied source doesn't blow out the scale
        "flagged": flagged,
        "max_jaccard": round(max_jaccard, 4),
        "max_verbatim_run_words": max_run,
        "max_verbatim_run_text": max_run_text,
        "per_source": per_source,
    }
