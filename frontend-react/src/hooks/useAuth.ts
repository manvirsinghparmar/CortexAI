import { useState, useEffect, useCallback } from "react";
import { fetchCognitoConfig, fetchWhoAmI, buildCognitoLoginUrl } from "../api/auth";
import type { CognitoConfig, WhoAmIResponse } from "../types";

interface AuthState {
  cognitoConfig: CognitoConfig | null;
  whoAmI: WhoAmIResponse | null;
  loading: boolean;
  loggedIn: boolean;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    cognitoConfig: null,
    whoAmI: null,
    loading: true,
    loggedIn: false,
  });

  const refresh = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true }));
    try {
      const [config, whoAmI] = await Promise.all([
        fetchCognitoConfig().catch(() => null),
        fetchWhoAmI().catch(() => null),
      ]);
      setState({
        cognitoConfig: config,
        whoAmI,
        loading: false,
        loggedIn: !!whoAmI?.user_id,
      });
    } catch {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(() => {
    const { cognitoConfig } = state;
    if (!cognitoConfig?.enabled) return;
    try {
      const url = buildCognitoLoginUrl(cognitoConfig);
      window.location.href = url;
    } catch {
      // Cognito not fully configured
    }
  }, [state]);

  const logout = useCallback(async () => {
    try {
      await fetch("/v1/auth/logout", { method: "POST", credentials: "include" });
    } finally {
      setState((prev) => ({ ...prev, whoAmI: null, loggedIn: false }));
    }
  }, []);

  return {
    ...state,
    login,
    logout,
    refresh,
  };
}
