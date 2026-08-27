"""
Bug report storage helpers.

Handles CSV persistence for submitted bug reports and file storage for
uploaded logs. This module is framework-agnostic (no Flask imports) so
it can be reused by future AI modules, scripts, or tests.
"""

import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional



def secure_filename(filename: str) -> str:
    """Return a safe ASCII filename without requiring a web framework dependency."""
    filename = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    filename = filename.replace("\\", "_").replace("/", "_")
    filename = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
    filename = filename.strip("._")
    return filename or "uploaded_log"

# Project root: .../smart-bug-analyzer
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
BUGS_CSV_PATH = DATA_DIR / "bugs.csv"

CSV_HEADERS = [
    "Bug ID",
    "Submission Date",
    "Submission Time",
    "Bug Title",
    "Bug Description",
    "Stack Trace",
    "Module Name",
    "Category",
    "Severity",
    "Priority",
    "Reporter Name",
    "Uploaded Log File Name",
    "Status",
    "Actual Root Cause",
    "Actual Fix",
    "Resolution Notes",
    "Resolution Date",
]

STATUS_OPEN = "Open"
STATUS_IN_PROGRESS = "In Progress"
STATUS_RESOLVED = "Resolved"
VALID_STATUSES = [STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_RESOLVED]
DEFAULT_STATUS = STATUS_OPEN

ALLOWED_LOG_EXTENSIONS = {".txt", ".log"}

# Guards the "read count -> write row" sequence so concurrent requests
# can't generate the same Bug ID.
_storage_lock = Lock()


def ensure_storage_ready() -> None:
    """Create data/ and uploads/ directories and bugs.csv (with headers) if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    if not BUGS_CSV_PATH.exists():
        with open(BUGS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADERS)
        return

    _migrate_csv_if_needed()


def _migrate_csv_if_needed() -> None:
    """
    If bugs.csv already exists but was written before the Status/
    resolution columns were added, its header row won't match the
    current CSV_HEADERS. `csv.DictReader` takes its field names from
    that header row (not from this module), so leaving it as-is would
    silently misalign every new column on read. Detect that case and
    rewrite the file in place with the current headers, backfilling
    existing rows with sensible defaults (Status="Open", the rest blank).
    """
    with open(BUGS_CSV_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        current_headers = reader.fieldnames or []
        if current_headers == CSV_HEADERS:
            return  # already up to date
        existing_rows = [dict(row) for row in reader]

    migrated_rows = []
    for row in existing_rows:
        migrated_row = {header: row.get(header, "") or "" for header in CSV_HEADERS}
        if not migrated_row["Status"]:
            migrated_row["Status"] = DEFAULT_STATUS
        migrated_rows.append(migrated_row)

    with open(BUGS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(migrated_rows)


def generate_bug_id() -> str:
    """Generate the next sequential Bug ID, e.g. BUG-0001, BUG-0002, ..."""
    ensure_storage_ready()
    with open(BUGS_CSV_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header row
        existing_count = sum(1 for _ in reader)
    return f"BUG-{existing_count + 1:04d}"


def get_current_timestamp() -> tuple[str, str]:
    """Return (date_str, time_str) for the current moment."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


def is_allowed_log_file(filename: str) -> bool:
    """Check whether a filename has an allowed log extension (.txt/.log)."""
    return Path(filename).suffix.lower() in ALLOWED_LOG_EXTENSIONS


def save_uploaded_log(file_storage, bug_id: str) -> Optional[str]:
    """
    Save an uploaded log file into uploads/, prefixed with its Bug ID to
    guarantee a unique filename. Returns the stored filename, or None if
    no file was provided.

    Raises:
        ValueError: if the file extension is not .txt or .log.
    """
    if file_storage is None or not file_storage.filename:
        return None

    original_name = secure_filename(file_storage.filename)
    if not is_allowed_log_file(original_name):
        raise ValueError("Only .txt or .log files are allowed.")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{bug_id}_{original_name}"
    file_storage.save(UPLOADS_DIR / stored_filename)
    return stored_filename


def append_bug_record(record: dict) -> None:
    """Append a single bug record (keyed by CSV_HEADERS) to bugs.csv."""
    ensure_storage_ready()
    with open(BUGS_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(record)


def read_all_bugs() -> list[dict]:
    """
    Read all stored bug records from bugs.csv, oldest first.

    Returns:
        list[dict]: one dict per bug, keyed by CSV_HEADERS. Returns an
        empty list if bugs.csv doesn't exist yet, has no rows, or can't
        currently be read (e.g. a transient I/O error) — callers such as
        duplicate detection must never crash because storage is
        temporarily unavailable.
    """
    if not BUGS_CSV_PATH.exists():
        return []

    try:
        with open(BUGS_CSV_PATH, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]
    except (OSError, csv.Error):
        return []


def create_bug_report(form_data, file_storage=None) -> dict:
    """
    Orchestrates a full bug submission: generates the Bug ID and timestamp,
    saves the uploaded log file (if any), appends the CSV row, and returns
    the full record.

    Args:
        form_data: mapping-like object (e.g. Flask's request.form) with the
            submitted field values.
        file_storage: Flask's request.files entry for the log upload, or None.

    Returns:
        dict: the full stored record, keyed by CSV_HEADERS.
    """
    with _storage_lock:
        bug_id = generate_bug_id()
        date_str, time_str = get_current_timestamp()
        log_filename = save_uploaded_log(file_storage, bug_id)

        record = {
            "Bug ID": bug_id,
            "Submission Date": date_str,
            "Submission Time": time_str,
            "Bug Title": form_data.get("bug_title", "").strip(),
            "Bug Description": form_data.get("bug_description", "").strip(),
            "Stack Trace": form_data.get("stack_trace", "").strip(),
            "Module Name": form_data.get("module_name", "").strip(),
            "Category": form_data.get("category", "").strip(),
            "Severity": form_data.get("severity", "").strip(),
            "Priority": form_data.get("priority", "").strip(),
            "Reporter Name": form_data.get("reporter_name", "").strip(),
            "Uploaded Log File Name": log_filename or "",
            "Status": DEFAULT_STATUS,
            "Actual Root Cause": "",
            "Actual Fix": "",
            "Resolution Notes": "",
            "Resolution Date": "",
        }

        append_bug_record(record)

    return record


def update_bug_resolution(
    bug_id: str,
    actual_root_cause: str,
    actual_fix: str,
    resolution_notes: str = "",
) -> Optional[dict]:
    """
    Mark a bug as Resolved and persist the developer-provided actual root
    cause, actual fix, and resolution notes back into bugs.csv, along
    with a resolution timestamp.

    This rewrites the whole CSV with the matching row updated in place —
    simple and correct at this data scale, and guarded by the same lock
    used for writes elsewhere so concurrent requests can't corrupt the file.

    Args:
        bug_id: the Bug ID to mark resolved.
        actual_root_cause: the real root cause, as determined by a developer.
        actual_fix: the real fix that was applied.
        resolution_notes: optional free-form notes about the resolution.

    Returns:
        The updated record (dict, keyed by CSV_HEADERS), or None if no
        bug with that ID exists.
    """
    with _storage_lock:
        rows = read_all_bugs()
        updated_record = None
        resolution_date, resolution_time = get_current_timestamp()

        for row in rows:
            if row.get("Bug ID") == bug_id:
                row["Status"] = STATUS_RESOLVED
                row["Actual Root Cause"] = actual_root_cause.strip()
                row["Actual Fix"] = actual_fix.strip()
                row["Resolution Notes"] = resolution_notes.strip()
                row["Resolution Date"] = f"{resolution_date} {resolution_time}"
                updated_record = row
                break

        if updated_record is None:
            return None

        ensure_storage_ready()
        with open(BUGS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(rows)

    return updated_record
