import { describe, expect, it } from "vitest";

import { assertViteDevServerAllowed, isLoopbackViteHost } from "./viteDevServerGuard";

describe("Vite development server guard", () => {
  it.each([undefined, false, "localhost", "127.0.0.1", "127.10.20.30", "::1", "[::1]"])(
    "accepts the loopback host %s",
    (host) => {
      expect(isLoopbackViteHost(host)).toBe(true);
    },
  );

  it.each([true, "0.0.0.0", "::", "10.0.0.8", "dev.example.com"])(
    "classifies the public host %s as non-loopback",
    (host) => {
      expect(isLoopbackViteHost(host)).toBe(false);
    },
  );

  it.each(["APP_ENV", "ENVIRONMENT", "ENV"])(
    "blocks the Vite server when %s is production-like",
    (name) => {
      expect(() =>
        assertViteDevServerAllowed({
          command: "serve",
          environment: { [name]: "production", ALLOW_PUBLIC_VITE_DEV_SERVER: "true" },
          host: "127.0.0.1",
        }),
      ).toThrow(new RegExp(`development server is disabled.*${name} is production-like`, "i"));
    },
  );

  it("blocks a publicly bound Vite server by default", () => {
    expect(() =>
      assertViteDevServerAllowed({
        command: "serve",
        environment: {},
        host: "0.0.0.0",
      }),
    ).toThrow(/Refusing to expose the Vite development server/i);
  });

  it("allows an explicit trusted-network development override", () => {
    expect(() =>
      assertViteDevServerAllowed({
        command: "serve",
        environment: { ALLOW_PUBLIC_VITE_DEV_SERVER: "true" },
        host: "0.0.0.0",
      }),
    ).not.toThrow();
  });

  it("never blocks a production build", () => {
    expect(() =>
      assertViteDevServerAllowed({
        command: "build",
        environment: { APP_ENV: "production" },
        host: "0.0.0.0",
      }),
    ).not.toThrow();
  });
});
