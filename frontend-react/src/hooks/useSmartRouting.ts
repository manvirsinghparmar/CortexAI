/** Keeps smart-routing derivation logic in one typed React module. */

export function parseModelKey(key: string): { provider: string; model: string } {
  const idx = key.indexOf(":");
  if (idx < 0) return { provider: "", model: key };
  return { provider: key.slice(0, idx), model: key.slice(idx + 1) };
}

export function hasProvider(key: string): boolean {
  return !!parseModelKey(key).provider;
}

export function deriveSmartMode(selectedKey: string): boolean {
  return !hasProvider(selectedKey);
}

export function isManualOverrideActive(
  mode: string,
  smartModeEnabled: boolean,
  key: string,
): boolean {
  return mode === "single" && !smartModeEnabled && hasProvider(key);
}

export function isModelDropdownVisible(mode: string, smartModeEnabled: boolean): boolean {
  return mode === "single" && !smartModeEnabled;
}

export function resolveManualSelection(selectedKey: string, fallbackKey: string): string {
  return hasProvider(selectedKey) ? selectedKey : fallbackKey;
}

/** Builds the "provider:model" composite key used throughout the UI. */
export function toModelKey(provider: string, model: string): string {
  return `${provider}:${model}`;
}
