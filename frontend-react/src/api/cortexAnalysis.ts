import { get, post } from "./client";
import type { CortexAnalysisRun } from "../types";

export async function createCortexAnalysis(
  requestGroupId: string,
  signal?: AbortSignal,
): Promise<CortexAnalysisRun> {
  return post<CortexAnalysisRun>(
    `/v1/compare/${encodeURIComponent(requestGroupId)}/analysis`,
    {},
    signal,
  );
}

export async function fetchCortexAnalysisRuns(
  options: { sessionId?: string; requestGroupId?: string },
  signal?: AbortSignal,
): Promise<CortexAnalysisRun[]> {
  const params = new URLSearchParams();
  if (options.sessionId) params.set("session_id", options.sessionId);
  if (options.requestGroupId) params.set("request_group_id", options.requestGroupId);
  return get<CortexAnalysisRun[]>(`/v1/compare/analysis-runs?${params.toString()}`, signal);
}
