import { post } from "./client";
import type { OptimizeRequest, OptimizeResponse } from "../types";

export async function optimizePrompt(
  request: OptimizeRequest,
  signal?: AbortSignal,
): Promise<OptimizeResponse> {
  return post<OptimizeResponse>("/v1/optimize", request, signal);
}
