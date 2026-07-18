const PRODUCTION_ENVIRONMENT_VALUES = new Set(["prod", "production"]);

type RuntimeEnvironment = Record<string, string | undefined>;

function isEnabled(value: string | undefined): boolean {
  return ["1", "true", "yes", "on"].includes((value ?? "").trim().toLowerCase());
}

function productionEnvironmentName(environment: RuntimeEnvironment): string | undefined {
  return ["APP_ENV", "ENVIRONMENT", "ENV"].find((name) =>
    PRODUCTION_ENVIRONMENT_VALUES.has((environment[name] ?? "").trim().toLowerCase()),
  );
}

function normalizedHost(host: string | boolean | undefined): string {
  if (host === undefined || host === false) {
    return "localhost";
  }
  if (host === true) {
    return "0.0.0.0";
  }
  return host.trim().replace(/^\[|\]$/g, "").toLowerCase();
}

export function isLoopbackViteHost(host: string | boolean | undefined): boolean {
  const value = normalizedHost(host);
  return value === "localhost" || value === "::1" || value.startsWith("127.");
}

export function assertViteDevServerAllowed(options: {
  command: "build" | "serve";
  environment: RuntimeEnvironment;
  host: string | boolean | undefined;
}): void {
  if (options.command !== "serve") {
    return;
  }

  const productionName = productionEnvironmentName(options.environment);
  if (productionName) {
    throw new Error(
      `Vite's development server is disabled because ${productionName} is production-like. ` +
        "Its HMR client can automatically reload browser pages. Build the React app and serve " +
        "frontend-react/dist with Dockerfile.frontend/nginx instead.",
    );
  }

  if (
    !isLoopbackViteHost(options.host) &&
    !isEnabled(options.environment.ALLOW_PUBLIC_VITE_DEV_SERVER)
  ) {
    throw new Error(
      `Refusing to expose the Vite development server on ${normalizedHost(options.host)}. ` +
        "Use the static production build, or set ALLOW_PUBLIC_VITE_DEV_SERVER=true only for " +
        "intentional development on a trusted network.",
    );
  }
}
