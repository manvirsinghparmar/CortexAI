import { post } from "./client";
import type { CompareRequest, CompareResponse } from "../types";

export async function sendCompare(request: CompareRequest): Promise<CompareResponse> {
  return post<CompareResponse>("/v1/compare", request);
}
