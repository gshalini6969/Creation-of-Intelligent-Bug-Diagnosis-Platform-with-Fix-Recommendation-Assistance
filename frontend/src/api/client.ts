// Thin API layer for the FastAPI backend.
//
// This is the only module in the app that should call fetch() directly —
// every page imports functions from here instead of duplicating request
// logic. Requests go to relative /api/... paths; in development, Vite's
// dev-server proxy (see vite.config.ts) forwards them to the FastAPI
// backend at http://127.0.0.1:8000, so no CORS handling is needed on
// the client side even though the backend also sends permissive CORS
// headers as a fallback.

import type {
  AnalyzeResponse,
  GetBugsResponse,
  ParseLogResponse,
  ResolveBugResponse,
  SubmitBugFields,
  SubmitBugResponse,
} from "./types";

const API_BASE = "/api";

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      // Let the browser set the multipart Content-Type (with boundary)
      // itself when sending FormData — setting it manually breaks upload parsing.
      headers: isFormData ? undefined : { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError(
      "Could not reach the backend. Is the FastAPI server running on http://127.0.0.1:8000?",
      0,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(`Server returned an unreadable response (status ${response.status}).`, response.status);
  }

  // 4xx/5xx are not necessarily failures at the application level (e.g.
  // 422 "invalid_input" is an expected, handleable outcome) — callers
  // that need that distinction should inspect the returned body's
  // `status` field themselves rather than relying on response.ok here.
  return payload as T;
}

/**
 * POST /api/bugs — submits a new bug report as multipart/form-data
 * (required for the optional log file upload). Returns the generated
 * Bug ID on success, or an error/missing_fields payload otherwise.
 */
export async function submitBug(
  fields: SubmitBugFields,
  logFile: File | null,
): Promise<SubmitBugResponse> {
  const formData = new FormData();
  Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
  if (logFile) {
    formData.append("log_file", logFile);
  }

  return request<SubmitBugResponse>("/bugs", {
    method: "POST",
    body: formData,
  });
}

/** GET /api/bugs — all stored historical bugs (Knowledge Base data source). */
export async function getBugs(): Promise<GetBugsResponse> {
  return request<GetBugsResponse>("/bugs", { method: "GET" });
}

/** POST /api/parse-log — runs the Log Parsing Agent only. */
export async function parseLog(rawText: string): Promise<ParseLogResponse> {
  return request<ParseLogResponse>("/parse-log", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText }),
  });
}

/**
 * POST /api/analyze — runs Triage, Root Cause, Duplicate Detection, and
 * Fix Recommendation. Returns either a full AnalyzeResult (status:
 * "success") or an AnalyzeInvalidResponse (status: "error" | "invalid_input")
 * — check `status` (see isAnalyzeSuccess in ./types) before reading
 * `analysis`/`similar_bugs`/`recommendation`.
 */
export async function analyzeBug(rawText: string): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/analyze", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText }),
  });
}

/** POST /api/bugs/{bugId}/resolve — marks a historical bug Resolved. */
export async function resolveBug(
  bugId: string,
  actualRootCause: string,
  actualFix: string,
  resolutionNotes = "",
): Promise<ResolveBugResponse> {
  return request<ResolveBugResponse>(`/bugs/${encodeURIComponent(bugId)}/resolve`, {
    method: "POST",
    body: JSON.stringify({
      actual_root_cause: actualRootCause,
      actual_fix: actualFix,
      resolution_notes: resolutionNotes,
    }),
  });
}

export { ApiError };
