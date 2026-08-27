import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getBugs, ApiError } from "../../api/client";
import type { BugRecord } from "../../api/types";
import BugDetailModal from "./BugDetailModal";
import { SeverityBadge, StatusBadge } from "./Badges";
import "./KnowledgeBasePage.css";

type LoadState = "loading" | "loaded" | "error";

export default function KnowledgeBasePage() {
  const [searchParams] = useSearchParams();
  const [bugs, setBugs] = useState<BugRecord[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [errorMessage, setErrorMessage] = useState("");

  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const [selectedBug, setSelectedBug] = useState<BugRecord | null>(null);

  const loadBugs = async () => {
    setLoadState("loading");
    setErrorMessage("");
    try {
      const response = await getBugs();
      setBugs(response.bugs);
      setLoadState("loaded");
    } catch (err) {
      setLoadState("error");
      setErrorMessage(
        err instanceof ApiError ? err.message : "Couldn't load bug reports right now.",
      );
    }
  };

  useEffect(() => {
    loadBugs();
  }, []);

  // Deep link support: /knowledge-base?bug_id=BUG-0001 auto-opens that
  // bug's detail modal once the data has loaded.
  useEffect(() => {
    const bugId = searchParams.get("bug_id");
    if (bugId && loadState === "loaded") {
      const match = bugs.find((b) => b["Bug ID"] === bugId);
      if (match) setSelectedBug(match);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadState, bugs]);

  const filteredBugs = bugs.filter((bug) => {
    const query = searchQuery.trim().toLowerCase();
    const matchesQuery =
      !query ||
      bug["Bug ID"].toLowerCase().includes(query) ||
      bug["Bug Title"].toLowerCase().includes(query) ||
      bug["Bug Description"].toLowerCase().includes(query);

    return (
      matchesQuery &&
      (!severityFilter || bug["Severity"] === severityFilter) &&
      (!priorityFilter || bug["Priority"] === priorityFilter) &&
      (!categoryFilter || bug["Category"] === categoryFilter) &&
      (!statusFilter || bug["Status"] === statusFilter)
    );
  });

  const handleResolved = (updatedBug: BugRecord) => {
    setBugs((prev) => prev.map((b) => (b["Bug ID"] === updatedBug["Bug ID"] ? updatedBug : b)));
    setSelectedBug(updatedBug);
  };

  const categories = [...new Set(bugs.map((b) => b["Category"]).filter(Boolean))].sort();

  return (
    <section className="kb-page">
      <header className="kb-header">
        <div>
          <h1>Knowledge Base</h1>
          <p>Browse, search, and inspect previously reported bugs.</p>
        </div>
        <div className="kb-count">
          {loadState === "loaded" &&
            (filteredBugs.length === bugs.length
              ? `${bugs.length} bug${bugs.length === 1 ? "" : "s"}`
              : `${filteredBugs.length} of ${bugs.length} bugs`)}
        </div>
      </header>

      <div className="kb-controls">
        <input
          type="search"
          placeholder="Search by Bug ID, title, or description..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />

        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
          <option value="">All Severities</option>
          {["Low", "Medium", "High", "Critical"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
          <option value="">All Priorities</option>
          {["Low", "Medium", "High", "Critical"].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>

        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
          <option value="">All Categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          {["Open", "In Progress", "Resolved"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {loadState === "loading" && <p className="kb-status">Loading bug reports...</p>}
      {loadState === "error" && <p className="kb-status kb-status--error">{errorMessage}</p>}

      {loadState === "loaded" && bugs.length === 0 && (
        <div className="kb-empty">
          <h2>No bugs found</h2>
          <p>No bug reports have been submitted yet. Once bugs are submitted, they'll show up here.</p>
        </div>
      )}

      {loadState === "loaded" && bugs.length > 0 && filteredBugs.length === 0 && (
        <div className="kb-empty">
          <h2>No matching bugs</h2>
          <p>Try adjusting your search or filters.</p>
        </div>
      )}

      {loadState === "loaded" && filteredBugs.length > 0 && (
        <div className="kb-table-wrapper">
          <table className="kb-table">
            <thead>
              <tr>
                <th>Bug ID</th>
                <th>Title</th>
                <th>Status</th>
                <th>Severity</th>
                <th>Priority</th>
                <th>Category</th>
                <th>Reporter</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {filteredBugs.map((bug) => (
                <tr key={bug["Bug ID"]} onClick={() => setSelectedBug(bug)}>
                  <td className="kb-col-id">{bug["Bug ID"]}</td>
                  <td className="kb-col-title">{bug["Bug Title"]}</td>
                  <td><StatusBadge value={bug["Status"]} /></td>
                  <td><SeverityBadge value={bug["Severity"]} /></td>
                  <td><SeverityBadge value={bug["Priority"]} /></td>
                  <td>{bug["Category"]}</td>
                  <td>{bug["Reporter Name"]}</td>
                  <td>{bug["Submission Date"]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedBug && (
        <BugDetailModal
          bug={selectedBug}
          onClose={() => setSelectedBug(null)}
          onResolved={handleResolved}
        />
      )}
    </section>
  );
}
