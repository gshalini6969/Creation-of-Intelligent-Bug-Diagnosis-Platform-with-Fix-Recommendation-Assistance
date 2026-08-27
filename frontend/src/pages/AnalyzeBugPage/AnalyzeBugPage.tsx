import { useState } from "react";
import { analyzeBug, parseLog, ApiError } from "../../api/client";
import { isAnalyzeSuccess } from "../../api/types";
import type { AnalyzeResult, ParsedLogInfo } from "../../api/types";
import "./AnalyzeBugPage.css";

type Status = "idle" | "loading" | "success" | "invalid" | "error";

const PIPELINE_STEPS = [
  { key: "parsing", label: "Log Parsing" },
  { key: "triage", label: "Triage" },
  { key: "root-cause", label: "Root Cause" },
  { key: "retrieval", label: "Duplicate Detection / RAG" },
  { key: "recommendation", label: "Fix Recommendation" },
];

const SEVERITY_BADGE: Record<string, string> = {
  Low: "badge-severity-low",
  Medium: "badge-severity-medium",
  High: "badge-severity-high",
  Critical: "badge-severity-critical",
};

const STATUS_BADGE: Record<string, string> = {
  Open: "badge-neutral",
  "In Progress": "badge-warning",
  Resolved: "badge-success",
};

function SeverityBadge({ value }: { value: string }) {
  if (!value) return null;
  return <span className={`badge ${SEVERITY_BADGE[value] || "badge-neutral"}`}>{value}</span>;
}

function StatusBadge({ value }: { value: string }) {
  if (!value) return null;
  return <span className={`badge ${STATUS_BADGE[value] || "badge-neutral"}`}>{value}</span>;
}

export default function AnalyzeBugPage() {
  const [rawText, setRawText] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [parsed, setParsed] = useState<ParsedLogInfo | null>(null);
  const [result, setResult] = useState<AnalyzeResult | null>(null);

  const handleAnalyze = async () => {
    const trimmed = rawText.trim();
    if (!trimmed) {
      setStatus("error");
      setMessage("Please paste a bug report, error log, or stack trace before analyzing.");
      return;
    }

    setStatus("loading");
    setMessage("");
    setParsed(null);
    setResult(null);

    try {
      const [parseLogResponse, analyzeResponse] = await Promise.all([
        parseLog(trimmed),
        analyzeBug(trimmed),
      ]);

      if (!isAnalyzeSuccess(analyzeResponse)) {
        setStatus(analyzeResponse.status === "invalid_input" ? "invalid" : "error");
        setMessage(analyzeResponse.message);
        return;
      }

      if (parseLogResponse.status === "success" && parseLogResponse.parsed) {
        setParsed(parseLogResponse.parsed);
      }

      setResult(analyzeResponse);
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setMessage(
        err instanceof ApiError
          ? err.message
          : "Something went wrong while analyzing. Please try again.",
      );
    }
  };

  const pipelineState: "pending" | "active" | "done" =
    status === "loading" ? "active" : status === "success" ? "done" : "pending";

  return (
    <section className="analyze-page">
      <header className="page-header">
        <h1 className="page-title">Analyze Bug</h1>
        <p className="page-subtitle">
          Paste a bug report, error log, or stack trace to run it through the full diagnosis pipeline.
        </p>
      </header>

      <div className="card analyze-input-card">
        <textarea
          className="analyze-textarea mono"
          rows={10}
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="Paste your raw bug report, error log, or stack trace here..."
        />

        <div className="analyze-actions">
          <button
            type="button"
            className="btn btn-primary btn-lg"
            onClick={handleAnalyze}
            disabled={status === "loading"}
          >
            {status === "loading" ? "Analyzing…" : "Analyze"}
          </button>
        </div>

        {status === "error" && <p className="analyze-message analyze-message--error">{message}</p>}
        {status === "invalid" && (
          <p className="analyze-message analyze-message--warning">
            <strong>Insufficient Information</strong>
            <br />
            {message}
          </p>
        )}
      </div>

      <ol className="pipeline-stepper" aria-label="Analysis pipeline">
        {PIPELINE_STEPS.map((step, index) => (
          <li key={step.key} className={`pipeline-step pipeline-step--${pipelineState}`}>
            <span className="pipeline-step__marker">
              {pipelineState === "done" ? "✓" : index + 1}
            </span>
            <span className="pipeline-step__label">{step.label}</span>
          </li>
        ))}
      </ol>

      {status === "success" && result && (
        <>
          <div className="analyze-zone analyze-zone--ai">
            <h2 className="analyze-zone__title">
              <span className="analyze-zone__dot analyze-zone__dot--ai" />
              AI Diagnosis
            </h2>

            {parsed && (
              <div className="card">
                <h3>Parsed Bug Information</h3>
                <dl className="kv-grid">
                  <div><dt>Exception Type</dt><dd>{parsed.exception_type}</dd></div>
                  <div><dt>Programming Language</dt><dd>{parsed.programming_language}</dd></div>
                  <div><dt>File Name</dt><dd className="mono">{parsed.file_name}</dd></div>
                  <div><dt>Method Name</dt><dd className="mono">{parsed.method_name}</dd></div>
                  <div><dt>Line Number</dt><dd>{parsed.line_number}</dd></div>
                  <div className="kv-grid__wide"><dt>Error Message</dt><dd className="mono">{parsed.error_message}</dd></div>
                </dl>
              </div>
            )}

            <div className="card">
              <h3>Rule-based Diagnosis</h3>
              <div className="diagnosis-summary">
                <div className="diagnosis-summary__badges">
                  <span className="badge badge-info">{result.analysis.category}</span>
                  <SeverityBadge value={result.analysis.severity} />
                  <span className="badge badge-neutral">Priority: {result.analysis.priority}</span>
                  <span className="badge badge-neutral">{result.analysis.confidence}% confidence</span>
                </div>
                <p className="diagnosis-summary__root-cause">{result.analysis.root_cause}</p>
              </div>
            </div>
          </div>

          <div className="analyze-zone analyze-zone--evidence">
            <h2 className="analyze-zone__title">
              <span className="analyze-zone__dot analyze-zone__dot--evidence" />
              Historical Evidence
            </h2>

            <div className="card">
              <h3>Similar Historical Bugs</h3>
              <p className="card-hint">Duplicate detection via TF-IDF text similarity over stored bug reports.</p>
              {result.similar_bugs.length === 0 ? (
                <p className="text-muted">No similar historical bugs found.</p>
              ) : (
                <ul className="evidence-list">
                  {result.similar_bugs.map((bug) => (
                    <li key={bug.bug_id} className="evidence-item">
                      <div className="evidence-item__top">
                        <span className="evidence-item__id">{bug.bug_id}</span>
                        <span className="evidence-item__score">{bug.similarity_percentage}% match</span>
                        <StatusBadge value={bug.status} />
                      </div>
                      <div className="evidence-item__title">{bug.title}</div>
                      <div className="evidence-item__meta">
                        <SeverityBadge value={bug.severity} />
                        <span>{bug.category}</span>
                        <span>{bug.reporter}</span>
                        <span>{bug.submission_date}</span>
                      </div>
                      {bug.previous_fix && (
                        <div className="evidence-item__fix">
                          <strong>Previously fixed by:</strong> {bug.previous_fix}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="card">
              <h3>Retrieved Historical Knowledge</h3>
              <p className="card-hint">
                Retrieved by semantic similarity search (RAG) over historical bug titles, descriptions, stack traces, and resolutions.
              </p>
              {result.rag_results.length === 0 ? (
                <p className="text-muted">No relevant historical knowledge retrieved.</p>
              ) : (
                <ul className="evidence-list">
                  {result.rag_results.map((bug) => (
                    <li key={bug.bug_id} className="evidence-item">
                      <div className="evidence-item__top">
                        <span className="evidence-item__id">{bug.bug_id}</span>
                        <span className="evidence-item__score">{(bug.similarity * 100).toFixed(1)}% similarity</span>
                        <StatusBadge value={bug.status} />
                      </div>
                      <div className="evidence-item__title">{bug.title}</div>
                      {bug.root_cause && (
                        <div className="evidence-item__fix">
                          <strong>Historical root cause:</strong> {bug.root_cause}
                        </div>
                      )}
                      {bug.fix && (
                        <div className="evidence-item__fix">
                          <strong>Historical fix:</strong> {bug.fix}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="card fix-card">
            <h2 className="fix-card__title">Recommended Fix</h2>
            <p className="fix-card__resolution">{result.recommendation.recommended_resolution}</p>

            <div className="fix-card__grid">
              <div className="fix-card__section">
                <h3>Immediate Actions</h3>
                <ul>{result.recommendation.immediate_actions.map((a) => <li key={a}>{a}</li>)}</ul>
              </div>
              <div className="fix-card__section">
                <h3>Investigation Steps</h3>
                <ul>{result.recommendation.investigation_steps.map((s) => <li key={s}>{s}</li>)}</ul>
              </div>
              <div className="fix-card__section">
                <h3>Files/Modules to Inspect</h3>
                <ul>{result.recommendation.files_modules_to_inspect.map((f) => <li key={f}>{f}</li>)}</ul>
              </div>
              <div className="fix-card__section">
                <h3>Possible Risks</h3>
                <ul>{result.recommendation.possible_risks.map((r) => <li key={r}>{r}</li>)}</ul>
              </div>
              <div className="fix-card__section fix-card__section--wide">
                <h3>Prevention Tips</h3>
                <ul>{result.recommendation.prevention_tips.map((t) => <li key={t}>{t}</li>)}</ul>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
