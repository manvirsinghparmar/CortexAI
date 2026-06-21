import { describe, expect, it } from "vitest";
import {
  buildCognitoLoginUrl,
  buildCognitoLogoutUrl,
  cognitoClientId,
  cognitoRedirectUri,
} from "../api/auth";
import type { CognitoConfig } from "../types";

describe("auth helpers", () => {
  it("accepts backend camelCase Cognito config fields", () => {
    const config: CognitoConfig = {
      enabled: true,
      clientId: "client-123",
      domain: "https://auth.example.com",
      redirectUri: "https://app.example.com/auth",
      logoutUrl: "https://auth.example.com/logout?client_id=client-123",
    };

    expect(cognitoClientId(config)).toBe("client-123");
    expect(cognitoRedirectUri(config)).toBe("https://app.example.com/auth");

    const loginUrl = new URL(buildCognitoLoginUrl(config));
    expect(loginUrl.origin).toBe("https://auth.example.com");
    expect(loginUrl.pathname).toBe("/oauth2/authorize");
    expect(loginUrl.searchParams.get("client_id")).toBe("client-123");
    expect(loginUrl.searchParams.get("redirect_uri")).toBe("https://app.example.com/auth");

    const logoutUrl = new URL(buildCognitoLogoutUrl(config));
    expect(logoutUrl.origin).toBe("https://auth.example.com");
    expect(logoutUrl.pathname).toBe("/logout");
    expect(logoutUrl.searchParams.get("client_id")).toBe("client-123");
    expect(logoutUrl.searchParams.get("redirect_uri")).toBe("https://app.example.com/auth");
  });

  it("keeps snake_case Cognito config compatibility", () => {
    const config: CognitoConfig = {
      enabled: true,
      client_id: "snake-client",
      domain: "https://auth.example.com",
      redirect_uri: "https://app.example.com/auth",
      logout_url: "https://auth.example.com/logout?client_id=snake-client",
    };

    expect(cognitoClientId(config)).toBe("snake-client");
    expect(cognitoRedirectUri(config)).toBe("https://app.example.com/auth");
    expect(buildCognitoLogoutUrl(config)).toContain("client_id=snake-client");
  });

  it("falls back to the same-origin auth callback when no redirect URI is configured", () => {
    const config: CognitoConfig = {
      enabled: true,
      clientId: "client-123",
      domain: "https://auth.example.com",
      logoutUrl: "https://auth.example.com/logout?client_id=client-123",
    };

    const loginUrl = new URL(buildCognitoLoginUrl(config));
    const logoutUrl = new URL(buildCognitoLogoutUrl(config));

    expect(loginUrl.searchParams.get("redirect_uri")).toBe(`${window.location.origin}/auth`);
    expect(logoutUrl.searchParams.get("redirect_uri")).toBe(`${window.location.origin}/auth`);
  });
});
