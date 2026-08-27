"""
Similar Bug Detection — backend/ai/similarity_search.py

Given a new bug's raw text, searches the historical bug database
(data/bugs.csv) for the most textually similar previously reported
bugs, comparing against each historical bug's Title + Description +
Stack Trace combined.

Current implementation: TF-IDF vectorization + cosine similarity
(scikit-learn), with several adjustments so that differently-worded
reports of the same underlying problem are still recognized as related,
while genuinely unrelated bugs aren't falsely matched:

  - Concept clustering (see CONCEPT_CLUSTERS): before vectorizing, both
    the new bug's text and each historical bug's text are expanded with
    canonical "concept tags" (e.g. concept_nullref, concept_auth,
    concept_database) whenever recognized technical vocabulary for that
    concept appears. This is what lets "Login fails with
    NullPointerException" and "User login crashes because the
    authentication object is null" be recognized as related even though
    they share few exact words — both trigger concept_auth AND
    concept_nullref. It's still plain keyword/pattern matching (no
    ML/embeddings), just generalized from "same word" to "same
    recognized concept". CamelCase identifiers (e.g.
    "NullPointerException") are also split into their component words
    so they can match plain-English mentions like "null".

  - Explicit stop words for a few generic bug-report terms ("error",
    "login", "application", "failed" and close variants) that are
    common enough across unrelated bugs to be poor evidence of
    similarity on their own. They're excluded from the raw TF-IDF
    vocabulary entirely; any real signal about e.g. a login-related
    problem instead comes through the concept_auth tag above, which
    only fires alongside genuine authentication vocabulary — so two
    bugs that merely both mention "login" in unrelated ways don't
    falsely match, but genuinely related login/auth bugs still do.

  - Category alignment: if the new bug's rule-derived category (see
    ai.rule_analyzer) matches a historical bug's stored, ground-truth
    Category, its text similarity is amplified (see
    CATEGORY_MATCH_BOOST). Because this is a *multiplier* on the
    existing text similarity rather than a flat bonus, it can never by
    itself turn two bugs with zero real text overlap into a match —
    sharing a category alone is not treated as evidence of duplication.

  - A small ranking boost for bugs marked "Resolved" (see
    RESOLVED_BOOST) since they carry proven fix information.

The whole computation is wrapped defensively: malformed or missing
historical records are skipped rather than raising, and any unexpected
error falls back to returning no matches rather than crashing the
Analyze Bug page.

This module exposes a single stable entry point, `find_similar_bugs()`,
so it can later be replaced with an embeddings + vector database
approach (e.g. Sentence Transformers + FAISS) without changing any
caller.
"""

import re
from typing import Optional, TypedDict

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from utils.bug_storage import STATUS_RESOLVED, read_all_bugs

DEFAULT_TOP_N = 3
MIN_SIMILARITY = 0.20  # 20% — below this, a match isn't considered meaningful

# Bugs marked "Resolved" carry proven, developer-confirmed fix information
# (see ai.fix_recommender), which is more useful to surface than an
# unverified Open/In Progress match at a similar similarity level. This
# small additive boost lets Resolved bugs win close ties in ranking
# without letting a barely-related Resolved bug outrank a strong match.
RESOLVED_BOOST = 0.05

# Multiplier applied to a historical bug's text similarity when its
# stored Category matches the new bug's rule-derived category. This is
# what lets two differently-worded reports of the same underlying
# problem be recognized as related (see module docstring). Tuned so a
# moderate lexical overlap (a shared concept, not just a shared common
# word) clears MIN_SIMILARITY once boosted, while two same-category
# bugs with no real text overlap stay at 0 (0 * multiplier is still 0).
CATEGORY_MATCH_BOOST = 1.6
UNKNOWN_CATEGORY = "Unknown"

# A handful of generic bug-report words that appear across many unrelated
# bugs and are poor evidence of similarity on their own (see module
# docstring). Excluded from the TF-IDF vocabulary entirely — genuine
# relatedness for e.g. login-adjacent bugs instead has to come through a
# concept tag (CONCEPT_CLUSTERS below), which only fires alongside real
# supporting vocabulary.
_GENERIC_TERM_STOP_WORDS = {
    "error", "errors", "login", "logins", "application", "applications",
    "app", "apps", "failed", "fail", "fails", "failure", "failures", "bug",
}
_STOP_WORDS = list(ENGLISH_STOP_WORDS | _GENERIC_TERM_STOP_WORDS)

# Recognized technical concepts, each with a set of trigger patterns
# (checked case-insensitively). If any pattern for a concept matches the
# text, that concept's canonical tag is appended to the text before
# vectorizing. This lets two differently-worded reports of the same
# underlying concept (e.g. a null-reference / authentication problem)
# share a strong, distinctive token even when their exact wording and
# surrounding stack-trace noise differ. It's still keyword/pattern
# matching — just generalized from exact words to recognized concepts.
CONCEPT_CLUSTERS: dict[str, list[str]] = {
    "concept_nullref": [
        r"null\s*pointer", r"\bnullpointerexception\b", r"\bnpe\b",
        r"\bnull\b", r"\bundefined\b", r"\bnone\s*type\b", r"\bnull\s*reference\b",
    ],
    "concept_auth": [
        r"\blogin\b", r"\bsign\s*in\b", r"\bsignin\b", r"\blogon\b",
        r"\bauthentication\b", r"\bauth\b", r"\bcredential", r"\bpassword\b",
        r"\bsession\b", r"\btoken\b", r"\bunauthorized\b",
    ],
    "concept_database": [
        r"\bdatabase\b", r"\bsql\b", r"\bmysql\b", r"\bpostgres", r"\bmongodb\b",
        r"\bquery\b", r"\btransaction\b", r"\bdeadlock\b",
    ],
    "concept_network": [
        r"\btimeout\b", r"\btimed\s*out\b", r"\bconnection\s*refused\b",
        r"\bconnection\s*reset\b", r"\bunreachable\b", r"\bnetwork\b",
        r"\bdns\b", r"\bsocket\b",
    ],
    "concept_ui": [
        r"\bcss\b", r"\bdom\b", r"\bbutton\b", r"\brender", r"\blayout\b",
        r"\bbrowser\b", r"\bflexbox\b", r"\bmodal\b", r"\bresponsive\b",
    ],
    "concept_performance": [
        r"\bslow\b", r"\bmemory\s*leak\b", r"\bhigh\s*cpu\b", r"\blatency\b",
        r"\bout\s*of\s*memory\b", r"\bbottleneck\b", r"\bdegraded\b",
    ],
    "concept_filesystem": [
        r"\bfile\s*not\s*found\b", r"\bno\s*such\s*file\b", r"\bdisk\s*full\b",
        r"\bpermission\s*denied\b", r"\benoent\b", r"\beacces\b",
    ],
}

_CAMEL_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# How many times a matched concept tag is repeated when injected. A
# single occurrence can get lost in the noise of longer/redundant bug
# text (e.g. a title duplicated into the description, or a verbose
# stack trace); repeating it gives the concept match enough TF-IDF
# weight to reliably surface real relatedness without being so extreme
# that it overwhelms genuine distinguishing content.
_CONCEPT_TAG_REPEAT = 4


def _expand_camel_case(text: str) -> str:
    """
    Split CamelCase/PascalCase identifiers so e.g. "NullPointerException"
    also contributes "Null", "Pointer", "Exception" as separate tokens —
    lets it match plain-English mentions like "null" elsewhere.
    """
    return _CAMEL_CASE_BOUNDARY.sub(" ", text)


def _inject_concept_tags(text: str) -> str:
    """
    Preprocess a document for comparison: append a CamelCase-split
    version of the text, then scan for recognized technical concepts
    (see CONCEPT_CLUSTERS) and append a canonical tag (repeated
    _CONCEPT_TAG_REPEAT times) for each one that matches. Applied
    identically to the new bug's text and every historical bug's text
    so they're compared on equal footing.
    """
    expanded = f"{text} {_expand_camel_case(text)}"
    text_lower = expanded.lower()

    matched_tags = _detect_concept_tags(text_lower)

    if matched_tags:
        tag_tokens = " ".join(sorted(matched_tags) * _CONCEPT_TAG_REPEAT)
        expanded = f"{expanded} {tag_tokens}"

    return expanded


def _detect_concept_tags(text_lower: str) -> set[str]:
    """Return the set of concept tags (see CONCEPT_CLUSTERS) present in already-lowercased text."""
    return {
        tag for tag, patterns in CONCEPT_CLUSTERS.items()
        if any(re.search(pattern, text_lower) for pattern in patterns)
    }


_CONCEPT_LABELS = {
    "concept_nullref": "null reference",
    "concept_auth": "authentication",
    "concept_database": "database",
    "concept_network": "network",
    "concept_ui": "UI",
    "concept_performance": "performance",
    "concept_filesystem": "filesystem",
}


class SimilarBug(TypedDict):
    bug_id: str
    title: str
    similarity_percentage: float
    severity: str
    category: str
    reporter: str
    submission_date: str
    status: str
    matched_concepts: list[str]
    previous_root_cause: str
    previous_fix: str


def _deduplicate_by_bug_id(bugs: list[dict]) -> list[dict]:
    """Keep only the first occurrence of each Bug ID (data-integrity safeguard)."""
    seen = set()
    unique = []
    for bug in bugs:
        bug_id = bug.get("Bug ID")
        if bug_id and bug_id not in seen:
            seen.add(bug_id)
            unique.append(bug)
    return unique


def _build_comparison_text(bug: dict) -> str:
    """
    Combine Title + Description + Stack Trace into one comparison
    document, then apply the same concept-tag preprocessing used for the
    new bug's text (see _inject_concept_tags) so both sides of the
    comparison are on equal footing.

    Defensive: a malformed record (missing/non-string fields) yields an
    empty string rather than raising, so one bad row can't crash
    duplicate detection for everything else (requirement: must not crash
    if a bug is unavailable/malformed).
    """
    try:
        title = (bug.get("Bug Title") or "").strip()
        description = (bug.get("Bug Description") or "").strip()
        stack_trace = (bug.get("Stack Trace") or "").strip()
    except AttributeError:
        return ""

    combined = " ".join(part for part in (title, description, stack_trace) if part)
    if not combined:
        return ""

    return _inject_concept_tags(combined)


def get_knowledge_base_size() -> int:
    """Return the number of unique historical bugs currently in storage."""
    return len(_deduplicate_by_bug_id(read_all_bugs()))


def find_similar_bugs(
    new_bug_text: str,
    new_bug_category: Optional[str] = None,
    exclude_bug_id: Optional[str] = None,
    top_n: int = DEFAULT_TOP_N,
    min_similarity: float = MIN_SIMILARITY,
) -> list[SimilarBug]:
    """
    Find the most similar historical bugs to a new bug report using
    TF-IDF + cosine similarity, amplified by category alignment.

    Args:
        new_bug_text: the new bug's raw text (title/description/stack
            trace, in any combination — e.g. the raw pasted log).
        new_bug_category: the new bug's category as classified by
            ai.rule_analyzer.analyze_bug_text(), if available. Used to
            amplify similarity for historical bugs in the same category
            (see CATEGORY_MATCH_BOOST). Pass None to skip this signal
            (pure text similarity, the original behavior).
        exclude_bug_id: optional Bug ID to exclude from comparison, so a
            stored bug never matches itself if re-analyzed later.
        top_n: maximum number of results to return.
        min_similarity: minimum similarity (0-1), after boosting,
            required for a historical bug to be considered a meaningful
            match.

    Returns:
        Up to `top_n` SimilarBug dicts, ordered by descending
        similarity. Empty list if nothing meets `min_similarity`.
    """
    if not new_bug_text or not new_bug_text.strip():
        return []

    try:
        historical_bugs = _deduplicate_by_bug_id(read_all_bugs())

        if exclude_bug_id:
            historical_bugs = [b for b in historical_bugs if b.get("Bug ID") != exclude_bug_id]

        corpus = [_build_comparison_text(bug) for bug in historical_bugs]
        valid_pairs = [(bug, text) for bug, text in zip(historical_bugs, corpus) if text]
        if not valid_pairs:
            return []

        historical_bugs = [pair[0] for pair in valid_pairs]
        corpus = [pair[1] for pair in valid_pairs]

        query_text = _inject_concept_tags(new_bug_text.strip())
        documents = corpus + [query_text]

        try:
            vectorizer = TfidfVectorizer(stop_words=_STOP_WORDS)
            tfidf_matrix = vectorizer.fit_transform(documents)
        except ValueError:
            # Corpus produced an empty vocabulary (e.g. only stop words/numbers).
            return []

        new_bug_vector = tfidf_matrix[-1]
        historical_vectors = tfidf_matrix[:-1]
        similarities = cosine_similarity(new_bug_vector, historical_vectors)[0]

        category_signal_active = bool(new_bug_category) and new_bug_category != UNKNOWN_CATEGORY
        query_concept_tags = _detect_concept_tags(query_text.lower())

        scored_bugs = []
        for raw_similarity, bug in zip(similarities, historical_bugs):
            similarity = float(raw_similarity)

            # Category alignment amplifies existing text similarity — it can
            # never create a match out of zero real overlap (0 * boost = 0),
            # so sharing a category alone is never sufficient evidence.
            if category_signal_active and bug.get("Category") == new_bug_category:
                similarity = min(similarity * CATEGORY_MATCH_BOOST, 1.0)

            if bug.get("Status") == STATUS_RESOLVED:
                similarity = min(similarity + RESOLVED_BOOST, 1.0)

            if similarity >= min_similarity:
                scored_bugs.append((similarity, bug))

        scored_bugs.sort(key=lambda pair: pair[0], reverse=True)

        results: list[SimilarBug] = []
        for similarity, bug in scored_bugs[:top_n]:
            # "Why similar": concept tags this specific historical bug's
            # text shares with the query (see CONCEPT_CLUSTERS) — a
            # deterministic, inspectable explanation rather than a black box.
            bug_concept_tags = _detect_concept_tags(_build_comparison_text(bug).lower())
            shared_tags = sorted(query_concept_tags & bug_concept_tags)
            matched_concepts = [_CONCEPT_LABELS.get(tag, tag) for tag in shared_tags]

            is_resolved = bug.get("Status") == STATUS_RESOLVED
            results.append({
                "bug_id": bug.get("Bug ID", ""),
                "title": bug.get("Bug Title", ""),
                "similarity_percentage": round(similarity * 100, 1),
                "severity": bug.get("Severity", ""),
                "category": bug.get("Category", ""),
                "reporter": bug.get("Reporter Name", ""),
                "submission_date": bug.get("Submission Date", ""),
                "status": bug.get("Status", ""),
                "matched_concepts": matched_concepts,
                "previous_root_cause": bug.get("Actual Root Cause", "") if is_resolved else "",
                "previous_fix": bug.get("Actual Fix", "") if is_resolved else "",
            })

        return results
    except Exception:
        # Duplicate detection is a supporting feature, not the core
        # workflow — if something unexpected goes wrong (malformed CSV
        # row, missing file, etc.), fail safe with no matches rather
        # than crashing the Analyze Bug page.
        return []
