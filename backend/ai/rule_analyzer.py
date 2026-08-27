"""
Rule-Based Bug Analyzer — backend/ai/rule_analyzer.py

Analyzes raw bug report / error log / stack trace text using keyword
matching to estimate:

    - Bug Category
    - Severity
    - Priority
    - Possible Root Cause
    - Suggested Fix
    - Confidence Score
    - Matched Keywords (the keywords that drove the category/sub-rule match)

This is a first-pass, purely rule-based implementation — no ML or LLM.
It exposes a single stable entry point, `analyze_bug_text()`, so the
underlying engine can later be swapped for a trained classifier or an
LLM-based analyzer without changing any caller.

Two-tier rules: category classification (as before) is followed by an
optional SUB-RULE match within that category (see "sub_rules" on the
Authentication and Database rules). This is what lets the diagnosis
distinguish e.g. "database unreachable" from "invalid database query"
instead of always returning one generic template per category, and lets
severity/priority reflect the *specific* scenario matched rather than a
flat per-category floor.

`analyze_bug_text()` optionally accepts the Log Parsing Agent's output
(see utils.log_parser.parse_log_text) so a detected exception type (e.g.
"NullPointerException") can inform category/sub-rule matching even when
the exception name itself isn't repeated verbatim elsewhere in the text.
"""

import re
from typing import Optional, TypedDict

UNKNOWN_CATEGORY = "Unknown"
DEFAULT_SEVERITY = "Low"

_SEVERITY_ORDER = ["Low", "Medium", "High", "Critical"]


class BugAnalysis(TypedDict):
    category: str
    severity: str
    priority: str
    root_cause: str
    suggested_fix: str
    confidence: int
    matched_keywords: list[str]
    sub_rule_id: Optional[str]


# ---------------------------------------------------------------------
# Category rules: keywords -> root cause / fix templates + baseline severity
# ---------------------------------------------------------------------

_CATEGORY_RULES = [
    {
        "category": "Authentication",
        "keywords": [
            "authentication", "auth", "login", "log in", "password", "credential",
            "credentials", "unauthorized", "401", "token expired", "invalid token",
            "session expired", "permission denied", "access denied", "sign in",
        ],
        # Used only when no sub-rule below matches a more specific scenario.
        "root_cause": (
            "Authentication failed, but the specific cause (invalid credentials, "
            "a session/token problem, a null reference, or a configuration issue) "
            "could not be determined from the available information."
        ),
        "suggested_fix": (
            "Review the authentication service logs around the time of failure to "
            "narrow down whether this is a credentials issue, a session/token "
            "problem, a code-level null reference, or a configuration issue."
        ),
        "default_severity": "Medium",
        "priority_escalate": False,
        "sub_rules": [
            {
                # A NullPointerException (or equivalent) during login/auth is a
                # code defect, not evidence of bad credentials — must not be
                # diagnosed the same way. See Issue 3.
                "id": "auth_null_reference",
                "keywords": [
                    "nullpointerexception", "null pointer", "npe", "null reference",
                    "undefined reference", "null",
                ],
                "root_cause": (
                    "The login/authentication flow crashed due to a null object or "
                    "reference (e.g. a null user, session, or token object) rather "
                    "than invalid credentials — this points to a missing null check "
                    "or an initialization/configuration bug in the authentication "
                    "code path, not a bad username/password."
                ),
                "suggested_fix": (
                    "Check the authentication code path for missing null checks "
                    "(e.g. a session, token, or user object not initialized before "
                    "use), verify required dependencies are properly configured and "
                    "injected, and add defensive null handling with a clear error "
                    "message instead of letting it crash."
                ),
                "severity": "High",
                "priority_escalate": True,
            },
            {
                "id": "auth_token_expired",
                "keywords": [
                    "token expired", "invalid token", "session expired",
                    "expired session", "token invalid",
                ],
                "root_cause": (
                    "The user's session or authentication token was invalid or had "
                    "expired, requiring re-authentication."
                ),
                "suggested_fix": (
                    "Verify session/token expiry settings, confirm the token "
                    "refresh flow works correctly, and check for clock skew "
                    "between services that validate the token."
                ),
                "severity": "Medium",
                "priority_escalate": False,
            },
            {
                "id": "auth_misconfiguration",
                "keywords": [
                    "misconfigured", "misconfiguration", "configuration",
                    "identity provider", "sso", "oauth", "ldap",
                ],
                "root_cause": (
                    "Authentication failed due to a misconfiguration in the "
                    "identity provider, SSO, or authentication service setup — "
                    "likely impacting all users rather than a single account."
                ),
                "suggested_fix": (
                    "Review recent changes to the authentication/identity-provider "
                    "configuration, verify SSO/OAuth/LDAP settings, and check the "
                    "authentication service's health and logs."
                ),
                "severity": "High",
                "priority_escalate": True,
            },
            {
                "id": "auth_invalid_credentials",
                "keywords": [
                    "invalid credentials", "incorrect password", "wrong password",
                    "access denied", "permission denied", "401", "unauthorized",
                ],
                "root_cause": (
                    "Authentication failed because the provided credentials could "
                    "not be validated against the identity store."
                ),
                "suggested_fix": (
                    "Verify the submitted credentials are correct, confirm the "
                    "account is active and not locked, and check the identity "
                    "provider/user store for the account in question."
                ),
                "severity": "Medium",
                "priority_escalate": False,
            },
        ],
    },
    {
        "category": "Database",
        "keywords": [
            "database", "sql", "query", "deadlock", "connection pool", "db connection",
            "mysql", "postgres", "postgresql", "mongodb", "constraint violation",
            "duplicate key", "foreign key", "transaction", "orm", "connection refused",
        ],
        # Used only when no sub-rule below matches a more specific scenario.
        "root_cause": (
            "A database operation failed, but the specific cause (connectivity, "
            "credentials, pool exhaustion, or a query/constraint issue) could not "
            "be determined from the available information."
        ),
        "suggested_fix": (
            "Review the application and database logs around the time of failure "
            "to narrow down whether this is a connectivity, credentials, "
            "capacity, or query-level issue."
        ),
        "default_severity": "Medium",
        "priority_escalate": False,
        "sub_rules": [
            {
                # Server unreachable / timing out — genuinely urgent, but must
                # not also claim there's a query/constraint problem. See Issue 2.
                "id": "db_connection_refused",
                "keywords": [
                    "connection refused", "econnrefused", "cannot connect",
                    "unable to connect", "unreachable", "connection timeout",
                    "timed out", "timeout",
                ],
                "root_cause": (
                    "The application could not establish a connection to the "
                    "database server — likely because the database server is "
                    "unavailable or not running, the configured host/port is "
                    "incorrect, there is a network connectivity issue between the "
                    "application and the database, or the connection attempt is "
                    "timing out."
                ),
                "suggested_fix": (
                    "Check whether the database server is running and healthy, "
                    "verify the configured host and port, check network "
                    "connectivity and firewall/container network rules between "
                    "the application and the database, and review the connection "
                    "timeout and pool settings."
                ),
                "severity": "Critical",
                "priority_escalate": True,
            },
            {
                "id": "db_pool_exhausted",
                "keywords": [
                    "connection pool", "pool exhausted", "too many connections",
                    "max connections", "pool timeout",
                ],
                "root_cause": (
                    "The database connection pool has been exhausted, likely due "
                    "to connections not being released properly or the pool being "
                    "undersized for the current load."
                ),
                "suggested_fix": (
                    "Review connection pool size and timeout configuration, check "
                    "for connections that aren't being closed/released after use, "
                    "and monitor active connection counts under load."
                ),
                "severity": "High",
                "priority_escalate": True,
            },
            {
                "id": "db_invalid_credentials",
                "keywords": [
                    "access denied", "invalid credentials", "authentication failed",
                    "login failed for user", "invalid password",
                ],
                "root_cause": (
                    "The database rejected the connection because the provided "
                    "credentials are invalid or the account lacks the required "
                    "privileges."
                ),
                "suggested_fix": (
                    "Verify the database username and password, confirm the "
                    "account has the required privileges, and check for recent "
                    "credential or secret rotation."
                ),
                "severity": "High",
                "priority_escalate": False,
            },
            {
                "id": "db_query_error",
                "keywords": [
                    "syntax error", "constraint violation", "duplicate key",
                    "foreign key", "deadlock", "invalid query", "query failed",
                ],
                "root_cause": (
                    "A specific database query failed, likely due to a SQL syntax "
                    "error, a constraint violation (e.g. a duplicate or foreign "
                    "key), or a transaction deadlock."
                ),
                "suggested_fix": (
                    "Inspect the failing query for syntax or logic errors, review "
                    "the relevant constraint definitions, and check for deadlocks "
                    "in concurrent transactions."
                ),
                "severity": "Medium",
                "priority_escalate": False,
            },
        ],
    },
    {
        "category": "API",
        "keywords": [
            "api", "endpoint", "rest", "graphql", "400", "404", "500", "502", "503",
            "timeout", "request failed", "response", "http error", "status code",
            "invalid payload", "malformed request",
        ],
        "root_cause": "An API call failed, likely due to an invalid request, an unexpected server response, or a downstream service error.",
        "suggested_fix": "Check the request payload and headers, inspect server logs for the failing endpoint, verify downstream service health, and confirm the API contract hasn't changed.",
        "default_severity": "Medium",
        "priority_escalate": False,
    },
    {
        "category": "UI",
        "keywords": [
            "ui", "button", "render", "css", "layout", "component", "dom",
            "click", "display", "screen", "modal", "responsive", "browser",
            "undefined is not a function", "cannot read propert",
        ],
        "root_cause": "A frontend rendering or interaction issue occurred, likely due to a JavaScript error, missing/undefined data, or a layout/CSS conflict.",
        "suggested_fix": "Reproduce the issue in the browser console, check for JavaScript errors or undefined values, verify the affected component's props/state, and review recent UI changes.",
        "default_severity": "Medium",
        "priority_escalate": False,
    },
    {
        "category": "Network",
        "keywords": [
            "network", "connection reset", "dns", "unreachable",
            "socket", "econnrefused", "etimedout", "ssl", "tls", "certificate",
            "proxy", "firewall",
        ],
        "root_cause": "A network-level failure occurred, likely due to connectivity loss, DNS resolution issues, or a misconfigured certificate/proxy.",
        "suggested_fix": "Check network connectivity between services, verify DNS resolution, inspect SSL/TLS certificates, and review firewall or proxy configuration.",
        "default_severity": "Medium",
        "priority_escalate": True,
    },
    {
        "category": "Performance",
        "keywords": [
            "slow", "performance", "latency", "memory leak", "high cpu",
            "out of memory", "oom", "degraded", "bottleneck",
            "n+1", "throttle", "rate limit",
        ],
        "root_cause": "The system experienced degraded performance, likely due to a resource bottleneck, an inefficient query/algorithm, or a memory leak.",
        "suggested_fix": "Profile the affected code path, check memory/CPU usage under load, review recent changes for inefficient loops or queries, and consider caching or scaling.",
        "default_severity": "Medium",
        "priority_escalate": False,
    },
    {
        "category": "File System",
        "keywords": [
            "file not found", "no such file", "filesystem", "file system",
            "disk", "enospc", "enoent", "eacces",
            "directory", "read-only file system", "disk full",
        ],
        "root_cause": "A file system operation failed, likely due to a missing file/directory, insufficient permissions, or exhausted disk space.",
        "suggested_fix": "Verify the file/directory path exists, check file and directory permissions, confirm available disk space, and review recent deployment or file-cleanup changes.",
        "default_severity": "Medium",
        "priority_escalate": False,
    },
]

_SEVERITY_KEYWORDS = [
    ("Critical", ["critical", "crash", "outage", "data loss", "down", "security breach", "corrupt", "fatal"]),
    # Deliberately excludes generic words like "error", "exception", "fail",
    # "failed", "failure" — those appear in nearly every bug report by
    # definition and would systematically override the more carefully
    # tuned per-sub-rule severity (e.g. an "incorrect password" report,
    # genuinely Medium severity, would get bumped to High just because it
    # says "login failed"). Only keywords specific enough to reliably
    # indicate elevated severity on their own are listed here.
    ("High", ["unauthorized", "500", "denied", "security vulnerability"]),
    ("Medium", ["warning", "deprecated", "slow", "timeout", "degraded"]),
]

MAX_DISPLAYED_KEYWORDS = 6


def _count_keyword_matches(text_lower: str, keywords: list[str]) -> list[str]:
    """
    Return the keywords that genuinely appear as whole words/phrases in
    text_lower.

    Uses word-boundary matching rather than plain substring containment.
    Substring matching caused real false positives — e.g. the short
    keyword "orm" (meant for the ORM/database term) matching inside
    "format" or "performance", "api" matching inside "rapid", and "sso"
    matching inside "processor" — silently misclassifying unrelated
    reports. `\\b` boundaries also naturally handle multi-word phrases
    like "connection refused" correctly.
    """
    return [kw for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)]


def _detect_category(text_lower: str):
    """Return (best_rule_or_None, matched_keywords) — the rule with the most keyword hits."""
    best_rule = None
    best_matches: list[str] = []

    for rule in _CATEGORY_RULES:
        matches = _count_keyword_matches(text_lower, rule["keywords"])
        if len(matches) > len(best_matches):
            best_rule = rule
            best_matches = matches

    return best_rule, best_matches


def _select_sub_rule(sub_rules: list[dict], text_lower: str):
    """
    Return (best_sub_rule_or_None, matched_keywords) — same "most keyword
    hits wins" logic as _detect_category, but scoped to one category's
    specific sub-scenarios (e.g. Database's connection-failure vs
    query-error sub-rules). Returns (None, []) if no sub-rule has any
    match at all, so callers fall back to the category's generic
    root_cause/suggested_fix/default_severity.
    """
    best_rule = None
    best_matches: list[str] = []

    for sub_rule in sub_rules:
        matches = _count_keyword_matches(text_lower, sub_rule["keywords"])
        if len(matches) > len(best_matches):
            best_rule = sub_rule
            best_matches = matches

    return best_rule, best_matches


def _detect_severity(text_lower: str, baseline_severity: str) -> str:
    """
    Explicit severity keywords can escalate (never downgrade) the
    matched scenario's baseline severity. Uses word-boundary matching
    (see _count_keyword_matches) — substring matching previously let
    e.g. "down" match inside "dropdown", incorrectly escalating an
    unrelated UI report all the way to Critical.
    """
    for level, keywords in _SEVERITY_KEYWORDS:
        if any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in keywords):
            if _SEVERITY_ORDER.index(level) >= _SEVERITY_ORDER.index(baseline_severity):
                return level
            return baseline_severity
    return baseline_severity


def _calculate_confidence(category_match_count: int, sub_rule_match_count: int = 0) -> int:
    """
    Confidence reflects the strength of matched evidence: how many
    category-level keywords matched, plus a bonus when a *specific*
    sub-scenario was also identified (stronger evidence than a broad
    category match alone). Always deterministic, capped at 95% (never
    claim full certainty from keyword matching).
    """
    if category_match_count <= 0:
        return 0
    base = 45 + (category_match_count * 10)
    bonus = sub_rule_match_count * 8
    return min(base + bonus, 95)


def _determine_priority(severity: str, escalate: bool) -> str:
    """
    Derive priority from severity, optionally escalating one level for
    scenarios that represent shared/core infrastructure outages (e.g. a
    database that's completely unreachable, an auth misconfiguration
    affecting everyone) — as opposed to routine, single-user issues
    (e.g. one wrong password), which shouldn't be inflated. Which
    scenarios escalate is decided per sub-rule/category (see
    "priority_escalate" above), not by category membership alone.
    """
    if severity not in _SEVERITY_ORDER:
        return DEFAULT_SEVERITY

    index = _SEVERITY_ORDER.index(severity)
    if escalate and index < len(_SEVERITY_ORDER) - 1:
        index += 1

    return _SEVERITY_ORDER[index]


def analyze_bug_text(raw_text: str, parsed_info: Optional[dict] = None) -> BugAnalysis:
    """
    Main entry point for the rule-based Bug Analyzer.

    Args:
        raw_text: the raw bug report, error log, or stack trace text.
        parsed_info: optional output of utils.log_parser.parse_log_text()
            for this same raw_text. When provided, a detected exception
            type (e.g. "NullPointerException") is folded into the text
            used for category/sub-rule matching, so downstream diagnosis
            is consistent with what the Log Parsing Agent found instead
            of re-deriving it independently and potentially disagreeing.

    Returns:
        BugAnalysis: dict with category, severity, priority, root_cause,
        suggested_fix, confidence (0-100), and matched_keywords.
    """
    if not raw_text or not raw_text.strip():
        return {
            "category": UNKNOWN_CATEGORY,
            "severity": DEFAULT_SEVERITY,
            "priority": DEFAULT_SEVERITY,
            "root_cause": "Not enough information was provided to determine a root cause.",
            "suggested_fix": "Provide a bug report, error log, or stack trace with more detail and try again.",
            "confidence": 0,
            "matched_keywords": [],
            "sub_rule_id": None,
        }

    text_lower = raw_text.lower()

    exception_type = (parsed_info or {}).get("exception_type")
    if exception_type and exception_type != "Not Detected":
        # Fold the parser's detected exception type into the matching
        # text so it can influence category/sub-rule selection even if
        # it isn't repeated verbatim elsewhere in the report.
        text_lower = f"{text_lower} {exception_type.lower()}"

    rule, matches = _detect_category(text_lower)

    if rule is None:
        return {
            "category": UNKNOWN_CATEGORY,
            "severity": DEFAULT_SEVERITY,
            "priority": DEFAULT_SEVERITY,
            "root_cause": "No known pattern matched this report. Manual investigation is required to determine the root cause.",
            "suggested_fix": "Review the raw log/stack trace manually, or provide additional context (e.g. affected module, recent changes).",
            "confidence": 0,
            "matched_keywords": [],
            "sub_rule_id": None,
        }

    sub_rule, sub_matches = (
        _select_sub_rule(rule["sub_rules"], text_lower) if rule.get("sub_rules") else (None, [])
    )

    if sub_rule:
        root_cause = sub_rule["root_cause"]
        suggested_fix = sub_rule["suggested_fix"]
        baseline_severity = sub_rule["severity"]
        escalate = sub_rule["priority_escalate"]
    else:
        root_cause = rule["root_cause"]
        suggested_fix = rule["suggested_fix"]
        baseline_severity = rule["default_severity"]
        escalate = rule["priority_escalate"]

    severity = _detect_severity(text_lower, baseline_severity)
    priority = _determine_priority(severity, escalate)
    confidence = _calculate_confidence(len(matches), len(sub_matches))

    # Preserve match order/uniqueness while combining both evidence sources.
    combined_keywords = list(dict.fromkeys(matches + sub_matches))

    return {
        "category": rule["category"],
        "severity": severity,
        "priority": priority,
        "root_cause": root_cause,
        "suggested_fix": suggested_fix,
        "confidence": confidence,
        "matched_keywords": combined_keywords[:MAX_DISPLAYED_KEYWORDS],
        "sub_rule_id": sub_rule.get("id") if sub_rule else None,
    }
