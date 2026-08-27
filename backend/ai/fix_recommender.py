"""
Intelligent Fix Recommendation Engine — backend/ai/fix_recommender.py

Generates a structured fix recommendation by combining:
    1. The current rule-based diagnosis (category, severity, root cause).
    2. The Top 3 similar historical bugs found by the Duplicate Detection
       Agent — their Category and Severity are read directly from
       data/bugs.csv; their Root Cause and Suggested Fix are not stored
       fields, so they're derived by re-running the same rule engine
       (`ai.rule_analyzer.analyze_bug_text`) against each historical
       bug's stored Title + Description + Stack Trace.

The result is a category-adaptive, multi-section recommendation — not a
single hardcoded string. TF-IDF-derived historical evidence (via
similar_bug_ids) remains the primary source; optionally, additional
confirmed-fix evidence retrieved by the semantic RAG layer
(backend.rag.retriever) can be passed in and is folded in the same way
(see _merge_rag_evidence) — purely additive, never required, never
fabricated. This module exposes one stable entry point,
`generate_recommendation()`.
"""

from typing import TypedDict

from .rule_analyzer import UNKNOWN_CATEGORY, analyze_bug_text
from utils.bug_storage import STATUS_RESOLVED, read_all_bugs

MAX_HISTORICAL_NOTES = 2


class Recommendation(TypedDict):
    recommended_resolution: str
    immediate_actions: list[str]
    investigation_steps: list[str]
    files_modules_to_inspect: list[str]
    possible_risks: list[str]
    prevention_tips: list[str]
    resolved_bugs_considered: int


# ---------------------------------------------------------------------
# Category-adaptive action templates
# ---------------------------------------------------------------------

_CATEGORY_TEMPLATES = {
    "Authentication": {
        "immediate_actions": [
            "Verify the reported credentials are correct and not locked or expired",
            "Check token expiry and the session refresh flow",
        ],
        "investigation_steps": [
            "Inspect authentication middleware logs for the failing request",
            "Confirm the identity provider / SSO configuration hasn't changed recently",
            "Reproduce the login flow in a staging environment",
        ],
        "files_modules_to_inspect": [
            "Authentication middleware",
            "Session/token management module",
            "Login controller or handler",
        ],
        "possible_risks": [
            "Users may be locked out of the system",
            "Repeated failures could trigger account-lockout policies",
            "Incorrect token validation changes could introduce a security gap",
        ],
        "prevention_tips": [
            "Add automated tests covering token expiry edge cases",
            "Monitor authentication failure rates with alerting",
            "Rotate and audit credentials/secrets on a regular schedule",
        ],
    },
    "Database": {
        "immediate_actions": [
            "Verify the database connection and credentials are valid",
            "Check whether the database service is reachable and running",
        ],
        "investigation_steps": [
            "Inspect the failing SQL query for syntax or logic errors",
            "Check transaction rollback behavior and isolation level",
            "Review recent schema migrations or index changes",
        ],
        "files_modules_to_inspect": [
            "Database connection/pool configuration",
            "ORM models or query layer",
            "Migration scripts",
        ],
        "possible_risks": [
            "Data inconsistency if a transaction partially commits",
            "Downtime for dependent services if the database is unreachable",
            "Connection pool exhaustion under load",
        ],
        "prevention_tips": [
            "Add retry logic with backoff for transient connection errors",
            "Set and actively monitor connection pool size limits",
            "Add integration tests covering transaction rollback paths",
        ],
    },
    "API": {
        "immediate_actions": [
            "Check the request payload and headers for correctness",
            "Verify the API endpoint is reachable and returning expected status codes",
        ],
        "investigation_steps": [
            "Inspect server logs for the failing endpoint",
            "Confirm downstream/dependent service health",
            "Check whether the API contract or schema recently changed",
        ],
        "files_modules_to_inspect": [
            "API route/controller handling the request",
            "Request validation/serialization layer",
            "API gateway or middleware configuration",
        ],
        "possible_risks": [
            "Clients may receive inconsistent or failed responses",
            "Cascading failures if downstream services are affected",
            "Backward-compatibility breakage for existing API consumers",
        ],
        "prevention_tips": [
            "Add contract tests between the API producer and its consumers",
            "Set up monitoring/alerting on error rate and latency",
            "Version the API to avoid breaking existing clients",
        ],
    },
    "UI": {
        "immediate_actions": [
            "Inspect the browser console for JavaScript errors",
            "Reproduce the issue across different browsers and screen sizes",
        ],
        "investigation_steps": [
            "Validate DOM changes and component state around the failure",
            "Check for CSS conflicts or layout regressions",
            "Review recent frontend changes to the affected component",
        ],
        "files_modules_to_inspect": [
            "Affected UI component(s)",
            "Shared stylesheet or design tokens",
            "State management logic for the view",
        ],
        "possible_risks": [
            "Degraded user experience or broken workflows",
            "Accessibility regressions if elements are hidden or misrendered",
            "Inconsistent behavior across browsers or devices",
        ],
        "prevention_tips": [
            "Add visual regression tests for critical UI flows",
            "Add null/undefined checks before rendering dynamic data",
            "Review CSS specificity conflicts as part of code review",
        ],
    },
    "Network": {
        "immediate_actions": [
            "Check API endpoint connectivity and DNS resolution",
            "Verify firewall and security group rules allow the required traffic",
        ],
        "investigation_steps": [
            "Inspect timeout configuration on both client and server",
            "Check SSL/TLS certificate validity",
            "Review proxy/load balancer configuration for recent changes",
        ],
        "files_modules_to_inspect": [
            "Network/HTTP client configuration",
            "Firewall or security group rules",
            "Proxy or load balancer configuration",
        ],
        "possible_risks": [
            "Intermittent failures that are hard to reproduce",
            "Requests silently dropped or timing out under load",
            "Service unavailability if the network path is fully blocked",
        ],
        "prevention_tips": [
            "Add retry with exponential backoff for transient network errors",
            "Monitor network latency and packet loss",
            "Document and version-control firewall/proxy rules",
        ],
    },
    "Performance": {
        "immediate_actions": [
            "Check current CPU and memory usage on the affected service",
            "Identify whether the slowdown correlates with a traffic spike",
        ],
        "investigation_steps": [
            "Analyze slow queries or expensive operations in the affected code path",
            "Review memory consumption trends for possible leaks",
            "Profile the affected code path under realistic load",
        ],
        "files_modules_to_inspect": [
            "Hot code path identified by profiling",
            "Caching layer configuration",
            "Database query layer",
        ],
        "possible_risks": [
            "Cascading slowdowns affecting other services",
            "Increased infrastructure costs from over-provisioning",
            "Request timeouts and dropped connections under load",
        ],
        "prevention_tips": [
            "Add performance regression tests / benchmarks",
            "Set up resource-usage alerting with sensible thresholds",
            "Cache expensive or frequently repeated operations",
        ],
    },
    "File System": {
        "immediate_actions": [
            "Verify the expected file/directory exists at the reported path",
            "Check available disk space on the affected host",
        ],
        "investigation_steps": [
            "Check file and directory permissions for the reported path",
            "Review recent deployment or cleanup scripts that touch this path",
            "Confirm the path is correct across environments (dev/staging/prod)",
        ],
        "files_modules_to_inspect": [
            "File I/O module handling the operation",
            "Deployment/cleanup scripts",
            "Storage/volume configuration",
        ],
        "possible_risks": [
            "Data loss if cleanup scripts remove files prematurely",
            "Service crashes if a required file is unexpectedly missing",
            "Silent failures if errors aren't properly surfaced",
        ],
        "prevention_tips": [
            "Add disk space monitoring and alerting",
            "Validate required files exist as part of startup health checks",
            "Use least-privilege, explicit permissions for file operations",
        ],
    },
    UNKNOWN_CATEGORY: {
        "immediate_actions": [
            "Gather more context: reproduction steps, environment, and recent changes",
            "Check application and server logs around the time of the failure",
        ],
        "investigation_steps": [
            "Manually review the raw log or stack trace for clues",
            "Ask the reporter for additional details if information is incomplete",
            "Search the Knowledge Base for related past incidents",
        ],
        "files_modules_to_inspect": [
            "Not enough information to identify specific files or modules",
        ],
        "possible_risks": [
            "The root cause may recur if not properly investigated",
        ],
        "prevention_tips": [
            "Encourage more detailed bug reports (logs, steps to reproduce)",
            "Add logging/observability in the affected area for next time",
        ],
    },
}


# ---------------------------------------------------------------------
# Sub-rule-specific templates — override the category-level template
# above when rule_analyzer identified a *specific* scenario (see
# sub_rule_id on BugAnalysis). This is what keeps recommendations
# genuinely matched to the diagnosed root cause: e.g. a NullPointerException
# during login gets "find the null reference" advice, not "verify your
# password", even though both are Authentication-category bugs.
# ---------------------------------------------------------------------

_SUB_RULE_TEMPLATES = {
    "auth_null_reference": {
        "immediate_actions": [
            "Identify exactly which object/variable was null at the point of failure",
            "Check the indicated file, method, and line number from the stack trace",
        ],
        "investigation_steps": [
            "Trace where the null object should have been initialized or set",
            "Check for a missing null check before the object is dereferenced",
            "Verify any required service/dependency injection completed successfully before this code ran",
        ],
        "files_modules_to_inspect": [
            "The specific file/method/line reported in the stack trace",
            "Object/session initialization code in the authentication flow",
        ],
        "possible_risks": [
            "The application crashes for any user hitting this code path, not just one account",
            "A rushed fix that only suppresses the null check could hide the real initialization bug",
        ],
        "prevention_tips": [
            "Add a null check with a clear error message instead of letting it crash",
            "Add a unit/integration test covering the missing-object scenario",
        ],
    },
    "auth_token_expired": {
        "immediate_actions": [
            "Confirm the session/token expiry settings currently in effect",
            "Check whether the token refresh flow ran and what it returned",
        ],
        "investigation_steps": [
            "Verify the token/session validity window and renewal logic",
            "Check for clock skew between services that issue and validate the token",
            "Confirm the identity-provider configuration for token lifetime hasn't changed",
        ],
        "files_modules_to_inspect": [
            "Session/token management module",
            "Token refresh/renewal logic",
        ],
        "possible_risks": [
            "Users get logged out unexpectedly if expiry is too aggressive",
            "A too-long expiry window increases the security exposure of stolen tokens",
        ],
        "prevention_tips": [
            "Add monitoring for abnormal token-expiry/refresh failure rates",
            "Add tests covering token expiry and refresh edge cases",
        ],
    },
    "auth_misconfiguration": {
        "immediate_actions": [
            "Check recent changes to the identity provider / SSO / OAuth / LDAP configuration",
            "Confirm the authentication service itself is healthy",
        ],
        "investigation_steps": [
            "Review identity-provider and authentication-service logs for configuration errors",
            "Verify SSO/OAuth/LDAP endpoint URLs, certificates, and credentials are current",
            "Reproduce against a known-good configuration to isolate the change",
        ],
        "files_modules_to_inspect": [
            "Identity provider / SSO / OAuth / LDAP configuration",
            "Authentication service startup and configuration loading code",
        ],
        "possible_risks": [
            "Likely affects all users, not just one account — treat as high urgency",
            "Rolling back the wrong configuration change could reintroduce a prior issue",
        ],
        "prevention_tips": [
            "Version-control and review authentication configuration changes",
            "Add a health check that validates identity-provider connectivity on deploy",
        ],
    },
    "auth_invalid_credentials": {
        "immediate_actions": [
            "Verify the submitted credentials are actually correct",
            "Confirm the account is active and not locked",
        ],
        "investigation_steps": [
            "Check the identity provider/user store for the account in question",
            "Confirm password hashing/comparison logic hasn't changed recently",
            "Check for recent credential or secret rotation affecting this account",
        ],
        "files_modules_to_inspect": [
            "Login controller or handler",
            "Credential validation logic",
        ],
        "possible_risks": [
            "Repeated failures could trigger account-lockout policies",
            "If widespread, may indicate a broken credential-validation deploy rather than one bad password",
        ],
        "prevention_tips": [
            "Add clear, non-revealing error messaging to help users self-diagnose typos vs. lockouts",
            "Monitor authentication failure rates for spikes indicating a systemic issue",
        ],
    },
    "db_connection_refused": {
        "immediate_actions": [
            "Check whether the database server is running and reachable",
            "Verify the configured host and port are correct",
        ],
        "investigation_steps": [
            "Check network connectivity and firewall/container network rules between the application and the database",
            "Review the connection timeout and connection pool settings",
            "Check whether the database was recently restarted, moved, or had its address changed",
        ],
        "files_modules_to_inspect": [
            "Database connection/pool configuration",
            "Network/firewall/container network configuration",
        ],
        "possible_risks": [
            "Complete outage for any feature depending on the database",
            "Requests may pile up waiting on connection timeouts, compounding the impact",
        ],
        "prevention_tips": [
            "Add health checks and alerting on database reachability",
            "Add retry logic with backoff for transient connection failures",
        ],
    },
    "db_pool_exhausted": {
        "immediate_actions": [
            "Check current active connection count against the configured pool size",
            "Identify whether a recent traffic spike or a connection leak is the trigger",
        ],
        "investigation_steps": [
            "Review connection pool size and timeout configuration",
            "Check for connections that aren't being closed/released after use",
            "Monitor active connection counts under load to confirm the exhaustion pattern",
        ],
        "files_modules_to_inspect": [
            "Database connection pool configuration",
            "Code paths that acquire a connection (check for missing close/release)",
        ],
        "possible_risks": [
            "New requests fail or queue indefinitely once the pool is exhausted",
            "Increasing pool size without fixing a leak just delays the same failure",
        ],
        "prevention_tips": [
            "Ensure connections are released in a finally-block/context-manager pattern",
            "Add monitoring/alerting on pool utilization",
        ],
    },
    "db_invalid_credentials": {
        "immediate_actions": [
            "Verify the database username and password currently configured",
            "Confirm the account has the required privileges",
        ],
        "investigation_steps": [
            "Check for recent database credential or secret rotation",
            "Confirm the application's configured credentials match what the database expects",
            "Check database-side logs for the specific authentication rejection reason",
        ],
        "files_modules_to_inspect": [
            "Database connection configuration / secrets management",
        ],
        "possible_risks": [
            "Complete outage for any feature depending on the database until credentials are fixed",
        ],
        "prevention_tips": [
            "Automate credential rotation with coordinated config updates",
            "Add a startup health check that validates database credentials",
        ],
    },
    "db_query_error": {
        "immediate_actions": [
            "Inspect the specific failing query for syntax or logic errors",
            "Identify the exact constraint or key involved, if the error names one",
        ],
        "investigation_steps": [
            "Review the relevant table constraint/index definitions",
            "Check for concurrent transactions that could cause a deadlock",
            "Review recent schema migrations or ORM model changes touching this query",
        ],
        "files_modules_to_inspect": [
            "The specific query/ORM code path involved",
            "Relevant schema/migration files",
        ],
        "possible_risks": [
            "Data integrity issues if a constraint violation is being silently retried incorrectly",
            "Other queries against the same table/transaction pattern may share the same bug",
        ],
        "prevention_tips": [
            "Add tests covering the specific constraint/edge case that failed",
            "Add query-level logging for easier diagnosis next time",
        ],
    },
}


def _derive_historical_diagnoses(similar_bug_ids: list[str]) -> list[dict]:
    """
    For each similar historical bug, read its Category/Severity directly
    from storage. For its Root Cause and Suggested Fix, prefer the real,
    developer-confirmed Actual Root Cause / Actual Fix when the bug is
    marked Resolved and those fields were filled in (see the Resolution
    Learning feature) — otherwise fall back to deriving them by running
    the rule engine against the bug's stored Title + Description + Stack
    Trace, same as for a fresh bug.
    """
    if not similar_bug_ids:
        return []

    bugs_by_id = {bug.get("Bug ID"): bug for bug in read_all_bugs()}

    diagnoses = []
    for bug_id in similar_bug_ids:
        bug = bugs_by_id.get(bug_id)
        if not bug:
            continue

        combined_text = " ".join(
            part for part in (
                bug.get("Bug Title", ""),
                bug.get("Bug Description", ""),
                bug.get("Stack Trace", ""),
            ) if part
        )
        derived = analyze_bug_text(combined_text)

        actual_root_cause = (bug.get("Actual Root Cause") or "").strip()
        actual_fix = (bug.get("Actual Fix") or "").strip()
        has_confirmed_resolution = (
            bug.get("Status") == STATUS_RESOLVED and bool(actual_root_cause) and bool(actual_fix)
        )

        diagnoses.append({
            "bug_id": bug_id,
            "category": bug.get("Category") or derived["category"],
            "severity": bug.get("Severity") or derived["severity"],
            "root_cause": actual_root_cause if has_confirmed_resolution else derived["root_cause"],
            "suggested_fix": actual_fix if has_confirmed_resolution else derived["suggested_fix"],
            "is_resolved": has_confirmed_resolution,
        })

    return diagnoses


def _build_resolution_summary(
    category: str, severity: str, historical_diagnoses: list[dict]
) -> tuple[str, int]:
    """
    Synthesize a one-paragraph summary combining current + historical
    evidence.

    Returns (summary_text, resolved_count_used) — resolved_count_used is
    the number of resolved historical bugs actually referenced by
    summary_text, not a count over the full (possibly category-irrelevant)
    historical_diagnoses pool. This keeps the number shown to the user
    consistent with what the wording claims: if the summary doesn't cite
    any historical fix (e.g. the Unknown-category branch, which never
    references historical_diagnoses at all), the count is 0.
    """
    if category == UNKNOWN_CATEGORY:
        return (
            "This report doesn't match a known category with high confidence. "
            "Manual investigation is recommended before applying a fix.",
            0,
        )

    matching_historical = [d for d in historical_diagnoses if d["category"] == category]
    # Resolved bugs carry confirmed, real fix information — surface them first.
    matching_historical.sort(key=lambda d: d["is_resolved"], reverse=True)

    if matching_historical:
        count = len(matching_historical)
        resolved_count = sum(1 for d in matching_historical if d["is_resolved"])
        plural = "s" if count != 1 else ""
        verb = "were" if count != 1 else "was"
        confirmation_note = (
            f" This is based on {resolved_count} previously resolved bug{'s' if resolved_count != 1 else ''}."
            if resolved_count > 0 else ""
        )
        summary = (
            f"This appears to be a {severity.lower()}-severity {category} issue. "
            f"{count} similar historical bug{plural} in the same category {verb} previously "
            f"resolved using a comparable approach: {matching_historical[0]['suggested_fix']} "
            f"Apply the same remediation pattern, adjusted for the current context.{confirmation_note}"
        )
        return summary, resolved_count

    return (
        f"This appears to be a {severity.lower()}-severity {category} issue based on the rule-based "
        "diagnosis. No closely related historical bugs were found, so treat this as a new "
        f"occurrence and follow the standard {category} remediation steps below.",
        0,
    )


def _historical_investigation_notes(historical_diagnoses: list[dict]) -> list[str]:
    """Turn up to MAX_HISTORICAL_NOTES historical matches into extra investigation-step bullets, resolved bugs first."""
    ordered = sorted(historical_diagnoses, key=lambda d: d["is_resolved"], reverse=True)
    notes = []
    for diagnosis in ordered[:MAX_HISTORICAL_NOTES]:
        label = "confirmed root cause" if diagnosis["is_resolved"] else "previously diagnosed as"
        notes.append(
            f"Review {diagnosis['bug_id']} ({diagnosis['severity']} severity) — "
            f"{label}: {diagnosis['root_cause']}"
        )
    return notes


def _merge_rag_evidence(historical_diagnoses: list[dict], rag_bugs: list[dict]) -> list[dict]:
    """
    Fold RAG-retrieved historical bugs into the same historical-diagnosis
    shape produced by _derive_historical_diagnoses (from TF-IDF duplicate
    detection), so retrieved semantic evidence can influence the
    resolution summary and investigation notes exactly like a TF-IDF
    match does, via the existing _build_resolution_summary /
    _historical_investigation_notes functions — without duplicating
    that logic here.

    Only RAG bugs not already surfaced via TF-IDF are added (dedup by
    bug_id), and only bugs RAG returned with a confirmed, already-stored
    Actual Root Cause + Actual Fix are merged in — nothing is derived,
    guessed, or invented here; an unresolved RAG match contributes
    nothing new since there's no confirmed fix to add.
    """
    if not rag_bugs:
        return historical_diagnoses

    existing_ids = {d["bug_id"] for d in historical_diagnoses}
    merged = list(historical_diagnoses)

    for bug in rag_bugs:
        bug_id = bug.get("bug_id")
        if not bug_id or bug_id in existing_ids:
            continue

        root_cause = (bug.get("actual_root_cause") or "").strip()
        suggested_fix = (bug.get("actual_fix") or "").strip()
        if not (bug.get("status") == STATUS_RESOLVED and root_cause and suggested_fix):
            continue

        merged.append({
            "bug_id": bug_id,
            "category": bug.get("category", ""),
            "severity": bug.get("severity", ""),
            "root_cause": root_cause,
            "suggested_fix": suggested_fix,
            "is_resolved": True,
        })
        existing_ids.add(bug_id)

    return merged


def generate_recommendation(
    current_analysis: dict,
    similar_bug_ids: list[str],
    rag_context: list[dict] | None = None,
) -> Recommendation:
    """
    Main entry point for the Intelligent Fix Recommendation Engine.

    Args:
        current_analysis: the current bug's diagnosis, as returned by
            `ai.rule_analyzer.analyze_bug_text()` (must include at least
            "category" and "severity"; "sub_rule_id" is used when present
            for a more specific recommendation than category alone).
        similar_bug_ids: Bug IDs of the Top 3 similar historical bugs, as
            returned by `ai.similarity_search.find_similar_bugs()`
            (TF-IDF duplicate detection — unchanged, still the primary
            signal).
        rag_context: optional additional historical bugs retrieved by
            the semantic RAG retriever (`backend.rag.retriever.retrieve`),
            each a dict with at least bug_id/category/severity/status/
            actual_root_cause/actual_fix. Purely additive: only used to
            surface confirmed historical fixes TF-IDF didn't already
            find (see _merge_rag_evidence) — never required, never
            fabricated, and TF-IDF matches always take precedence for a
            given bug_id.

    Returns:
        Recommendation: a structured, category-adaptive dict with
        recommended_resolution, immediate_actions, investigation_steps,
        files_modules_to_inspect, possible_risks, and prevention_tips.
    """
    category = current_analysis.get("category", UNKNOWN_CATEGORY)
    severity = current_analysis.get("severity", "Low")
    sub_rule_id = current_analysis.get("sub_rule_id")

    # Prefer the sub-rule-specific template (e.g. "auth_null_reference")
    # when available — it's diagnosed from more specific evidence than
    # the category alone, so it produces a recommendation that actually
    # matches what was detected instead of generic category-level advice.
    template = _SUB_RULE_TEMPLATES.get(sub_rule_id) or _CATEGORY_TEMPLATES.get(
        category, _CATEGORY_TEMPLATES[UNKNOWN_CATEGORY]
    )
    historical_diagnoses = _derive_historical_diagnoses(similar_bug_ids)
    historical_diagnoses = _merge_rag_evidence(historical_diagnoses, rag_context or [])

    investigation_steps = list(template["investigation_steps"])
    investigation_steps.extend(_historical_investigation_notes(historical_diagnoses))

    resolution_summary, resolved_bugs_considered = _build_resolution_summary(
        category, severity, historical_diagnoses
    )

    return {
        "recommended_resolution": resolution_summary,
        "immediate_actions": list(template["immediate_actions"]),
        "investigation_steps": investigation_steps,
        "files_modules_to_inspect": list(template["files_modules_to_inspect"]),
        "possible_risks": list(template["possible_risks"]),
        "prevention_tips": list(template["prevention_tips"]),
        "resolved_bugs_considered": resolved_bugs_considered,
    }
