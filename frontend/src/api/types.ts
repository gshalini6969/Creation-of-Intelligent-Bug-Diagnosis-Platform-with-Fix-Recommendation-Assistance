// Types mirroring the FastAPI backend's actual response shapes
// (backend/app/schemas/*.py and the ai/ modules' return values).
// Keep these in sync with the backend by hand — there's no shared
// schema generation yet in this phase of the migration.

/** A stored bug record — keys match data/bugs.csv column headers exactly. */
export interface BugRecord {
  "Bug ID": string;
  "Submission Date": string;
  "Submission Time": string;
  "Bug Title": string;
  "Bug Description": string;
  "Stack Trace": string;
  "Module Name": string;
  "Category": string;
  "Severity": string;
  "Priority": string;
  "Reporter Name": string;
  "Uploaded Log File Name": string;
  "Status": string;
  "Actual Root Cause": string;
  "Actual Fix": string;
  "Resolution Notes": string;
  "Resolution Date": string;
}

export interface GetBugsResponse {
  status: string;
  count: number;
  bugs: BugRecord[];
}

/** Output of the Log Parsing Agent. */
export interface ParsedLogInfo {
  exception_type: string;
  programming_language: string;
  file_name: string;
  method_name: string;
  line_number: string;
  error_message: string;
}

export interface ParseLogResponse {
  status: "success" | "error";
  parsed?: ParsedLogInfo;
  message?: string;
}

/** Output of the Triage + Root Cause Agent (rule_analyzer.analyze_bug_text). */
export interface RuleAnalysis {
  category: string;
  severity: string;
  priority: string;
  root_cause: string;
  suggested_fix: string;
  confidence: number;
  matched_keywords: string[];
}

/** One entry from the Duplicate Detection Agent. */
export interface SimilarBug {
  bug_id: string;
  title: string;
  similarity_percentage: number;
  severity: string;
  category: string;
  reporter: string;
  submission_date: string;
  status: string;
  matched_concepts: string[];
  previous_root_cause: string;
  previous_fix: string;
}

/** One entry from POST /api/rag/retrieve (and the rag_results field on /api/analyze). */
export interface RagResult {
  bug_id: string;
  title: string;
  category: string;
  severity: string;
  priority: string;
  status: string;
  root_cause: string;
  fix: string;
  resolution_notes: string;
  similarity: number;
}

/** Output of the Fix Recommendation Agent. */
export interface Recommendation {
  recommended_resolution: string;
  immediate_actions: string[];
  investigation_steps: string[];
  files_modules_to_inspect: string[];
  possible_risks: string[];
  prevention_tips: string[];
  resolved_bugs_considered: number;
}

/** Successful POST /api/analyze response. */
export interface AnalyzeResult {
  status: "success";
  analysis: RuleAnalysis;
  similar_bugs: SimilarBug[];
  recommendation: Recommendation;
  rag_results: RagResult[];
  rag_context: string;
}

/** POST /api/analyze when the input was empty or failed validation. */
export interface AnalyzeInvalidResponse {
  status: "error" | "invalid_input";
  message: string;
}

export type AnalyzeResponse = AnalyzeResult | AnalyzeInvalidResponse;

export function isAnalyzeSuccess(
  response: AnalyzeResponse,
): response is AnalyzeResult {
  return response.status === "success";
}

export interface SubmitBugFields {
  bug_title: string;
  bug_description: string;
  stack_trace: string;
  module_name: string;
  category: string;
  severity: string;
  priority: string;
  reporter_name: string;
}

export interface SubmitBugResponse {
  status: "success" | "error";
  message?: string;
  bug_id?: string;
  submission_date?: string;
  submission_time?: string;
  missing_fields?: string[];
}

export interface ResolveBugResponse {
  status: string;
  message?: string;
  bug?: BugRecord;
}
