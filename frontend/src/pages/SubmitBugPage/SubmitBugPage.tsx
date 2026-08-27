import { useState, useRef } from "react";
import type { FormEvent } from "react";
import { submitBug, ApiError } from "../../api/client";
import type { SubmitBugFields } from "../../api/types";
import "./SubmitBugPage.css";

const CATEGORY_OPTIONS = [
  "Backend", "Frontend", "Database", "Authentication", "API",
  "UI", "Performance", "Security", "Network", "Other",
];
const SEVERITY_PRIORITY_OPTIONS = ["Low", "Medium", "High", "Critical"];
const ALLOWED_LOG_EXTENSIONS = [".txt", ".log"];

const EMPTY_FIELDS: SubmitBugFields = {
  bug_title: "",
  bug_description: "",
  stack_trace: "",
  module_name: "",
  category: "",
  severity: "",
  priority: "",
  reporter_name: "",
};

type Status = "idle" | "submitting" | "success" | "error";

interface SuccessInfo {
  bugId: string;
  date: string;
  time: string;
}

export default function SubmitBugPage() {
  const [fields, setFields] = useState<SubmitBugFields>(EMPTY_FIELDS);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [successInfo, setSuccessInfo] = useState<SuccessInfo | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const updateField = (key: keyof SubmitBugFields, value: string) => {
    setFields((prev) => ({ ...prev, [key]: value }));
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    (Object.keys(EMPTY_FIELDS) as (keyof SubmitBugFields)[]).forEach((key) => {
      if (!fields[key].trim()) {
        errors[key] = "This field is required.";
      }
    });

    const file = fileInputRef.current?.files?.[0];
    if (file) {
      const hasValidExtension = ALLOWED_LOG_EXTENSIONS.some((ext) =>
        file.name.toLowerCase().endsWith(ext),
      );
      if (!hasValidExtension) {
        errors.log_file = "Only .txt or .log files are allowed.";
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setErrorMessage("");

    if (!validate()) {
      setErrorMessage("Please fix the highlighted fields before submitting.");
      return;
    }

    setStatus("submitting");
    try {
      const file = fileInputRef.current?.files?.[0] ?? null;
      const response = await submitBug(fields, file);

      if (response.status !== "success" || !response.bug_id) {
        setStatus("error");
        setErrorMessage(response.message || "Something went wrong while submitting the bug.");
        return;
      }

      setSuccessInfo({
        bugId: response.bug_id,
        date: response.submission_date || "",
        time: response.submission_time || "",
      });
      setStatus("success");
      setFields(EMPTY_FIELDS);
      setFieldErrors({});
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setStatus("error");
      setErrorMessage(
        err instanceof ApiError ? err.message : "Something went wrong while submitting the bug.",
      );
    }
  };

  const handleSubmitAnother = () => {
    setStatus("idle");
    setSuccessInfo(null);
    setErrorMessage("");
  };

  if (status === "success" && successInfo) {
    return (
      <section className="submit-page">
        <div className="submit-card submit-card--success">
          <div className="submit-success-icon">&#10003;</div>
          <h2>Bug submitted successfully.</h2>
          <dl className="kv-grid">
            <div><dt>Bug ID</dt><dd>{successInfo.bugId}</dd></div>
            <div><dt>Submitted At</dt><dd>{successInfo.date} {successInfo.time}</dd></div>
          </dl>
          <button type="button" onClick={handleSubmitAnother}>Submit Another Bug</button>
        </div>
      </section>
    );
  }

  return (
    <section className="submit-page">
      <div className="submit-card">
        <h1>Submit a Bug</h1>
        <p>Provide as much detail as possible.</p>

        {errorMessage && <p className="submit-message submit-message--error">{errorMessage}</p>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="bug_title">Bug Title *</label>
            <input
              id="bug_title"
              type="text"
              value={fields.bug_title}
              onChange={(e) => updateField("bug_title", e.target.value)}
            />
            {fieldErrors.bug_title && <span className="field-error">{fieldErrors.bug_title}</span>}
          </div>

          <div className="form-field">
            <label htmlFor="bug_description">Bug Description *</label>
            <textarea
              id="bug_description"
              rows={4}
              value={fields.bug_description}
              onChange={(e) => updateField("bug_description", e.target.value)}
            />
            {fieldErrors.bug_description && <span className="field-error">{fieldErrors.bug_description}</span>}
          </div>

          <div className="form-field">
            <label htmlFor="stack_trace">Stack Trace / Error Log *</label>
            <textarea
              id="stack_trace"
              rows={5}
              className="monospace"
              value={fields.stack_trace}
              onChange={(e) => updateField("stack_trace", e.target.value)}
            />
            {fieldErrors.stack_trace && <span className="field-error">{fieldErrors.stack_trace}</span>}
          </div>

          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="module_name">Module Name *</label>
              <input
                id="module_name"
                type="text"
                value={fields.module_name}
                onChange={(e) => updateField("module_name", e.target.value)}
              />
              {fieldErrors.module_name && <span className="field-error">{fieldErrors.module_name}</span>}
            </div>

            <div className="form-field">
              <label htmlFor="category">Category *</label>
              <select
                id="category"
                value={fields.category}
                onChange={(e) => updateField("category", e.target.value)}
              >
                <option value="" disabled>Select a category</option>
                {CATEGORY_OPTIONS.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
              </select>
              {fieldErrors.category && <span className="field-error">{fieldErrors.category}</span>}
            </div>

            <div className="form-field">
              <label htmlFor="severity">Severity *</label>
              <select
                id="severity"
                value={fields.severity}
                onChange={(e) => updateField("severity", e.target.value)}
              >
                <option value="" disabled>Select severity</option>
                {SEVERITY_PRIORITY_OPTIONS.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
              </select>
              {fieldErrors.severity && <span className="field-error">{fieldErrors.severity}</span>}
            </div>

            <div className="form-field">
              <label htmlFor="priority">Priority *</label>
              <select
                id="priority"
                value={fields.priority}
                onChange={(e) => updateField("priority", e.target.value)}
              >
                <option value="" disabled>Select priority</option>
                {SEVERITY_PRIORITY_OPTIONS.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
              </select>
              {fieldErrors.priority && <span className="field-error">{fieldErrors.priority}</span>}
            </div>

            <div className="form-field">
              <label htmlFor="reporter_name">Reporter Name *</label>
              <input
                id="reporter_name"
                type="text"
                value={fields.reporter_name}
                onChange={(e) => updateField("reporter_name", e.target.value)}
              />
              {fieldErrors.reporter_name && <span className="field-error">{fieldErrors.reporter_name}</span>}
            </div>

            <div className="form-field">
              <label htmlFor="log_file">Upload Log File (.txt or .log)</label>
              <input id="log_file" type="file" accept=".txt,.log" ref={fileInputRef} />
              {fieldErrors.log_file && <span className="field-error">{fieldErrors.log_file}</span>}
            </div>
          </div>

          <div className="submit-actions">
            <button type="submit" disabled={status === "submitting"}>
              {status === "submitting" ? "Submitting..." : "Submit Bug"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
