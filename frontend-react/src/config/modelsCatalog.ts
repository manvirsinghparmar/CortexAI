import catalogData from "./models.data.json";

export type ModelTier =
  | "Flagship"
  | "Balanced"
  | "Fast"
  | "Lite"
  | "Reasoning"
  | "Coding"
  | "Multimodal";

export type ModelSpeed = "Fast" | "Medium" | "Slow";
export type DepthLabel = "Deep" | "Balanced" | "Light";

export interface CatalogModel {
  name: string;
  id: string;
  tier: ModelTier;
  speed: ModelSpeed;
  bestFor: string;
  tags: string[];
  strengths: string[];
}

export interface CatalogProvider {
  key: string;
  name: string;
  colorVar: string;
  colorSoftVar: string;
  glyph: string;
  models: CatalogModel[];
}

export interface ModelsCatalog {
  _comment?: string;
  tasks: string[];
  depthRule: Record<DepthLabel, ModelTier[]>;
  speedLevels: Record<ModelSpeed, number>;
  rec: Record<string, string>;
  providers: CatalogProvider[];
}

export interface CatalogModelWithProvider {
  provider: CatalogProvider;
  model: CatalogModel;
}

export interface CatalogSummary {
  providerCount: number;
  modelCount: number;
}

export interface DepthInfo {
  label: DepthLabel;
  level: number;
}

const DEPTH_LEVELS: Record<DepthLabel, number> = {
  Deep: 3,
  Balanced: 2,
  Light: 1,
};

export const MODELS_CATALOG = catalogData as ModelsCatalog;

export function getModelsCatalogSummary(catalog = MODELS_CATALOG): CatalogSummary {
  return {
    providerCount: catalog.providers.length,
    modelCount: catalog.providers.reduce((total, provider) => total + provider.models.length, 0),
  };
}

export function findCatalogModelById(
  modelId: string | undefined,
  catalog = MODELS_CATALOG,
): CatalogModelWithProvider | null {
  if (!modelId) return null;

  for (const provider of catalog.providers) {
    const model = provider.models.find((candidate) => candidate.id === modelId);
    if (model) return { provider, model };
  }

  return null;
}

export function getDepthInfo(tier: ModelTier, catalog = MODELS_CATALOG): DepthInfo {
  for (const [label, tiers] of Object.entries(catalog.depthRule) as [
    DepthLabel,
    ModelTier[],
  ][]) {
    if (tiers.includes(tier)) {
      return { label, level: DEPTH_LEVELS[label] };
    }
  }

  return { label: "Light", level: DEPTH_LEVELS.Light };
}

export function getSpeedLevel(speed: ModelSpeed, catalog = MODELS_CATALOG): number {
  return catalog.speedLevels[speed] ?? 1;
}

export function getPresentationProviderKey(providerKey: string): string {
  const normalized = providerKey.trim().toLowerCase();
  if (normalized === "anthropic") return "claude";
  if (normalized === "google") return "gemini";
  if (normalized === "xai") return "grok";
  return normalized;
}

export function splitGatewayModelId(modelId: string): { provider: string; model: string } {
  const separator = modelId.indexOf(":");
  if (separator < 0) return { provider: "", model: modelId };

  return {
    provider: modelId.slice(0, separator),
    model: modelId.slice(separator + 1),
  };
}

export function getModelSearchText(model: CatalogModel): string {
  return [
    model.name,
    model.id,
    model.tier,
    model.speed,
    model.bestFor,
    ...model.tags,
    ...model.strengths,
  ]
    .join(" ")
    .toLowerCase();
}
