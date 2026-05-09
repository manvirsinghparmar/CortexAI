import { get, post } from "./client";
import type { CognitoConfig, WhoAmIResponse } from "../types";

export async function fetchCognitoConfig(): Promise<CognitoConfig> {
  return get<CognitoConfig>("/v1/auth/cognito-config");
}

export async function fetchWhoAmI(): Promise<WhoAmIResponse> {
  return get<WhoAmIResponse>("/v1/whoami");
}

export async function devLogin(token?: string): Promise<{ session_id: string }> {
  return post<{ session_id: string }>("/v1/auth/dev-login", token ? { token } : {});
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
