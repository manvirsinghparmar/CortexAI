"""Deterministic Tavily search-option resolver."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

TAVILY_DEFAULT_MAX_RESULTS = 5
TAVILY_DEFAULT_SEARCH_DEPTH = "advanced"
TAVILY_DEFAULT_CHUNKS_PER_SOURCE = 3
TAVILY_CREDITS_PER_ADVANCED_SEARCH = 2

_CHUNK_WARNING_EMITTED = False


@dataclass(frozen=True)
class TavilyResolverConfig:
    enhanced_search_enabled: bool = True
    chunks_per_source: int = TAVILY_DEFAULT_CHUNKS_PER_SOURCE
    domain_rules_enabled: bool = True


@dataclass(frozen=True)
class TavilySearchResolution:
    params: dict[str, Any]
    log_fields: dict[str, Any]


_FINANCE_SIGNALS = (
    "inflation",
    "cpi",
    "core cpi",
    "pce",
    "gdp",
    "gnp",
    "economic growth",
    "recession",
    "stagflation",
    "unemployment rate",
    "jobless claims",
    "nonfarm payrolls",
    "jobs report",
    "labour market",
    "labor market",
    "employment data",
    "interest rate",
    "rate hike",
    "rate cut",
    "rate decision",
    "basis points",
    "bps",
    "quantitative easing",
    "qe",
    "quantitative tightening",
    "qt",
    "tapering",
    "federal reserve",
    "fed",
    "fomc",
    "bank of canada",
    "boc",
    "ecb",
    "bank of england",
    "boe",
    "bank of japan",
    "boj",
    "central bank",
    "stock",
    "stocks",
    "stock price",
    "equity",
    "equities",
    "s&p 500",
    "s&p500",
    "nasdaq",
    "dow jones",
    "ftse",
    "tsx",
    "bond",
    "yield",
    "treasury",
    "gilt",
    "forex",
    "fx",
    "commodity",
    "crude oil",
    "gold price",
    "silver price",
    "bitcoin",
    "crypto",
    "earnings",
    "eps",
    "revenue",
    "quarterly results",
    "annual report",
    "profit",
    "margin",
    "ebitda",
    "guidance",
    "ipo",
    "merger",
    "acquisition",
    "m&a",
    "sec filing",
    "10-k",
    "10-q",
    "8-k",
    "annual filing",
    "proxy statement",
    "prospectus",
    "pmi",
    "purchasing managers",
    "consumer confidence",
    "retail sales",
    "trade balance",
    "current account",
    "deficit",
    "surplus",
)

_NEWS_SIGNALS = (
    "breaking",
    "breaking news",
    "just happened",
    "developing",
    "latest update",
    "update on",
    "election",
    "vote",
    "voted",
    "poll",
    "polls",
    "polling",
    "president",
    "prime minister",
    "government",
    "parliament",
    "congress",
    "senate",
    "legislation",
    "bill passed",
    "policy announcement",
    "war",
    "ceasefire",
    "invasion",
    "airstrike",
    "attack",
    "battle",
    "conflict",
    "military operation",
    "troops",
    "sanctions",
    "peace talks",
    "humanitarian",
    "match",
    "game",
    "score",
    "fixture",
    "tournament",
    "championship",
    "league",
    "goal",
    "points",
    "standings",
    "transfer",
    "signing",
    "earthquake",
    "hurricane",
    "flood",
    "wildfire",
    "storm",
    "disaster",
    "evacuation",
    "casualties",
    "summit",
    "diplomatic",
    "treaty",
    "veto",
    "un resolution",
)

_HEALTH_SIGNALS = (
    "disease",
    "disorder",
    "syndrome",
    "diagnosis",
    "condition",
    "symptom",
    "symptoms",
    "chronic",
    "acute",
    "infection",
    "virus",
    "bacteria",
    "cancer",
    "diabetes",
    "hypertension",
    "asthma",
    "arthritis",
    "treatment",
    "therapy",
    "medication",
    "drug",
    "vaccine",
    "vaccination",
    "clinical trial",
    "dosage",
    "prescription",
    "side effects",
    "antibiotic",
    "surgery",
    "procedure",
    "mental health",
    "anxiety",
    "depression",
    "stress",
    "burnout",
    "adhd",
    "ptsd",
    "bipolar",
    "ocd",
    "counselling",
    "counseling",
    "psychiatry",
    "wellbeing",
    "mindfulness",
    "nutrition",
    "diet",
    "calorie",
    "calories",
    "macros",
    "protein",
    "carbs",
    "carbohydrates",
    "fat",
    "fibre",
    "fiber",
    "vitamins",
    "minerals",
    "supplement",
    "supplements",
    "intermittent fasting",
    "keto",
    "vegan",
    "plant-based",
    "workout",
    "exercise",
    "training",
    "gym",
    "strength",
    "cardio",
    "hiit",
    "running",
    "cycling",
    "yoga",
    "pilates",
    "stretching",
    "recovery",
    "muscle",
    "weight loss",
    "fat loss",
    "fitness",
    "reps",
    "sets",
    "sleep",
    "insomnia",
    "rest",
    "circadian",
    "melatonin",
    "sleep quality",
    "fatigue",
    "jet lag",
    "outbreak",
    "pandemic",
    "epidemic",
    "covid",
    "covid-19",
    "who",
    "cdc",
    "nhs",
    "public health",
    "health advisory",
    "health warning",
    "mortality",
    "morbidity",
    "bmi",
    "blood pressure",
    "heart rate",
    "vo2 max",
    "hrv",
    "cholesterol",
    "blood sugar",
    "a1c",
    "body fat percentage",
    "resting heart rate",
)

_CODING_SIGNALS = (
    "python",
    "javascript",
    "typescript",
    "rust",
    "golang",
    "java",
    "kotlin",
    "swift",
    "c++",
    "c#",
    "ruby",
    "php",
    "scala",
    "haskell",
    "matlab",
    "bash",
    "shell script",
    "react",
    "vue",
    "angular",
    "next.js",
    "nuxt",
    "django",
    "fastapi",
    "flask",
    "spring",
    "rails",
    "laravel",
    "express",
    "svelte",
    "tailwindcss",
    "pytorch",
    "tensorflow",
    "langchain",
    "docker",
    "kubernetes",
    "terraform",
    "ansible",
    "github actions",
    "ci/cd",
    "pipeline",
    "deployment",
    "container",
    "serverless",
    "aws",
    "gcp",
    "azure",
    "cdk",
    "helm",
    "algorithm",
    "data structure",
    "api",
    "rest",
    "graphql",
    "grpc",
    "microservices",
    "monolith",
    "caching",
    "database",
    "sql",
    "nosql",
    "orm",
    "concurrency",
    "async",
    "recursion",
    "big o",
    "error",
    "bug",
    "exception",
    "stack trace",
    "segfault",
    "memory leak",
    "race condition",
    "deadlock",
    "fix",
    "debug",
    "troubleshoot",
    "npm",
    "pip",
    "cargo",
    "gem",
    "maven",
    "gradle",
    "poetry",
    "conda",
    "package",
    "dependency",
    "version",
    "upgrade",
    "install",
    "release",
    "changelog",
    "breaking change",
    "deprecation",
    "migration guide",
    "upgrade guide",
    "v2",
    "v3",
    "latest version",
    "patch notes",
    "cve",
    "vulnerability",
    "vuln",
    "exploit",
    "patch",
    "security advisory",
    "owasp",
    "xss",
    "csrf",
    "sql injection",
    "dependency audit",
    "snyk",
)

_DAY_SIGNALS = (
    "today",
    "tonight",
    "this morning",
    "this evening",
    "yesterday",
    "right now",
    "just now",
    "live",
    "breaking",
    "ongoing",
    "happening now",
)
_WEEK_SIGNALS = (
    "latest",
    "current",
    "recent",
    "this week",
    "past week",
    "last week",
    "now",
    "new",
    "newly",
    "just released",
    "just announced",
)
_MONTH_SIGNALS = ("this month", "past month", "last month", "this quarter", "last quarter", "q1", "q2", "q3", "q4")
_YEAR_SIGNALS = ("this year", "past year", "last year", "year to date", "ytd", "fiscal year", "fy")
_MULTI_YEAR_SIGNALS = ("historical", "over time", "trend", "trends", "since", "decade", "century", "all time", "ever")
_STABLE_EXPLANATION_SIGNALS = (
    "what is",
    "what are",
    "define",
    "definition",
    "meaning of",
    "explain",
    "overview",
    "background",
    "history of",
    "how does",
    "why does",
)

_SEC_SIGNALS = ("sec filing", "10-k", "10-q", "8-k", "annual filing", "proxy statement", "prospectus")

_SUPPORTED_COUNTRIES = {
    "australia",
    "brazil",
    "canada",
    "china",
    "france",
    "germany",
    "india",
    "japan",
    "mexico",
    "united kingdom",
    "united states",
}

_REGION_ONLY_PATTERNS = (
    r"\beu\b",
    r"\beuropean union\b",
    r"\beurozone\b",
    r"\beurope\b",
    r"\bglobal\b",
    r"\bworldwide\b",
    r"\binternational\b",
    r"\bnorth america\b",
    r"\bsouth america\b",
    r"\bmiddle east\b",
    r"\basia pacific\b",
    r"\bapac\b",
    r"\bemea\b",
    r"\bg7\b",
    r"\bg20\b",
)

_COUNTRY_PATTERNS = (
    ("canada", (r"\bcanada\b", r"\bcanadian\b")),
    ("united states", (r"\bunited states(?: of america)?\b", r"\busa\b", r"\bu\.s\.\b", r"\bUS\b")),
    ("united kingdom", (r"\bunited kingdom\b", r"\buk\b", r"\bUK\b", r"\bu\.k\.\b", r"\bbritain\b", r"\bbritish\b")),
    ("brazil", (r"\bbrazil\b", r"\bbrazilian\b")),
    ("australia", (r"\baustralia\b", r"\baustralian\b")),
    ("india", (r"\bindia\b", r"\bindian\b")),
    ("france", (r"\bfrance\b", r"\bfrench\b")),
    ("germany", (r"\bgermany\b", r"\bgerman\b")),
    ("japan", (r"\bjapan\b", r"\bjapanese\b")),
    ("china", (r"\bchina\b", r"\bchinese\b")),
    ("mexico", (r"\bmexico\b", r"\bmexican\b")),
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _parse_chunks_per_source(raw: str | None) -> int:
    global _CHUNK_WARNING_EMITTED
    try:
        parsed = int(str(raw or "").strip())
    except Exception:
        parsed = TAVILY_DEFAULT_CHUNKS_PER_SOURCE
    if 1 <= parsed <= 3:
        return parsed
    if not _CHUNK_WARNING_EMITTED:
        logger.warning(
            "Tavily chunks_per_source out of bounds; using default",
            extra={
                "extra_fields": {
                    "event": "research.resolver.config.warning",
                    "provider": "tavily",
                    "config_key": "TAVILY_CHUNKS_PER_SOURCE",
                    "configured_value": str(raw or ""),
                    "resolved_value": TAVILY_DEFAULT_CHUNKS_PER_SOURCE,
                }
            },
        )
        _CHUNK_WARNING_EMITTED = True
    return TAVILY_DEFAULT_CHUNKS_PER_SOURCE


def _coerce_chunks_per_source(value: Any) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        return TAVILY_DEFAULT_CHUNKS_PER_SOURCE
    return parsed if 1 <= parsed <= 3 else TAVILY_DEFAULT_CHUNKS_PER_SOURCE


def tavily_resolver_config_from_env() -> TavilyResolverConfig:
    return TavilyResolverConfig(
        enhanced_search_enabled=_env_bool("TAVILY_ENHANCED_SEARCH_ENABLED", default=True),
        chunks_per_source=_parse_chunks_per_source(
            os.getenv("TAVILY_CHUNKS_PER_SOURCE", str(TAVILY_DEFAULT_CHUNKS_PER_SOURCE))
        ),
        domain_rules_enabled=_env_bool("TAVILY_ENHANCED_SEARCH_DOMAIN_RULES", default=True),
    )


def _signal_pattern(signal: str) -> re.Pattern[str]:
    escaped = re.escape(signal).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def _contains_signal(text: str, signals: tuple[str, ...]) -> bool:
    return any(_signal_pattern(signal).search(text) for signal in signals)


def resolve_category(query: str) -> str:
    text = str(query or "")
    if _contains_signal(text, _FINANCE_SIGNALS):
        return "finance"
    if _contains_signal(text, _HEALTH_SIGNALS):
        return "health"
    if _contains_signal(text, _NEWS_SIGNALS):
        return "news"
    if _contains_signal(text, _CODING_SIGNALS):
        return "coding"
    return "general"


def resolve_time_range(query: str, *, category: str | None = None) -> str | None:
    text = str(query or "")
    if _contains_signal(text, _MULTI_YEAR_SIGNALS):
        return None
    if _contains_signal(text, _DAY_SIGNALS):
        return "day"
    if _contains_signal(text, _WEEK_SIGNALS):
        return "week"
    if _contains_signal(text, _MONTH_SIGNALS):
        return "month"
    if _contains_signal(text, _YEAR_SIGNALS):
        return "year"
    if category in {"finance", "news"} and not _contains_signal(text, _STABLE_EXPLANATION_SIGNALS):
        return "week"
    return None


def _countries_in_text(text: str) -> set[str]:
    found: set[str] = set()
    for country, patterns in _COUNTRY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text, flags=0 if "US" in pattern or "UK" in pattern else re.IGNORECASE):
                found.add(country)
                break
    return {country for country in found if country in _SUPPORTED_COUNTRIES}


def _has_region_only_cue(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _REGION_ONLY_PATTERNS)


def _country_from_locale(locale_context: str | None) -> str | None:
    value = str(locale_context or "").strip().lower().replace("_", "-")
    if not value:
        return None
    if value in {"canada", "ca"} or value.endswith("-ca"):
        return "canada"
    if value in {"united states", "usa", "us"} or value.endswith("-us"):
        return "united states"
    if value in {"united kingdom", "uk", "gb"} or value.endswith("-gb"):
        return "united kingdom"
    return None


def resolve_country(query: str, locale_context: str | None = None) -> str | None:
    text = str(query or "")
    countries = _countries_in_text(text)
    if len(countries) > 1:
        return None
    if _has_region_only_cue(text):
        return None
    if len(countries) == 1:
        return next(iter(countries))
    if _contains_signal(text, _SEC_SIGNALS):
        return "united states"
    return _country_from_locale(locale_context)


def _domain_rule_for(category: str, country: str | None, query: str, *, enabled: bool) -> tuple[str | None, list[str]]:
    if not enabled or category != "finance" or not country:
        return None, []
    if country == "canada":
        return "canada_economic", ["bankofcanada.ca", "statcan.gc.ca"]
    if country == "united states":
        if _contains_signal(query, _SEC_SIGNALS):
            return "us_sec", ["sec.gov"]
        return "us_economic", ["bls.gov", "bea.gov", "federalreserve.gov"]
    if country == "united kingdom":
        return "uk_economic", ["ons.gov.uk", "bankofengland.co.uk"]
    return None, []


def resolve_tavily_search_options(
    query: str,
    *,
    locale_context: str | None = None,
    config: TavilyResolverConfig | None = None,
    max_results: int = TAVILY_DEFAULT_MAX_RESULTS,
    search_depth: str = TAVILY_DEFAULT_SEARCH_DEPTH,
) -> TavilySearchResolution:
    cfg = config or tavily_resolver_config_from_env()
    chunks = _coerce_chunks_per_source(cfg.chunks_per_source)
    params: dict[str, Any] = {
        "max_results": TAVILY_DEFAULT_MAX_RESULTS,
        "search_depth": TAVILY_DEFAULT_SEARCH_DEPTH,
        "chunks_per_source": int(chunks),
        "include_raw_content": False,
        "include_answer": False,
        "auto_parameters": False,
    }

    category = "general"
    topic_sent: str | None = None
    time_range: str | None = None
    country_detected: str | None = None
    country_sent: str | None = None
    domain_rule: str | None = None
    include_domains: list[str] = []

    if cfg.enhanced_search_enabled:
        category = resolve_category(query)
        topic_sent = category if category in {"finance", "news"} else None
        time_range = resolve_time_range(query, category=category)
        country_detected = resolve_country(query, locale_context=locale_context)
        country_sent = country_detected if topic_sent is None else None
        domain_rule, include_domains = _domain_rule_for(
            category,
            country_detected,
            str(query or ""),
            enabled=cfg.domain_rules_enabled,
        )

        if topic_sent:
            params["topic"] = topic_sent
        if time_range:
            params["time_range"] = time_range
        if country_sent:
            params["country"] = country_sent
        if include_domains:
            params["include_domains"] = include_domains

    log_fields = {
        "enhanced_search_enabled": bool(cfg.enhanced_search_enabled),
        "chunks_per_source": int(chunks),
        "category": category,
        "topic_sent": topic_sent,
        "time_range": time_range,
        "country_detected": country_detected,
        "country_sent": country_sent,
        "domain_rule": domain_rule,
        "include_domain_count": len(include_domains),
    }
    return TavilySearchResolution(params=params, log_fields=log_fields)
