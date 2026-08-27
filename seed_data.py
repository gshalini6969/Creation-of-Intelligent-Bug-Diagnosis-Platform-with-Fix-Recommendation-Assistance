"""
Knowledge Base seed script — seed_data.py

Populates data/bugs.csv with a small, realistic set of historical bugs
so the Duplicate Detection Agent and Knowledge Base have real data to
work with out of the box, instead of an empty repository that makes
every analysis return "No similar historical bugs found."

This does NOT introduce a separate data system — it reuses the exact
same storage functions the rest of the app already uses
(utils.bug_storage.create_bug_report / update_bug_resolution), so
every seeded bug is a normal row in data/bugs.csv, indistinguishable
from a bug submitted through the Submit Bug page, and fully visible in
the Knowledge Base, Dashboard, and Duplicate Detection.

Usage:
    python seed_data.py            # skips seeding if bugs already exist
    python seed_data.py --force    # seeds additional bugs regardless
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils.bug_storage import create_bug_report, read_all_bugs, update_bug_resolution  # noqa: E402

SEED_BUGS = [
    {
        "form": {
            "bug_title": "Login fails with NullPointerException in LoginService",
            "bug_description": (
                "Users report that login intermittently fails. Authentication crashes "
                "while validating the user object — the session/user object appears to "
                "be null at the point of validation, not an invalid password."
            ),
            "stack_trace": (
                "java.lang.NullPointerException: Cannot invoke \"User.getId()\" because "
                "\"user\" is null\n\tat com.example.auth.LoginService.validateUser("
                "LoginService.java:47)\n\tat com.example.auth.LoginService.login("
                "LoginService.java:22)"
            ),
            "module_name": "auth-service",
            "category": "Authentication",
            "severity": "High",
            "priority": "High",
            "reporter_name": "Priya Nair",
        },
        "resolve": {
            "actual_root_cause": (
                "The session object was not initialized before LoginService.validateUser() "
                "read it — a race condition on first login after a service restart."
            ),
            "actual_fix": (
                "Added a null check with a clear error before use, and fixed session "
                "initialization order in LoginService so the session object is guaranteed "
                "to exist before validateUser() runs."
            ),
            "resolution_notes": "Verified with load test simulating cold-start logins.",
        },
    },
    {
        "form": {
            "bug_title": "MySQL connection refused under peak load",
            "bug_description": (
                "Application cannot connect to the database during peak traffic hours. "
                "MySQL connection refused, and requests eventually time out."
            ),
            "stack_trace": (
                "com.mysql.cj.jdbc.exceptions.CommunicationsException: Communications link "
                "failure\nCaused by: java.net.ConnectException: Connection refused\n\tat "
                "com.example.db.ConnectionPool.getConnection(ConnectionPool.java:33)"
            ),
            "module_name": "db-service",
            "category": "Database",
            "severity": "Critical",
            "priority": "Critical",
            "reporter_name": "Miguel Torres",
        },
        "resolve": None,  # left Open — realistic mix of resolved/unresolved history
    },
    {
        "form": {
            "bug_title": "ArrayIndexOutOfBoundsException while processing uploaded images",
            "bug_description": (
                "The application crashes while processing an image because an array index "
                "is outside the valid range. Happens only for images with unusual aspect "
                "ratios."
            ),
            "stack_trace": (
                "java.lang.ArrayIndexOutOfBoundsException: Index 512 out of bounds for "
                "length 512\n\tat com.example.media.ImageProcessor.resize("
                "ImageProcessor.java:88)"
            ),
            "module_name": "media-service",
            "category": "Backend",
            "severity": "Medium",
            "priority": "Medium",
            "reporter_name": "Wei Zhang",
        },
        "resolve": None,
    },
    {
        "form": {
            "bug_title": "Submit button unresponsive on Safari mobile",
            "bug_description": (
                "The submit button on the bug report form does not respond to taps on "
                "Safari for iOS. Works correctly on Chrome and Firefox."
            ),
            "stack_trace": "TypeError: undefined is not a function (near '...form.submit...')",
            "module_name": "frontend-web",
            "category": "UI",
            "severity": "Medium",
            "priority": "Low",
            "reporter_name": "Sofia Rossi",
        },
        "resolve": {
            "actual_root_cause": (
                "A CSS pointer-events rule was unintentionally applied to the button's "
                "parent element on narrow viewports, which Safari treats differently."
            ),
            "actual_fix": "Removed the conflicting rule and added a mobile-specific test.",
            "resolution_notes": "",
        },
    },
    {
        "form": {
            "bug_title": "Dashboard takes over 8 seconds to load under normal traffic",
            "bug_description": (
                "The dashboard page is noticeably slow to load, even outside peak hours. "
                "Users report waiting several seconds before stats appear."
            ),
            "stack_trace": "",
            "module_name": "dashboard-service",
            "category": "Performance",
            "severity": "Medium",
            "priority": "Medium",
            "reporter_name": "James Okafor",
        },
        "resolve": None,
    },
]


def seed(force: bool = False) -> None:
    existing = read_all_bugs()
    if existing and not force:
        print(
            f"data/bugs.csv already has {len(existing)} bug(s). "
            "Skipping seed (pass --force to add the seed bugs anyway)."
        )
        return

    created = []
    for entry in SEED_BUGS:
        record = create_bug_report(entry["form"])
        created.append(record["Bug ID"])

        if entry["resolve"]:
            update_bug_resolution(
                record["Bug ID"],
                entry["resolve"]["actual_root_cause"],
                entry["resolve"]["actual_fix"],
                entry["resolve"].get("resolution_notes", ""),
            )

    print(f"Seeded {len(created)} historical bugs: {', '.join(created)}")


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
