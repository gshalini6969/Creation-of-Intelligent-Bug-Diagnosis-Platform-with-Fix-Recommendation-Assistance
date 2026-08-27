import { useState } from "react";
import type { FormEvent } from "react";
import { resolveBug, ApiError } from "../../api/client";
import type { BugRecord } from "../../api/types";
import { SeverityBadge, StatusBadge } from "./Badges";

interface BugDetailModalProps {
  bug: BugRecord;
  onClose: () => void;
  onResolved: (updatedBug: BugRecord) => void;
}

export default function BugDetailModal({ bug, onClose, onResolved }: BugDetailModalProps) {
  const [showResolveForm, setShowResolveForm] = useState(false);
  const [actualRootCause, setActualRootCause] = useState("");
  const [actualFix, setActualFix] = useState("");
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const isResolved = bug["Status"] === "Resolved";

  const handleResolveSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError("");

    if (!actualRootCause.trim() || !actualFix.trim()) {
      setFormError("Actual Root Cause and Actual Fix are both required.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await resolveBug(bug["Bug ID"], actualRootCause, actualFix, resolutionNotes);
      if (response.status !== "success" || !response.bug) {
        setFormError(response.message || "Something went wrong. Please try again.");
        return;
      }
      onResolved(response.bug);
      setShowResolveForm(false);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="kb-modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="kb-modal" role="dialog" aria-modal="true">
        <button type="button" className="kb-modal-close" onClick={onClose} aria-label="Close">
          &times;
        </button>

        <header className="kb-modal-header">
          <div>
            <span className="kb-modal-id">{bug["Bug ID"]}</span>
            <h2>{bug["Bug Title"]}</h2>
          </div>
          <div className="kb-modal-badges">
            <StatusBadge value={bug["Status"]} />
            <SeverityBadge value={bug["Severity"]} />
            <SeverityBadge value={bug["Priority"]} />
          </div>
        </header>

        <dl className="kb-modal-meta">
          <div><dt>Reporter</dt><dd>{bug["Reporter Name"] || "—"}</dd></div>
          <div><dt>Module</dt><dd>{bug["Module Name"] || "—"}</dd></div>
          <div><dt>Category</dt><dd>{bug["Category"] || "—"}</dd></div>
          <div><dt>Date &amp; Time</dt><dd>{[bug["Submission Date"], bug["Submission Time"]].filter(Boolean).join(" ") || "—"}</dd></div>
          <div><dt>Log File</dt><dd>{bug["Uploaded Log File Name"] || "None"}</dd></div>
        </dl>

        <div className="kb-modal-section">
          <h3>Description</h3>
          <p>{bug["Bug Description"] || "—"}</p>
        </div>

        <div className="kb-modal-section">
          <h3>Stack Trace / Error Log</h3>
          <pre>{bug["Stack Trace"] || "—"}</pre>
        </div>

        {isResolved && (
          <div className="kb-modal-section">
            <h3>Resolution Details</h3>
            <p><strong>Resolved On:</strong> {bug["Resolution Date"] || "—"}</p>
            <p><strong>Actual Root Cause:</strong> {bug["Actual Root Cause"] || "—"}</p>
            <p><strong>Actual Fix Applied:</strong> {bug["Actual Fix"] || "—"}</p>
            {bug["Resolution Notes"] && (
              <p><strong>Resolution Notes:</strong> {bug["Resolution Notes"]}</p>
            )}
          </div>
        )}

        {!isResolved && !showResolveForm && (
          <div className="kb-resolve-action">
            <button type="button" onClick={() => setShowResolveForm(true)}>
              Mark as Resolved
            </button>
          </div>
        )}

        {!isResolved && showResolveForm && (
          <form className="kb-resolve-form" onSubmit={handleResolveSubmit}>
            <h3>Mark as Resolved</h3>

            <div className="form-field">
              <label htmlFor="actual_root_cause">Actual Root Cause *</label>
              <textarea
                id="actual_root_cause"
                rows={3}
                value={actualRootCause}
                onChange={(e) => setActualRootCause(e.target.value)}
              />
            </div>

            <div className="form-field">
              <label htmlFor="actual_fix">Actual Fix Applied *</label>
              <textarea
                id="actual_fix"
                rows={3}
                value={actualFix}
                onChange={(e) => setActualFix(e.target.value)}
              />
            </div>

            <div className="form-field">
              <label htmlFor="resolution_notes">Resolution Notes (optional)</label>
              <textarea
                id="resolution_notes"
                rows={2}
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
              />
            </div>

            {formError && <p className="kb-resolve-status kb-resolve-status--error">{formError}</p>}

            <div className="kb-resolve-form__actions">
              <button type="button" className="secondary" onClick={() => setShowResolveForm(false)}>
                Cancel
              </button>
              <button type="submit" disabled={submitting}>
                {submitting ? "Saving..." : "Save Resolution"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
