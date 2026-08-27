import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getBugs, ApiError } from "../../api/client";
import type { BugRecord } from "../../api/types";
import "./DashboardPage.css";

type LoadState = "loading" | "loaded" | "error";

const SEVERITY_ORDER = ["Critical", "High", "Medium", "Low"];
const RECENT_BUGS_LIMIT = 5;

interface BreakdownEntry {
  label: string;
  count: number;
  widthPercent: number;
}

function computeBreakdown(
  bugs: BugRecord[],
  field: "Category" | "Severity",
  fallbackLabel: string,
  sortOrder?: string[],
): BreakdownEntry[] {
  const counts: Record<string, number> = {};
  bugs.forEach((bug) => {
    const key = bug[field] || fallbackLabel;
    counts[key] = (counts[key] || 0) + 1;
  });

  const entries = Object.entries(counts);

  const sorted = sortOrder
    ? entries.sort((a, b) => {
        const ai = sortOrder.indexOf(a[0]);
        const bi = sortOrder.indexOf(b[0]);
        if (ai === -1 && bi === -1) return b[1] - a[1];
        if (ai === -1) return 1;
        if (bi === -1) return -1;
        return ai - bi;
      })
    : entries.sort((a, b) => b[1] - a[1]);

  const totalCount = bugs.length;

  // Width represents this group's real share of ALL bugs (e.g. 1 of 5
  // bugs -> 20%), not its share relative to the largest group, so a
  // single-category dataset doesn't render every bar as misleadingly
  // full-width.
  return sorted.map(([label, count]) => ({
    label,
    count,
    widthPercent: totalCount > 0 ? Math.round((count / totalCount) * 100) : 0,
  }));
}

function bugIdNumber(bugId: string): number {
  const match = /(\d+)$/.exec(bugId || "");
  return match ? parseInt(match[1], 10) : 0;
}

function computeRecentBugs(bugs: BugRecord[]): BugRecord[] {
  // Sort by actual stored Submission Date + Time, most recent first.
  // Zero-padded "YYYY-MM-DD HH:MM:SS" strings sort correctly as text.
  // If two bugs share the same second, fall back to Bug ID sequence
  // number, which still genuinely reflects insertion order.
  const sorted = [...bugs].sort((a, b) => {
    const aTime = `${a["Submission Date"] || ""} ${a["Submission Time"] || ""}`;
    const bTime = `${b["Submission Date"] || ""} ${b["Submission Time"] || ""}`;
    const timeComparison = bTime.localeCompare(aTime);
    if (timeComparison !== 0) return timeComparison;
    return bugIdNumber(b["Bug ID"]) - bugIdNumber(a["Bug ID"]);
  });

  return sorted.slice(0, RECENT_BUGS_LIMIT);
}

function StatusPill({ value }: { value: string }) {
  if (!value) return null;
  const modifierMap: Record<string, string> = {
    Open: "status-open",
    "In Progress": "status-in-progress",
    Resolved: "status-resolved",
  };
  const modifier = modifierMap[value] || "status-open";
  return <span className={`dash-pill dash-pill--${modifier}`}>{value}</span>;
}

function SeverityPill({ value }: { value: string }) {
  if (!value) return null;
  const level = value.toLowerCase();
  const validLevels = ["low", "medium", "high", "critical"];
  const modifier = validLevels.includes(level) ? level : "default";
  return <span className={`dash-pill dash-pill--severity-${modifier}`}>{value}</span>;
}

export default function DashboardPage() {
  const [bugs, setBugs] = useState<BugRecord[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [errorMessage, setErrorMessage] = useState("");

  const loadDashboard = async () => {
    setLoadState("loading");
    setErrorMessage("");
    try {
      const response = await getBugs();
      setBugs(response.bugs);
      setLoadState("loaded");
    } catch (err) {
      setLoadState("error");
      setErrorMessage(
        err instanceof ApiError
          ? err.message
          : "Couldn't load dashboard data right now. Please refresh the page to try again.",
      );
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const total = bugs.length;
  const openCount = useMemo(() => bugs.filter((b) => b["Status"] === "Open").length, [bugs]);
  const inProgressCount = useMemo(() => bugs.filter((b) => b["Status"] === "In Progress").length, [bugs]);
  const resolvedCount = useMemo(() => bugs.filter((b) => b["Status"] === "Resolved").length, [bugs]);
  const criticalHighCount = useMemo(
    () => bugs.filter((b) => b["Severity"] === "Critical" || b["Severity"] === "High").length,
    [bugs],
  );
  const resolutionRate = total > 0 ? Math.round((resolvedCount / total) * 100) : 0;

  const categoryBreakdown = useMemo(
    () => computeBreakdown(bugs, "Category", "Uncategorized"),
    [bugs],
  );
  const severityBreakdown = useMemo(
    () => computeBreakdown(bugs, "Severity", "Unspecified", SEVERITY_ORDER),
    [bugs],
  );
  const recentBugs = useMemo(() => computeRecentBugs(bugs), [bugs]);

  return (
    <section className="dash-page">
      <header className="dash-header">
        <h1>Dashboard</h1>
        <p>An overview of submitted bugs and resolution progress.</p>
      </header>

      {loadState === "loading" && <p className="dash-status">Loading dashboard...</p>}
      {loadState === "error" && <p className="dash-status dash-status--error">{errorMessage}</p>}

      {loadState === "loaded" && total === 0 && (
        <div className="dash-empty">
          <h2>No bugs yet</h2>
          <p>Once bugs are submitted, statistics and recent activity will appear here.</p>
        </div>
      )}

      {loadState === "loaded" && total > 0 && (
        <>
          <div className="dash-stats">
            <div className="dash-stat-card">
              <span className="dash-stat-card__label">Total Bugs</span>
              <span className="dash-stat-card__value">{total}</span>
            </div>
            <div className="dash-stat-card dash-stat-card--open">
              <span className="dash-stat-card__label">Open Bugs</span>
              <span className="dash-stat-card__value">{openCount}</span>
            </div>
            <div className="dash-stat-card dash-stat-card--progress">
              <span className="dash-stat-card__label">In Progress</span>
              <span className="dash-stat-card__value">{inProgressCount}</span>
            </div>
            <div className="dash-stat-card dash-stat-card--resolved">
              <span className="dash-stat-card__label">Resolved Bugs</span>
              <span className="dash-stat-card__value">{resolvedCount}</span>
            </div>
            <div className="dash-stat-card dash-stat-card--critical">
              <span className="dash-stat-card__label">Critical / High Severity</span>
              <span className="dash-stat-card__value">{criticalHighCount}</span>
            </div>
            <div className="dash-stat-card dash-stat-card--rate">
              <span className="dash-stat-card__label">Resolution Rate</span>
              <span className="dash-stat-card__value">{resolutionRate}%</span>
            </div>
          </div>

          <div className="dash-section">
            <h2>Bugs by Category</h2>
            <ul className="dash-bar-list">
              {categoryBreakdown.map((entry) => (
                <li key={entry.label} className="dash-bar-row">
                  <span className="dash-bar-row__label">{entry.label}</span>
                  <span className="dash-bar-track">
                    <span className="dash-bar-fill" style={{ width: `${entry.widthPercent}%` }} />
                  </span>
                  <span className="dash-bar-row__count">{entry.count}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="dash-section">
            <h2>Bugs by Severity</h2>
            <ul className="dash-bar-list">
              {severityBreakdown.map((entry) => (
                <li key={entry.label} className="dash-bar-row">
                  <span className="dash-bar-row__label">{entry.label}</span>
                  <span className="dash-bar-track">
                    <span className="dash-bar-fill" style={{ width: `${entry.widthPercent}%` }} />
                  </span>
                  <span className="dash-bar-row__count">{entry.count}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="dash-section">
            <h2>Recent Bugs</h2>
            <ul className="dash-recent-list">
              {recentBugs.map((bug) => (
                <li key={bug["Bug ID"]} className="dash-recent-item">
                  <div className="dash-recent-item__main">
                    <span className="dash-recent-item__id">{bug["Bug ID"]}</span>
                    <span className="dash-recent-item__title">{bug["Bug Title"]}</span>
                  </div>
                  <div className="dash-recent-item__meta">
                    <StatusPill value={bug["Status"]} />
                    <SeverityPill value={bug["Severity"]} />
                    <span>{bug["Category"]}</span>
                    <span>{bug["Submission Date"]}</span>
                  </div>
                  <Link
                    className="dash-recent-item__link"
                    to={`/knowledge-base?bug_id=${encodeURIComponent(bug["Bug ID"])}`}
                  >
                    View Details
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </section>
  );
}
