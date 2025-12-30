flowchart LR
  %% =========================
  %% AI Control Tower - 1 Page Architecture
  %% =========================

  U[User / Developer<br/>(CLI • Web UI • API Client)]
  API[Gateway API<br/>(REST/WS)]
  UI[Presentation Layer<br/>(CLI + Future Web UI)]
  U --> UI --> API

  subgraph CORE[Core Orchestration Layer]
    ORCH[Orchestrator<br/>fan-out • normalize • retries]
    ROUTER[Routing Engine<br/>rules • cost caps • fallback]
    CTX[Context Manager<br/>multi-turn • memory policy]
    PROMPT[Prompt Templates<br/>versioned prompts]
    SCORER[Evaluator/Scorer<br/>manual + automated]
  end

  API --> ORCH
  ORCH --> ROUTER
  ORCH --> CTX
  ORCH --> PROMPT
  ORCH --> SCORER

  subgraph PROVIDERS[Provider Connectors (Adapters)]
    OA[OpenAI Adapter]
    GE[Gemini Adapter]
    HF[Hugging Face Adapter]
    OSS[Local/OSS Adapter<br/>(optional)]
  end

  ROUTER --> OA
  ROUTER --> GE
  ROUTER --> HF
  ROUTER --> OSS

  OA --> NORM[Response Normalizer<br/>(common schema)]
  GE --> NORM
  HF --> NORM
  OSS --> NORM

  NORM --> ORCH

  subgraph DATA[Telemetry + Governance]
    USG[Usage Metering<br/>(tokens • latency • cost)]
    AUDIT[Audit Log<br/>(who • what • when • model)]
    STORE[(Storage<br/>SQLite/Postgres/Files)]
  end

  ORCH --> USG
  ORCH --> AUDIT
  USG --> STORE
  AUDIT --> STORE

  subgraph POLICY[Policy & Controls]
    RBAC[Auth/RBAC (Phase 3)]
    LIMITS[Budgets/Quotas<br/>(per user/team)]
    REDACT[Redaction/PII Rules<br/>(optional)]
  end

  API --> RBAC
  ROUTER --> LIMITS
  ORCH --> REDACT

  STORE --> DASH[Analytics Dashboard<br/>(Phase 2/3)]
  API --> DASH