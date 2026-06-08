import { get } from "./client";
import type { CognitoConfig, WhoAmIResponse } from "../types";

export async function fetchCognitoConfig(): Promise<CognitoConfig> {
  return get<CognitoConfig>("/v1/auth/cognito-config");
}

export async function fetchWhoAmI(): Promise<WhoAmIResponse> {
  return get<WhoAmIResponse>("/v1/whoami");
}

export async function devLogin(token?: string): Promise<{ session_id: string }> {
  const headers: Record<string, string> = {};
  if (token) headers["X-Dev-Login-Token"] = token;
  const res = await fetch("/v1/auth/dev-login", {
    method: "POST",
    credentials: "include",
    headers,
  });
  if (!res.ok) throw new Error(res.statusText || "Dev login failed");
  return res.json() as Promise<{ session_id: string }>;
}

export function buildCognitoLoginUrl(config: CognitoConfig): string {
  if (!config.enabled || !config.domain || !config.client_id || !config.redirect_uri) {
    throw new Error("Cognito is not fully configured");
  }
  const params = new URLSearchParams({
    response_type: "code",
    client_id: config.client_id,
    redirect_uri: config.redirect_uri,
    scope: "openid email profile",
  });
  return `${config.domain}/oauth2/authorize?${params.toString()}`;
}
