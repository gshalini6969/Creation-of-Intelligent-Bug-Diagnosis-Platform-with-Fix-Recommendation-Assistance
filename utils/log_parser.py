"""
Log Parsing Agent — utils/log_parser.py

The first AI agent in the Smart Bug Analyzer pipeline. It converts a raw
bug report, error log, or stack trace into structured information:

    - Exception Type
    - Programming Language
    - File Name
    - Method Name
    - Line Number
    - Error Message

This implementation is rule-based (regex pattern matching) — no ML,
embeddings, or similarity search yet. It supports common stack trace
formats for Python, Java, and JavaScript, and falls back gracefully
("Not Detected") when a field or the language itself can't be identified.

The module is intentionally framework-agnostic (no Flask imports) and
exposes a single, stable entry point — `parse_log_text()` — so future
agents (similarity search, fix recommendation, etc.) can import and
reuse it without depending on the web layer.
"""

import re
from typing import Optional, TypedDict

NOT_DETECTED = "Not Detected"


class ParsedBugInfo(TypedDict):
    """Structured output of the Log Parsing Agent."""
    exception_type: str
    programming_language: str
    file_name: str
    method_name: str
    line_number: str
    error_message: str


def _empty_result() -> ParsedBugInfo:
    """A result dict with every field defaulted to NOT_DETECTED."""
    return {
        "exception_type": NOT_DETECTED,
        "programming_language": NOT_DETECTED,
        "file_name": NOT_DETECTED,
        "method_name": NOT_DETECTED,
        "line_number": NOT_DETECTED,
        "error_message": NOT_DETECTED,
    }


# ---------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------

# Python: Traceback (most recent call last):
#           File "app.py", line 42, in <module>
#         ZeroDivisionError: division by zero
_PYTHON_TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE)

# Built-in exception names that exist only in Python (not Java or
# JavaScript) — a bare mention of one of these is genuine evidence of
# Python, unlike e.g. "TypeError" which is ambiguous (exists in both
# Python and JavaScript) and is deliberately NOT included here.
_PYTHON_EXCLUSIVE_EXCEPTIONS = re.compile(
    r"\b(?:ValueError|IndexError|KeyError|AttributeError|ZeroDivisionError|"
    r"FileNotFoundError|ImportError|ModuleNotFoundError|StopIteration|"
    r"NameError|UnboundLocalError|IndentationError)\b"
)
_PYTHON_FRAME_RE = re.compile(r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\S+)')
_PYTHON_EXCEPTION_LINE_RE = re.compile(r"^([\w.]*(?:Error|Exception|Warning))\s*:\s*(.*)$", re.MULTILINE)

# Error message phrasing produced only by JS engines (V8/Node), even
# without a file extension or stack frame — genuine evidence, not a
# guess, since no other language phrases errors this way.
_JS_EXCLUSIVE_PHRASES_RE = re.compile(
    r"cannot read propert|is not a function\b|is not defined\b|"
    r"undefined is not an object",
    re.IGNORECASE,
)

# Java:   at com.example.Main.process(Main.java:15)
#       java.lang.NullPointerException: Cannot invoke "String.length()"...
_JAVA_FRAME_RE = re.compile(r"at\s+([\w.$]+)\.([\w$<>]+)\(([\w\-.]+\.java):(\d+)\)")
_JAVA_EXCEPTION_RE = re.compile(r"((?:[\w]+\.)+[A-Z][\w]*(?:Exception|Error))\s*:\s*(.*)")

# JavaScript/Node: at Object.<anonymous> (/app/index.js:10:15)
#                TypeError: Cannot read properties of undefined (reading 'foo')
_JS_FRAME_RE = re.compile(r"at\s+([\w.<>$]+)?\s*\(?([^\s()]+\.(?:js|ts|jsx|tsx)):(\d+):(\d+)\)?")
_JS_EXCEPTION_RE = re.compile(r"^([A-Z][\w]*(?:Error|Exception))\s*:\s*(.*)$", re.MULTILINE)

# Generic fallback: "SomeName.Error: message" / "SomeError: message" on one line.
# Used when the language can't be determined but an exception-like line is present.
_GENERIC_EXCEPTION_RE = re.compile(r"([\w.$]*[A-Za-z][\w.$]*(?:Exception|Error|Warning))\s*:\s*(.+)")

# Bare exception/error class name with NO colon or message required — e.g. a
# lone "java.lang.NullPointerException" or "NullPointerException" pasted by
# itself. Requires the final segment to start with an uppercase letter and
# end in Exception/Error, so it can't match ordinary lowercase words like
# "error" or "failure" (those don't match the required capitalized suffix).
_BARE_EXCEPTION_RE = re.compile(r"\b((?:[A-Za-z_]\w*\.)*[A-Z]\w*(?:Exception|Error))\b")


# ---------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------

def detect_language(text: str) -> str:
    """
    Best-effort detection of the source language behind a stack trace or
    log snippet.

    Returns:
        One of "Python", "Java", "JavaScript", or NOT_DETECTED.
    """
    if _PYTHON_TRACEBACK_RE.search(text) or _PYTHON_FRAME_RE.search(text):
        return "Python"
    if _JAVA_FRAME_RE.search(text):
        return "Java"
    if _JS_FRAME_RE.search(text):
        return "JavaScript"

    # Looser fallbacks for partial/single-line input without a full trace.
    if re.search(r"\bat\s+[\w.$]+\([\w.\-]+\.java:\d+\)", text):
        return "Java"
    if re.search(r'\.py["\']?,?\s*line\s*\d+', text):
        return "Python"
    if re.search(r"\.(?:js|ts|jsx|tsx):\d+", text):
        return "JavaScript"
    if _PYTHON_EXCLUSIVE_EXCEPTIONS.search(text):
        return "Python"
    if _JS_EXCLUSIVE_PHRASES_RE.search(text):
        return "JavaScript"

    return NOT_DETECTED


# ---------------------------------------------------------------------
# Language-specific parsers
# ---------------------------------------------------------------------

def parse_python_log(text: str) -> ParsedBugInfo:
    """Extract structured fields from a Python traceback."""
    result = _empty_result()
    result["programming_language"] = "Python"

    frames = _PYTHON_FRAME_RE.findall(text)
    if frames:
        # The last frame is deepest in the call stack — closest to the
        # actual point of failure.
        file_name, line_number, method_name = frames[-1]
        result["file_name"] = file_name
        result["line_number"] = line_number
        result["method_name"] = method_name

    last_match = None
    for match in _PYTHON_EXCEPTION_LINE_RE.finditer(text):
        last_match = match  # keep the final exception line (the one actually raised)
    if last_match:
        result["exception_type"] = last_match.group(1)
        message = last_match.group(2).strip()
        result["error_message"] = message if message else NOT_DETECTED

    return result


def parse_java_log(text: str) -> ParsedBugInfo:
    """Extract structured fields from a Java stack trace."""
    result = _empty_result()
    result["programming_language"] = "Java"

    frames = _JAVA_FRAME_RE.findall(text)
    if frames:
        # The first "at" frame is the top of the stack — where the
        # exception originated.
        class_path, method_name, file_name, line_number = frames[0]
        result["file_name"] = file_name
        result["method_name"] = f"{class_path}.{method_name}"
        result["line_number"] = line_number

    exception_match = _JAVA_EXCEPTION_RE.search(text)
    if exception_match:
        result["exception_type"] = exception_match.group(1)
        message = exception_match.group(2).strip()
        result["error_message"] = message if message else NOT_DETECTED

    return result


def parse_javascript_log(text: str) -> ParsedBugInfo:
    """Extract structured fields from a JavaScript/Node.js stack trace."""
    result = _empty_result()
    result["programming_language"] = "JavaScript"

    frames = _JS_FRAME_RE.findall(text)
    if frames:
        method_name, file_name, line_number, _column = frames[0]
        result["file_name"] = file_name
        result["method_name"] = method_name if method_name else NOT_DETECTED
        result["line_number"] = line_number

    exception_match = _JS_EXCEPTION_RE.search(text)
    if exception_match:
        result["exception_type"] = exception_match.group(1)
        message = exception_match.group(2).strip()
        result["error_message"] = message if message else NOT_DETECTED

    return result


_LANGUAGE_PARSERS = {
    "Python": parse_python_log,
    "Java": parse_java_log,
    "JavaScript": parse_javascript_log,
}


# ---------------------------------------------------------------------
# Fallback handling (language undetermined)
# ---------------------------------------------------------------------

def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return NOT_DETECTED


def _normalize_exception_type(exception_type: str) -> str:
    """
    Strip a dotted package/module prefix down to the meaningful exception
    name, e.g. "java.lang.NullPointerException" -> "NullPointerException",
    "java.sql.SQLException" -> "SQLException". Names with no dots (e.g.
    "ValueError") are returned unchanged.
    """
    return exception_type.rsplit(".", 1)[-1]


def _fill_missing_exception_info(result: ParsedBugInfo, text: str) -> ParsedBugInfo:
    """
    If a language-specific parser couldn't find an exception type/message
    (e.g. the user pasted only a partial snippet), try progressively
    looser patterns before giving up:
      1. "ExceptionName: message" (colon + message required)
      2. A bare exception/error class name with no colon or message at
         all (e.g. just "java.lang.NullPointerException" pasted alone)
    """
    if result["exception_type"] == NOT_DETECTED:
        match = _GENERIC_EXCEPTION_RE.search(text)
        if match:
            result["exception_type"] = match.group(1)
            message = match.group(2).strip()
            result["error_message"] = message if message else NOT_DETECTED
        else:
            bare_match = _BARE_EXCEPTION_RE.search(text)
            if bare_match:
                result["exception_type"] = bare_match.group(1)
                if result["error_message"] == NOT_DETECTED:
                    result["error_message"] = _first_non_empty_line(text)
            elif result["error_message"] == NOT_DETECTED:
                result["error_message"] = _first_non_empty_line(text)

    return result


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------

def parse_log_text(raw_text: Optional[str]) -> ParsedBugInfo:
    """
    Main entry point for the Log Parsing Agent.

    Detects the programming language, dispatches to the matching
    language-specific parser, and fills in any still-missing fields with
    a generic fallback. Fields that can't be identified are set to
    "Not Detected" rather than left blank or raising an error.

    Args:
        raw_text: the raw bug report, error log, or stack trace pasted
            by the user. May be None or empty.

    Returns:
        ParsedBugInfo: dict with keys exception_type, programming_language,
        file_name, method_name, line_number, error_message.
    """
    if not raw_text or not raw_text.strip():
        return _empty_result()

    language = detect_language(raw_text)
    parser = _LANGUAGE_PARSERS.get(language)

    if parser is None:
        result = _empty_result()
        result = _fill_missing_exception_info(result, raw_text)
    else:
        result = parser(raw_text)
        result = _fill_missing_exception_info(result, raw_text)

    if result["exception_type"] != NOT_DETECTED:
        result["exception_type"] = _normalize_exception_type(result["exception_type"])

    return result
