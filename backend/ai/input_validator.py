"""
Input Validator — backend/ai/input_validator.py

Decides whether raw text submitted on the Analyze Bug page contains
enough meaningful information to run the AI Analysis Pipeline on, or
whether it's empty/gibberish/too short to analyze.

This is deliberately NOT a fixed list of exact strings to reject or
accept. It combines three general, rule-based signals:

    Tier A - Structural patterns: does the text look like a stack
             trace, traceback, or exception class name (e.g.
             "NullPointerException", "File "x.py", line 12", a Java/JS
             stack frame)? A single match is strong enough evidence on
             its own.

    Tier B - Strong technical keywords: does the text contain at least
             one term that's highly specific to bug/error reports
             (e.g. "timeout", "database", "unauthorized", "connection
             refused")? A single match is sufficient.

    Tier C - Plain-English bug description: if neither of the above
             fire, does the text contain at least a couple of
             recognizable, real English content words (as opposed to
             random keyboard mashing)? This catches legitimate prose
             descriptions ("the app crashes when I click submit") that
             don't happen to contain a specific technical term.

If none of these tiers find evidence, the input is treated as
insufficient. This module exposes one stable entry point,
`validate_bug_report_text()`, so the same check can be reused by future
agents or endpoints.
"""

import re
from typing import Optional, TypedDict

MIN_LENGTH = 4  # sanity floor only — real detection happens via the tiers below
MIN_GENERIC_WORD_MATCHES = 2

DEFAULT_INVALID_MESSAGE = (
    "Please provide a meaningful bug report, error message, or stack trace "
    "so the system can perform an analysis."
)


class ValidationResult(TypedDict):
    is_valid: bool
    reason: str


# ---------------------------------------------------------------------
# Tier A — structural / log patterns
# ---------------------------------------------------------------------

_STRUCTURAL_PATTERNS = [
    re.compile(r"\b\w+(?:Exception|Error)\b"),                       # NullPointerException, ValueError
    re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r'File\s+"[^"]+",\s+line\s+\d+'),                      # Python frame
    re.compile(r"at\s+[\w.$]+\([\w.\-]+:\d+\)"),                      # Java/JS stack frame
    re.compile(r"\bCaused by\s*:", re.IGNORECASE),
    re.compile(r"\b(?:ERROR|WARN|FATAL|CRITICAL)\s*:", re.IGNORECASE),  # log level markers
    re.compile(r"\bsegmentation fault\b", re.IGNORECASE),
    re.compile(r"\bnull\s*pointer\b", re.IGNORECASE),
    re.compile(r"\bstack\s*trace\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------
# Tier B — strong technical keywords (a single match is sufficient)
# ---------------------------------------------------------------------

STRONG_TECHNICAL_KEYWORDS = [
    "error", "exception", "traceback", "stacktrace", "undefined",
    "undefined reference", "segfault", "crash", "crashed", "crashes",
    "bug", "failure", "failed", "fails", "timeout", "timed out",
    "connection refused", "connection reset", "refused", "unreachable",
    "database", "sql", "mysql", "postgres", "postgresql", "mongodb",
    "deadlock", "constraint violation", "foreign key", "unauthorized",
    "permission denied", "access denied", "invalid credentials",
    "token expired", "session expired", "memory leak", "out of memory",
    "high cpu", "disk full", "no such file", "file not found",
    "cannot connect", "cannot read", "cannot find", "not defined",
    "is not a function", "null reference", "access violation",
    "stack overflow", "race condition", "npe", "404", "500", "502", "503",
]

# ---------------------------------------------------------------------
# Tier C — recognizable plain-English content words used in bug reports
# ---------------------------------------------------------------------

GENERIC_ENGLISH_WORDS = {
    "the", "application", "app", "system", "user", "users", "click",
    "clicking", "clicked", "button", "page", "screen", "load", "loading",
    "loads", "open", "opening", "opens", "close", "closing", "closes",
    "work", "works", "working", "broken", "break", "breaks", "stopped",
    "stop", "stops", "freeze", "freezes", "frozen", "hang", "hangs",
    "slow", "slowly", "fast", "issue", "issues", "problem", "problems",
    "cannot", "unable", "does", "not", "show", "shows", "showing",
    "display", "displays", "displaying", "message", "messages",
    "expected", "actual", "behavior", "happens", "happen", "happened",
    "occurs", "occurred", "occurring", "after", "before", "when", "then",
    "tried", "trying", "attempt", "attempted", "login", "logging",
    "logged", "submit", "submitting", "submitted", "save", "saving",
    "saved", "update", "updating", "updated", "delete", "deleting",
    "deleted", "create", "creating", "created", "request", "requests",
    "response", "responses", "server", "client", "browser", "mobile",
    "desktop", "version", "install", "installing", "reproduce",
    "reproducing", "steps", "result", "results", "unexpected", "keeps",
    "keep", "repeatedly", "sometimes", "always", "never", "getting",
    "get", "gets", "returns", "returned", "return", "throws", "throwing",
    "threw", "thrown", "test", "tested", "testing", "data", "field",
    "fields", "form", "value", "values", "empty", "blank", "missing",
    "wrong", "incorrect", "unresponsive", "stuck", "loop", "infinite",
    "code", "function", "module", "component", "endpoint", "api",
}


def _matches_structural_pattern(text: str) -> bool:
    return any(pattern.search(text) for pattern in _STRUCTURAL_PATTERNS)


def _matches_strong_keyword(text_lower: str) -> bool:
    return any(
        re.search(r"\b" + re.escape(keyword) + r"\b", text_lower)
        for keyword in STRONG_TECHNICAL_KEYWORDS
    )


def _count_generic_word_matches(text_lower: str) -> int:
    tokens = re.findall(r"[a-zA-Z]+", text_lower)
    return sum(1 for token in tokens if token in GENERIC_ENGLISH_WORDS)


def validate_bug_report_text(raw_text: Optional[str]) -> ValidationResult:
    """
    Determine whether `raw_text` contains enough meaningful bug/error
    information to run the AI Analysis Pipeline on.

    Args:
        raw_text: the raw text pasted into the Analyze Bug page.

    Returns:
        ValidationResult: {"is_valid": bool, "reason": str}. `reason` is
        for internal/debugging use — the user-facing message is fixed
        (see DEFAULT_INVALID_MESSAGE) so it doesn't leak detection
        internals to the person using the app.
    """
    if not raw_text or not raw_text.strip():
        return {"is_valid": False, "reason": "empty"}

    text = raw_text.strip()

    if len(text) < MIN_LENGTH:
        return {"is_valid": False, "reason": "too_short"}

    if _matches_structural_pattern(text):
        return {"is_valid": True, "reason": "structural_pattern"}

    text_lower = text.lower()

    if _matches_strong_keyword(text_lower):
        return {"is_valid": True, "reason": "technical_keyword"}

    if _count_generic_word_matches(text_lower) >= MIN_GENERIC_WORD_MATCHES:
        return {"is_valid": True, "reason": "natural_language"}

    return {"is_valid": False, "reason": "no_meaningful_content"}
