import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";

import {
  assertViteDevServerAllowed,
  loadRepositoryRuntimeEnvironment,
} from "./viteDevServerGuard";

declare const process: {
  env: Record<string, string | undefined>;
};

function localDevServerGuard(
  command: "build" | "serve",
  environment: Record<string, string | undefined>,
): Plugin {
  return {
    name: "cortexai-local-vite-dev-server-only",
    apply: "serve",
    configResolved(config) {
      assertViteDevServerAllowed({
        command,
        environment,
        host: config.server.host,
      });
    },
  };
}

export default defineConfig(({ command, mode }) => {
  const environment = loadRepositoryRuntimeEnvironment(mode, process.env);
  const apiProxyTarget = environment.CORTEX_API_PROXY_TARGET ?? "http://localhost:8000";

  return {
    plugins: [react(), localDevServerGuard(command, environment)],
    server: {
      port: 5173,
      proxy: {
        "/v1": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/auth": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/runtime-config.js": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test-setup.ts"],
    },
  };
});
