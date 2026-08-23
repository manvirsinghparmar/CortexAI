import catalogData from "./models.data.json";
import type { ModelCatalogItem } from "../types";
import { DEFAULT_MODELS } from "./defaultModels";
import { getModelPresentation } from "./modelPresentation";

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
  pricingLabel?: string;
  pricingSourceUrl?: string;
  sourceVerifiedAt?: string;
  lifecycleStatus?: string;
  releaseStatus?: string;
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

const TASK_TAGS: Record<string, string> = {
  reasoning: "Reasoning",
  coding: "Coding",
  agentic: "Agentic",
  cheap: "Fast & cheap",
  fast: "Fast & cheap",
  vision: "Vision",
  multimodal: "Vision",
  long_context: "Long context",
  writing: "Writing",
  general: "Writing",
};

export function buildModelsCatalogFromLiveModels(
  liveModels: ModelCatalogItem[],
  baseCatalog = MODELS_CATALOG,
): ModelsCatalog {
  const selectable = liveModels.filter(
    (model) => model.enabled && model.selectable !== false,
  );
  const providerOrder = new Map(
    baseCatalog.providers.map((provider, index) => [
      getPresentationProviderKey(provider.key),
      index,
    ]),
  );
  const grouped = new Map<string, ModelCatalogItem[]>();
  for (const model of selectable) {
    const models = grouped.get(model.provider) ?? [];
    models.push(model);
    grouped.set(model.provider, models);
  }

  const providers = [...grouped.entries()]
    .sort(
      ([left], [right]) =>
        (providerOrder.get(left) ?? 99) - (providerOrder.get(right) ?? 99),
    )
    .map(([providerKey, models]) => {
      const existing = baseCatalog.providers.find(
        (provider) => getPresentationProviderKey(provider.key) === providerKey,
      );
      const provider: CatalogProvider = existing
        ? { ...existing, key: providerKey, models: [] }
        : {
            key: providerKey,
            name: providerDisplayName(providerKey),
            colorVar: "--cx-prov-graphite",
            colorSoftVar: "--cx-prov-graphite-soft",
            glyph: "#64748b",
            models: [],
          };
      provider.models = models
        .map((model) => liveCatalogModel(model))
        .sort((left, right) => modelRank(right) - modelRank(left));
      return provider;
    });

  const flatModels = providers.flatMap((provider) => provider.models);
  const rec: Record<string, string> = {};
  for (const task of baseCatalog.tasks.filter((item) => item !== "All")) {
    const candidate = flatModels
      .filter((model) => model.tags.includes(task))
      .sort((left, right) => modelRank(right) - modelRank(left))[0];
    if (candidate) rec[task] = candidate.id;
  }

  return {
    ...baseCatalog,
    rec,
    providers,
  };
}

function liveCatalogModel(model: ModelCatalogItem): CatalogModel {
  const tags = [...new Set(model.tags.map((tag) => TASK_TAGS[tag] ?? "").filter(Boolean))];
  const tier = presentationTier(model);
  const contextLabel = `${formatTokenCount(model.context_limit)} context`;
  const strengths = [
    contextLabel,
    model.reasoning_modes?.length
      ? `Reasoning modes: ${model.reasoning_modes.join(", ")}`
      : undefined,
    model.cached_input_cost_per_1m != null
      ? `Cached input: $${formatRate(model.cached_input_cost_per_1m)} / 1M tokens`
      : undefined,
  ].filter((value): value is string => Boolean(value));
  return {
    name:
      model.display_name ||
      getModelPresentation(model.provider, model.model).label,
    id: `${model.provider}:${model.model}`,
    tier,
    speed: presentationSpeed(model),
    bestFor: model.description || `Current ${providerDisplayName(model.provider)} model.`,
    tags: tags.length > 0 ? tags : ["Writing"],
    strengths,
    pricingLabel: `$${formatRate(model.input_cost_per_1m)} input · $${formatRate(
      model.output_cost_per_1m,
    )} output / 1M tokens`,
    pricingSourceUrl: model.pricing_source_url,
    sourceVerifiedAt: model.source_verified_at,
    lifecycleStatus: model.lifecycle_status,
    releaseStatus: model.release_status,
  };
}

function presentationTier(model: ModelCatalogItem): ModelTier {
  if (model.tags.includes("coding") && model.tags.includes("agentic")) return "Coding";
  if (model.tier === "T3") return "Flagship";
  if (model.tier === "T2") return "Balanced";
  if (model.tier === "T0") return "Lite";
  return model.tags.includes("reasoning") ? "Reasoning" : "Fast";
}

function presentationSpeed(model: ModelCatalogItem): ModelSpeed {
  if (model.tier === "T0" || model.tags.includes("fast")) return "Fast";
  if (model.tier === "T3" && !model.tags.includes("fast")) return "Slow";
  return "Medium";
}

function modelRank(model: CatalogModel): number {
  const depth = getDepthInfo(model.tier).level;
  return depth * 10 + getSpeedLevel(model.speed);
}

function formatRate(value: number): string {
  return value < 0.01 ? value.toFixed(4) : value.toFixed(2);
}

function formatTokenCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(".0", "")}M-token`;
  return `${Math.round(value / 1000)}K-token`;
}

function providerDisplayName(provider: string): string {
  const names: Record<string, string> = {
    openai: "OpenAI · GPT",
    claude: "Anthropic · Claude",
    gemini: "Google · Gemini",
    deepseek: "DeepSeek",
    grok: "xAI · Grok",
  };
  return names[provider] ?? provider;
}

export const MODELS_CATALOG = buildModelsCatalogFromLiveModels(
  DEFAULT_MODELS,
  catalogData as ModelsCatalog,
);

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

export function getDepthInfo(
  tier: ModelTier,
  catalog: ModelsCatalog = catalogData as ModelsCatalog,
): DepthInfo {
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

export function getSpeedLevel(
  speed: ModelSpeed,
  catalog: ModelsCatalog = catalogData as ModelsCatalog,
): number {
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
