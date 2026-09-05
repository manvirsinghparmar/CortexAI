import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

declare const process: {
  env: Record<string, string | undefined>;
};

const apiProxyTarget = process.env.CORTEX_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
   allowedHosts: ["kudlo.triobrain.com"],
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
       // Source maps are disabled in production: they consume significant memory
    // during the build (~2x the bundle size) and expose source code publicly.
    // Enable locally with: VITE_SOURCEMAP=true npm run build
    sourcemap: process.env.VITE_SOURCEMAP === "true",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
