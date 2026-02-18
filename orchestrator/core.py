"""
CortexOrchestrator - Core business logic layer for CortexAI.

Key guarantees:
- CLI/API layers stay thin (no provider imports there)
- No exceptions bubble up from ask() / compare()
- TokenTracker updates happen here (business layer)
"""

import hashlib
import os
import threading
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from api.base_client import BaseAIClient
from models.unified_response import (
    MultiUnifiedResponse,
    NormalizedError,
    TokenUsage,
    UnifiedResponse,
)
from models.user_context import UserContext
from orchestrator.multi_orchestrator import MultiModelOrchestrator
from orchestrator.model_registry import ModelRegistry
from orchestrator.model_selector import ModelSelector, ReliabilityStore
from orchestrator.prompt_analyzer import PromptAnalyzer
from orchestrator.response_validator import ResponseValidator
from orchestrator.routing_types import (
    ModelCandidate,
    RoutingConstraints,
    Tier,
)
from orchestrator.fallback_manager import FallbackManager, FallbackPolicy
from orchestrator.smart_router import SmartRouter
from orchestrator.tier_decider import TierDecider
from tools.web import create_research_service_from_env
from tools.web.intent import (
    is_explicit_web_request,
    normalize_topic,
    sanitize_query,
    should_reuse_research,
    should_search,
    wants_more_sources,
)
from tools.web.research_state import (
    ResearchSource,
    ResearchState,
    create_initial_state,
)
from tools.web.session_state import get_session_store
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger
from utils.prompt_optimizer import PromptOptimizer
from utils.token_tracker import TokenTracker

logger = get_logger(__name__)


class CortexOrchestrator:
    def __init__(self):
        self._multi_orchestrator = MultiModelOrchestrator()
        self._client_cache: dict[str, BaseAIClient] = {}
        self._research_states: dict[str, Any] = {}  # session_id -> ResearchState
        self._research_lock = threading.Lock()  # thread-safe access to states
        self._smart_router: SmartRouter | None = None
        self._model_registry: ModelRegistry | None = None
        self._selector: ModelSelector | None = None
        self._validator: ResponseValidator | None = None
        self._fallback_manager: FallbackManager | None = None
        self._prompt_analyzer: PromptAnalyzer | None = None
        self._tier_decider: TierDecider | None = None
        self._enable_browse_disclaimer_check = (
            os.getenv("ENABLE_BROWSE_DISCLAIMER_CHECK", "true").lower() == "true"
        )
        self._enable_fabrication_check = (
            os.getenv("ENABLE_FABRICATION_CHECK", "true").lower() == "true"
        )

        # Initialize prompt optimizer (optional - controlled by env var)
        self._prompt_optimizer = None
        if os.getenv("ENABLE_PROMPT_OPTIMIZATION", "false").lower() == "true":
            try:
                provider = os.getenv("PROMPT_OPTIMIZER_PROVIDER", "gemini")
                self._prompt_optimizer = PromptOptimizer(provider=provider)
                logger.info(f"Prompt optimizer initialized with provider: {provider}")
            except Exception as e:
                logger.warning(f"Prompt optimizer initialization failed: {e}")
                self._prompt_optimizer = None

        # Initialize research service (optional - gracefully handle if not configured)
        try:
            self.research_service = create_research_service_from_env()
            self.session_store = get_session_store()
            logger.info("Research service initialized successfully")
        except Exception as e:
            self.research_service = None
            self.session_store = None
            logger.warning(f"Research service not available: {e}")

        # Initialize smart routing components (optional but preferred)
        try:
            self._model_registry = ModelRegistry.from_yaml()
            thresholds = self._model_registry.routing_defaults().get("thresholds", {})
            token_buffer = thresholds.get("token_buffer", 200)
            self._selector = ModelSelector(
                reliability_store=ReliabilityStore(), token_buffer=token_buffer
            )
            self._validator = ResponseValidator(thresholds=thresholds)
            self._fallback_manager = FallbackManager()
            self._prompt_analyzer = PromptAnalyzer()
            self._tier_decider = TierDecider(thresholds=thresholds)
            self._smart_router = SmartRouter(
                registry=self._model_registry,
                selector=self._selector,
                validator=self._validator,
                fallback_manager=self._fallback_manager,
                analyzer=self._prompt_analyzer,
                decider=self._tier_decider,
            )
            logger.info("Smart routing components initialized")
        except Exception as e:
            logger.warning(f"Smart routing initialization failed: {e}")

    # ---------- helpers ----------

    def _error_response(
        self,
        *,
        provider: str,
        model: str,
        message: str,
        code: str = "unknown",
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> UnifiedResponse:
        return UnifiedResponse(
            request_id=str(uuid.uuid4()),
            text="",
            provider=provider,
            model=model,
            latency_ms=0,
            token_usage=TokenUsage(0, 0, 0),
            estimated_cost=0.0,
            finish_reason="error",
            error=NormalizedError(
                code=code,
                message=message,
                provider=provider,
                retryable=retryable,
                details=details or {},
            ),
        )

    def _get_client(self, model_type: str, model_name: str | None = None) -> BaseAIClient:
        model_type = (model_type or "").lower().strip()
        cache_key = f"{model_type}:{model_name or 'default'}"
        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        if model_type == "openai":
            from api.openai_client import OpenAIClient

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            model_name = model_name or os.getenv("DEFAULT_OPENAI_MODEL", "gpt-3.5-turbo")
            client = OpenAIClient(api_key=api_key, model_name=model_name)

        elif model_type == "gemini":
            from api.google_gemini_client import GeminiClient

            api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_GEMINI_API_KEY not found in environment variables")
            model_name = model_name or os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.5-flash-lite")
            client = GeminiClient(api_key=api_key, model_name=model_name)

        elif model_type == "deepseek":
            from api.deepseek_client import DeepSeekClient

            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
            model_name = model_name or os.getenv("DEFAULT_DEEPSEEK_MODEL", "deepseek-chat")
            client = DeepSeekClient(api_key=api_key, model_name=model_name)

        elif model_type == "grok":
            from api.grok_client import GrokClient

            api_key = os.getenv("GROK_API_KEY")
            if not api_key:
                raise ValueError("GROK_API_KEY not found in environment variables")
            model_name = model_name or os.getenv("DEFAULT_GROK_MODEL", "grok-4-latest")
            client = GrokClient(api_key=api_key, model_name=model_name)

        else:
            raise ValueError(f"Unsupported MODEL_TYPE: {model_type}")

        self._client_cache[cache_key] = client
        logger.info(
            "Initialized client",
            extra={"extra_fields": {"provider": model_type, "model": model_name}},
        )
        return client

    def _build_messages(self, prompt: str, context: UserContext | None) -> list[dict[str, str]]:
        # Build base system instruction (ALWAYS injected first)
        system_instruction = {
            "role": "system",
            "content": """SYSTEM CONTEXT AND RULES:

You are CortexAI with REAL-TIME WEB RESEARCH capability.
CURRENT DATE: January 17, 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1: CHECK IF WEB SOURCES ARE PRESENT IN THIS CONVERSATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BEFORE reading the user's question, scroll up and check if there's a SYSTEM message that contains:
   "WEB RESEARCH SOURCES:"
   AND shows sources formatted like:
   "[1] Title"
   "[2] Title"
   "[3] Title"
   with URL and excerpt text

If you see this ⬆️ then web sources ARE present. Proceed to STEP 2A.
If you DON'T see this ⬆️ then no web sources were provided. Proceed to STEP 2B.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2A: IF WEB SOURCES ARE PRESENT (you found the "WEB RESEARCH SOURCES:" message above)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ READ the source excerpts carefully
✅ EXTRACT specific numbers, facts, dates from those excerpts
✅ ANSWER the user's question using ONLY information from those excerpts
✅ CITE sources: [1], [2], [3]
✅ If the specific info isn't in excerpts: "The provided sources don't contain that specific information."

❌ DO NOT say "I don't have current data" - you DO have it (the sources above)
❌ DO NOT ignore the sources
❌ DO NOT make up information not in the excerpts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2B: IF NO WEB SOURCES (you didn't find "WEB RESEARCH SOURCES:" message above)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For factual queries requiring current data (prices, percentages, recent events):
   ✅ Say: "I don't have current data for this query."

For general knowledge questions:
   ✅ Answer using your training data (but note knowledge cutoff if relevant)

❌ NEVER invent numbers, percentages, statistics, or specific facts
❌ NEVER say "strong performance", "record highs" without actual data

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OTHER IMPORTANT RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• You CANNOT control web research - the system does it automatically
• NEVER say "I will search/check/retrieve/access data" - you can't do this
• If user asks "can you search": Say "The system handles web research automatically.
  If sources aren't shown above, try rephrasing with time indicators like 'latest', 'recent', '2025', 'last year'."
• You DO have internet access (via system-provided sources) - never claim otherwise

These rules prevent misinformation. Follow them carefully.""",
        }

        if context and context.conversation_history:
            msgs = context.get_messages()
            msgs.append({"role": "user", "content": prompt})
            # Inject system instruction at the beginning
            return [system_instruction, *msgs]
        return [system_instruction, {"role": "user", "content": prompt}]

    def _generate_session_id(self, messages: list[dict[str, str]]) -> str:
        """
        Generate session ID from conversation history.

        Uses hash of all messages (except current user prompt) to identify unique sessions.
        If messages is empty or only has one user message, returns "default" session.

        Args:
            messages: Conversation messages

        Returns:
            Session ID string
        """
        if not messages or len(messages) <= 1:
            return "default"

        # Hash all messages except the last one (current prompt)
        history = messages[:-1]
        history_str = str(history)
        session_hash = hashlib.sha256(history_str.encode()).hexdigest()[:16]
        return f"session_{session_hash}"

    def _get_session_id(self, context: UserContext | None, messages: list[dict[str, str]]) -> str:
        """
        Get session ID from context or generate from messages.

        Args:
            context: UserContext (may have session_id)
            messages: Conversation messages

        Returns:
            Session ID string
        """
        if context and hasattr(context, "session_id") and context.session_id:
            return context.session_id
        return self._generate_session_id(messages)

    def _optimize_prompt_if_enabled(self, prompt: str) -> tuple[str, dict]:
        """
        Optimize prompt if optimization is enabled.

        Returns:
            tuple: (optimized_prompt, metadata)
            - If optimization disabled/fails: returns (original_prompt, {})
            - If optimization succeeds: returns (optimized_prompt, optimization_metadata)
        """
        if not self._prompt_optimizer:
            return prompt, {}

        try:
            result = self._prompt_optimizer.optimize_prompt({"prompt": prompt})

            if result.get("error"):
                logger.warning(f"Prompt optimization failed: {result['error']['message']}")
                return prompt, {"optimization_error": result["error"]["message"]}

            optimized = result.get("optimized_prompt", prompt)
            metadata = {
                "optimization_used": True,
                "original_prompt": prompt,
                "optimization_steps": result.get("steps", []),
                "optimization_metrics": result.get("metrics", {}),
            }

            logger.info(f"Prompt optimized: '{prompt[:50]}...' -> '{optimized[:50]}...'")
            return optimized, metadata

        except Exception as e:
            logger.error(f"Prompt optimization error: {e}")
            return prompt, {"optimization_error": str(e)}

    def _get_or_create_research_state(self, session_id: str, research_mode: str) -> ResearchState:
        """
        Get or create ResearchState for a session (thread-safe).

        Args:
            session_id: Session identifier
            research_mode: Current research mode

        Returns:
            ResearchState instance
        """
        with self._research_lock:
            if session_id not in self._research_states:
                # Get TTL from env, default to 900 seconds (15 minutes)
                ttl_seconds = int(os.getenv("RESEARCH_TTL_SECONDS", "900"))
                self._research_states[session_id] = create_initial_state(
                    session_id=session_id, mode=research_mode, ttl_seconds=ttl_seconds
                )
            else:
                # Update mode if it changed
                existing = self._research_states[session_id]
                if existing.mode != research_mode:
                    self._research_states[session_id] = existing.with_update(mode=research_mode)

            return self._research_states[session_id]

    def _apply_research_if_needed(
        self,
        *,
        prompt: str,
        messages: list[dict[str, str]],
        research_mode: str,
        context: UserContext | None = None,
    ) -> tuple[list[dict[str, str]], dict[str, Any]]:
        """
        Apply web research if needed based on research_mode and session state.

        Enforces deterministic, state-driven behavior:
        1. Reuse existing research when appropriate
        2. Perform new search when needed
        3. Never search on meta follow-ups
        4. Never pass garbage queries to search

        Args:
            prompt: User prompt
            messages: Current messages list
            research_mode: "off" | "auto" | "on"
            context: Optional user context

        Returns:
            Tuple of (updated_messages, research_metadata)
        """
        # 1) Determine session ID
        session_id = self._get_session_id(context, messages)

        # 2) Get or create research state (thread-safe)
        state = self._get_or_create_research_state(session_id, research_mode)

        # 3) Check if we should reuse existing research
        should_reuse = should_reuse_research(prompt, state)
        logger.info(f"Research decision - reuse: {should_reuse}, prompt: {prompt[:50]}...")

        if should_reuse:
            # Inject previous research
            injected_messages = [{"role": "system", "content": state.injected_text}, *messages]

            # Update last_used_at
            updated_state = state.with_update(last_used_at=datetime.now(timezone.utc).isoformat())
            with self._research_lock:
                self._research_states[session_id] = updated_state

            # Build metadata
            metadata = {
                "research_used": True,
                "research_reused": True,
                "research_topic": state.topic if state.topic else None,
                "research_error": None,
                "sources": [
                    {"id": s.id, "title": s.title, "url": s.url, "fetched_at": s.fetched_at}
                    for s in state.sources
                ],
            }
            return injected_messages, metadata

        # 4) Check if we should perform new search
        should_do_search = should_search(prompt, research_mode, state)
        logger.info(
            f"Research decision - search: {should_do_search}, mode: {research_mode}, prompt: {prompt[:50]}..."
        )

        if not should_do_search:
            logger.info(f"No research needed (mode={research_mode})")
            return messages, {
                "research_used": False,
                "research_reused": False,
                "research_topic": None,
                "research_error": None,
                "sources": [],
            }

        # 5) Perform new search
        if not self.research_service:
            return messages, {
                "research_used": False,
                "research_reused": False,
                "research_topic": None,
                "research_error": "service_not_configured",
                "sources": [],
            }

        # Extract PREVIOUS user message for context (helps with meta-commands like "check again")
        # Skip the current prompt (last user message) and get the one before it
        last_user_msg = None
        user_messages = [
            msg["content"] for msg in messages if msg.get("role") == "user" and msg.get("content")
        ]
        if len(user_messages) >= 2:
            # Get second-to-last user message (the one before current prompt)
            last_user_msg = user_messages[-2]

        # Apply query sanitization (remove stop words, handle meta-commands)
        logger.debug(f"Applying sanitization to: '{prompt[:50]}...'")
        query = sanitize_query(prompt, state, last_user_msg)

        if not query:
            # No query and no previous state - can't proceed
            logger.warning(f"Blocked garbage query with no fallback: {prompt[:50]}...")
            return messages, {
                "research_used": False,
                "research_reused": False,
                "research_topic": None,
                "research_error": "invalid_query",
                "sources": [],
            }

        # Log if query was transformed (different from prompt)
        if query != prompt:
            # Sanitization changed the query
            if wants_more_sources(prompt):
                logger.info(f"'More sources' requested, re-searching topic: '{query[:50]}...'")
            else:
                logger.info(f"Heuristics transformed query: '{prompt[:30]}...' → '{query[:50]}...'")

        # Execute search
        logger.info(f"Executing new search: {query[:50]}...")
        research_ctx = self.research_service.build(query)

        if research_ctx.used:
            # Convert SourceDoc to ResearchSource
            sources = [
                ResearchSource(
                    id=s.id, title=s.title, url=s.url, fetched_at=s.fetched_at, excerpt=s.excerpt
                )
                for s in research_ctx.sources
            ]

            # Create new ResearchState
            topic = normalize_topic(prompt)
            now = datetime.now(timezone.utc).isoformat()

            new_state = ResearchState(
                topic=topic,
                query=query,
                injected_text=research_ctx.injected_text,
                sources=sources,
                created_at=now,
                last_used_at=now,
                used=True,
                cache_hit=research_ctx.cache_hit,
                error=None,
                session_id=session_id,
                mode=research_mode,
                ttl_seconds=state.ttl_seconds,
            )

            # Store new state (thread-safe)
            with self._research_lock:
                self._research_states[session_id] = new_state

            # Inject research
            injected_messages = [
                {"role": "system", "content": research_ctx.injected_text},
                *messages,
            ]

            metadata = {
                "research_used": True,
                "research_reused": False,
                "research_topic": topic,
                "research_error": None,
                "sources": [
                    {"id": s.id, "title": s.title, "url": s.url, "fetched_at": s.fetched_at}
                    for s in sources
                ],
            }
            return injected_messages, metadata
        else:
            # Search failed
            logger.warning(f"Research failed: {research_ctx.error}")
            return messages, {
                "research_used": False,
                "research_reused": False,
                "research_topic": None,
                "research_error": research_ctx.error,
                "sources": [],
            }

    def _check_browse_disclaimer(
        self, response: UnifiedResponse, research_used: bool, prompt: str = ""
    ) -> UnifiedResponse:
        """
        Guard against model claiming "no internet access" inappropriately.

        If research was used OR user explicitly requested web search,
        and model response contains disclaimer phrases, replace with error message.

        Args:
            response: UnifiedResponse from model
            research_used: Whether research was actually used
            prompt: Original user prompt (to detect explicit web requests)

        Returns:
            Potentially modified UnifiedResponse
        """
        if not response.text:
            return response

        # Check if user explicitly requested web search
        explicit_request = is_explicit_web_request(prompt) if prompt else False

        # Only check disclaimers if:
        # 1. Research was actually used, OR
        # 2. User explicitly requested web search (catches logic bugs where search should have happened)
        if not research_used and not explicit_request:
            return response

        # Expanded disclaimer phrases that indicate model ignored research or made false promises
        disclaimer_phrases = [
            # Denial phrases
            "i can't browse",
            "i don't have internet",
            "i cannot access",
            "i don't have access",  # Catches "I don't have access to real-time information"
            "i am not able to browse",
            "i cannot browse",
            "no internet access",
            "can't access the internet",
            "unable to access real-time",
            "don't have real-time",
            "do not have real-time",
            "cannot access real-time",
            "can't provide real-time",
            "cannot provide real-time",
            "don't have the ability",  # Catches any "don't have the ability to X"
            "do not have the ability",
            "don't have the ability to browse",
            "do not have the ability to browse",
            "ability to browse the internet",  # Catches full phrase
            "knowledge cutoff",
            "trained on data",
            "as an ai language model",
            "as an ai",
            "i was last updated",
            "beyond those provided",  # Catches "beyond those provided in the conversation"
            "external sources",  # Catches "access external sources"
            # False promises (saying they WILL do something they can't control)
            "i will need to access",
            "i will access",
            "i will retrieve",
            "i will check",
            "i will search",
            "i will look",
            "i will browse",
            "let me retrieve",
            "let me access",
            "let me check",
            "let me search",
            "let me look",
            "let me recheck",  # "let me recheck the sources"
            "let me re-check",
            "just a moment",  # "just a moment, please"
            "give me a moment to retrieve",
            "give me a moment to access",
            "give me a moment to check",
            "please give me a moment",
            "the system has the capability",  # Caught in earlier log
        ]

        response_lower = response.text.lower()
        found_disclaimer = None

        for phrase in disclaimer_phrases:
            if phrase in response_lower:
                found_disclaimer = phrase
                break

        if found_disclaimer:
            logger.warning(
                f"Model claimed '{found_disclaimer}' despite research being provided",
                extra={
                    "extra_fields": {
                        "provider": response.provider,
                        "model": response.model,
                        "research_used": research_used,
                        "disclaimer_found": found_disclaimer,
                    }
                },
            )

            # Replace response text with clear error message
            if explicit_request and not research_used:
                # User requested search but it didn't happen - system bug
                replacement_text = (
                    "[SYSTEM ERROR] You requested web research, but the system failed to perform it. "
                    "Please try rephrasing your request or contact support."
                )
            else:
                # Research was provided but model ignored it
                replacement_text = (
                    "[SYSTEM CORRECTION] Web research sources were provided above. "
                    "The information you're looking for may be in sources [1], [2], or [3]. "
                    "If the specific information you need isn't in those sources, please ask me to search for more sources."
                )

            # Update metadata to indicate the model error
            md = response.metadata or {}
            md["research_error"] = "model_claimed_no_internet"

            modified_response = replace(response, text=replacement_text, metadata=md)
            return modified_response

        return response

    def _check_fabrication(
        self, response: UnifiedResponse, research_used: bool, prompt: str = ""
    ) -> UnifiedResponse:
        """
        NUCLEAR CHECK: Detect if model fabricated numbers/facts without web research.

        This is the most critical safety check - prevents hallucinated financial data,
        statistics, or facts from being shown to users.

        Args:
            response: UnifiedResponse from model
            research_used: Whether research was actually used
            prompt: Original user prompt

        Returns:
            Potentially modified UnifiedResponse with error if fabrication detected
        """
        if not response.text or research_used:
            return response  # If research was used, sources are cited

        response_lower = response.text.lower()
        prompt_lower = prompt.lower() if prompt else ""

        # Detect queries that REQUIRE factual data
        factual_query_indicators = [
            "how much",
            "what was",
            "what is",
            "what were",
            "how many",
            "percentage",
            "percent",
            "return",
            "performance",
            "growth",
            "decline",
            "gained",
            "lost",
            "price",
            "value",
            "rate",
            "score",
            "number",
        ]

        requires_facts = any(ind in prompt_lower for ind in factual_query_indicators)

        if not requires_facts:
            return response  # General questions OK without research

        # Detect fabricated numbers/stats in response
        fabrication_patterns = [
            r"\d+\.?\d*%",  # Percentages: "28.7%", "5%"
            r"\$\d+",  # Dollar amounts: "$1000"
            r"\d{4}",  # Years when talking about performance: "2025"
            r"around \d+",  # "around 28"
            r"approximately \d+",  # "approximately 15"
            r"about \d+",  # "about 20"
            r"reached .* high",  # "reached new highs" without citation
            r"strong performance",  # Vague claims without data
            r"record high",  # "record highs" without citation
            r"significant growth",  # Vague claims
            r"delivered .* return",  # "delivered X% return" without citation
        ]

        import re

        has_numbers = any(re.search(pattern, response_lower) for pattern in fabrication_patterns)

        # Check if numbers are cited (has [1], [2], [3])
        has_citations = bool(re.search(r"\[\d+\]", response.text))

        if has_numbers and not has_citations:
            logger.error(
                "FABRICATION DETECTED: Model provided numbers/facts without web research",
                extra={
                    "extra_fields": {
                        "provider": response.provider,
                        "model": response.model,
                        "research_used": research_used,
                        "prompt": prompt[:100],
                        "response_preview": response.text[:200],
                    }
                },
            )

            # BLOCK THE RESPONSE
            replacement_text = (
                "[SYSTEM ERROR: FABRICATED DATA DETECTED]\n\n"
                "The AI provided numbers or facts without performing web research. "
                "This violates safety protocols.\n\n"
                "For factual queries like yours, the system MUST perform web research. "
                "Please try your query again. If the issue persists, the system may need configuration."
            )

            md = response.metadata or {}
            md["fabrication_detected"] = True
            md["fabrication_reason"] = "numbers_without_research"

            return replace(response, text=replacement_text, metadata=md)

        return response

    def _build_routing_constraints(
        self, raw: dict[str, Any] | None
    ) -> RoutingConstraints | None:
        if not raw:
            return None
        allowed_providers = raw.get("allowed_providers") or raw.get("allow_providers")
        if isinstance(allowed_providers, str):
            allowed_providers = [allowed_providers]

        return RoutingConstraints(
            max_cost_usd=raw.get("max_cost_usd"),
            max_total_latency_ms=raw.get("max_total_latency_ms"),
            preferred_provider=raw.get("preferred_provider"),
            allowed_providers=allowed_providers,
            min_context_limit=raw.get("min_context_limit"),
            json_only=bool(raw.get("json_only", False)),
            strict_format=bool(raw.get("strict_format", False)),
        )

    def _resolve_forced_tier(self, routing_mode: str) -> Tier | None:
        if routing_mode == "cheap":
            return Tier.T0
        if routing_mode == "strong":
            return Tier.T2
        return None

    def _validate_explicit_model_selection(
        self, model_type: str | None, model_name: str | None
    ) -> tuple[bool, str]:
        if not model_type or not model_name:
            return False, "Both provider and model are required for explicit model selection"
        if not self._model_registry:
            return True, ""

        candidate = self._model_registry.find_model(model_type, model_name)
        if not candidate:
            return (
                False,
                f"Model '{model_name}' for provider '{model_type}' is not configured in model_registry.yaml",
            )
        if not candidate.enabled:
            return (
                False,
                f"Model '{model_name}' for provider '{model_type}' is currently disabled",
            )
        return True, ""

    def _invoke_candidate(
        self, candidate: ModelCandidate, messages: list[dict[str, str]], **kwargs
    ) -> UnifiedResponse:
        try:
            client = self._get_client(candidate.provider, candidate.model_name)
            return client.get_completion(messages=messages, **kwargs)
        except Exception as e:
            logger.exception("Candidate invocation failed")
            return self._error_response(
                provider=candidate.provider,
                model=candidate.model_name,
                message=str(e),
                code="unknown",
            )

    def _explain_attempt_failure(self, response: UnifiedResponse, validation_reason: str) -> str:
        if response.is_error and response.error:
            return (
                f"provider_error:{response.error.code}"
                f" message={response.error.message}"
            )

        reason_map = {
            "refusal": "model_refused_request_or_system_instruction_conflict",
            "too_short": "response_below_minimum_quality_length_threshold",
            "format_violation": "response_did_not_meet_required_output_format",
            "truncated": "response_truncated_before_completion",
            "timeout": "provider_timed_out",
            "rate_limit": "provider_rate_limited_request",
            "provider_error": "provider_returned_invalid_or_error_response",
            "latency_budget": "routing_latency_budget_exceeded",
            "max_attempts": "routing_max_attempts_reached",
        }
        return reason_map.get(validation_reason, f"validation_failed:{validation_reason}")

    def _update_routing_metadata_for_attempt(
        self,
        routing_md: dict[str, Any],
        *,
        attempt_number: int,
        tier: Tier,
        candidate: ModelCandidate,
        response: UnifiedResponse,
        validation_reason: str,
        validation_ok: bool,
    ) -> None:
        status = "success" if validation_ok else "failed"
        why_worked = (
            "response_passed_validator_checks_and_returned_usable_output"
            if validation_ok
            else None
        )
        why_failed = (
            None if validation_ok else self._explain_attempt_failure(response, validation_reason)
        )

        attempt_entry = {
            "attempt_number": attempt_number,
            "tier": tier.value,
            "provider": candidate.provider,
            "model": candidate.model_name,
            "validation": validation_reason,
            "latency_ms": response.latency_ms,
            "status": status,
            "why_worked": why_worked,
            "why_failed": why_failed,
        }
        routing_md["attempts"].append(attempt_entry)

        plan_entry = None
        for item in routing_md.get("candidate_plan", []):
            if (
                item.get("provider") == candidate.provider
                and item.get("model") == candidate.model_name
                and item.get("status") == "pending"
            ):
                plan_entry = item
                break

        selected_item = {
            "attempt_number": attempt_number,
            "provider": candidate.provider,
            "model": candidate.model_name,
            "tier": tier.value,
            "status": status,
            "why_selected": (plan_entry or {}).get(
                "why_selected",
                ["selected_by_runtime_fallback_or_tier_reselection"],
            ),
            "why_worked": why_worked,
            "why_failed": why_failed,
        }

        if plan_entry:
            plan_entry["status"] = status
            plan_entry["outcome_reason"] = "validator_ok" if validation_ok else validation_reason
            plan_entry["why_worked"] = why_worked
            plan_entry["why_failed"] = why_failed
            selected_item["order"] = plan_entry.get("order")

        routing_md.setdefault("selected_sequence", []).append(selected_item)

        seq = routing_md.get("selected_sequence", [])
        routing_md["first_selected_model"] = seq[0] if len(seq) >= 1 else None
        routing_md["second_selected_model"] = seq[1] if len(seq) >= 2 else None
        routing_md["third_selected_model"] = seq[2] if len(seq) >= 3 else None

    def _run_smart_attempt_loop(
        self,
        *,
        prompt: str,
        context: UserContext | None,
        messages: list[dict[str, str]],
        routing_mode: str,
        routing_constraints: RoutingConstraints | None,
        **kwargs,
    ) -> UnifiedResponse:
        if not self._smart_router or not self._model_registry or not self._validator:
            return self._error_response(
                provider="orchestrator",
                model="smart_router",
                message="Smart routing not initialized",
                code="unknown",
            )

        start_time = time.monotonic()
        try:
            features, initial_tier, ordered_candidates, routing_md = (
                self._smart_router.route_once_plan(
                    prompt=prompt,
                    context=context,
                    routing_mode=routing_mode,
                    constraints=routing_constraints,
                )
            )
        except Exception as e:
            logger.exception("Smart routing plan failed")
            return self._error_response(
                provider="orchestrator",
                model="smart_router",
                message=str(e),
                code="unknown",
            )

        defaults = self._model_registry.routing_defaults()
        max_attempts = int(defaults.get("max_attempts", 2))
        max_latency_ms = int(defaults.get("max_total_latency_ms", 12000))
        if routing_constraints and routing_constraints.max_total_latency_ms is not None:
            max_latency_ms = int(routing_constraints.max_total_latency_ms)

        policy = FallbackPolicy(
            max_attempts=max_attempts,
            max_total_latency_ms=max_latency_ms,
            allow_escalation=True,
        )

        current_tier = initial_tier
        current_candidates = list(ordered_candidates)
        attempt_index = 0
        best_non_error: UnifiedResponse | None = None
        final_response: UnifiedResponse | None = None
        last_response: UnifiedResponse | None = None

        while attempt_index < policy.max_attempts:
            if not current_candidates:
                next_tier = None
                if self._model_registry:
                    next_tier = self._model_registry.next_tier(current_tier)
                if not next_tier:
                    break
                current_tier = next_tier
                candidates = self._model_registry.get_candidates(current_tier, routing_constraints)
                selection = self._selector.select(features, candidates, routing_constraints)
                current_candidates = [
                    selection.primary_candidate,
                    *selection.fallback_candidates,
                ]
                continue

            candidate = current_candidates.pop(0)
            resp = self._invoke_candidate(candidate, messages, **kwargs)
            prev_response = last_response
            last_response = resp
            if attempt_index > 0 and prev_response:
                resp = replace(
                    resp,
                    attempt=attempt_index + 1,
                    fallback_from=f"{prev_response.provider}:{prev_response.model}",
                )
            else:
                resp = replace(resp, attempt=attempt_index + 1)

            validation = self._validator.validate(features, routing_constraints, resp)
            self._update_routing_metadata_for_attempt(
                routing_md,
                attempt_number=attempt_index + 1,
                tier=current_tier,
                candidate=candidate,
                response=resp,
                validation_reason=validation.reason,
                validation_ok=validation.ok,
            )

            if not resp.is_error and best_non_error is None:
                best_non_error = resp

            if validation.ok:
                final_response = resp
                break

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            decision = self._fallback_manager.decide(
                current_tier=current_tier,
                validation=validation,
                attempt_index=attempt_index,
                elapsed_ms=elapsed_ms,
                remaining_same_tier_candidates=len(current_candidates),
                policy=policy,
                next_tier_fn=self._model_registry.next_tier,
            )
            if routing_md.get("selected_sequence"):
                latest_selected = routing_md["selected_sequence"][-1]
                latest_selected["next_action"] = (
                    decision.action.value if hasattr(decision.action, "value") else str(decision.action)
                )
                latest_selected["next_action_reason"] = decision.reason

            if decision.action == "retry_same_tier":
                routing_md["fallback_used"] = True
                attempt_index += 1
                continue
            if decision.action == "escalate_tier" and decision.next_tier:
                routing_md["fallback_used"] = True
                current_tier = decision.next_tier
                candidates = self._model_registry.get_candidates(current_tier, routing_constraints)
                selection = self._selector.select(features, candidates, routing_constraints)
                current_candidates = [
                    selection.primary_candidate,
                    *selection.fallback_candidates,
                ]
                attempt_index += 1
                continue

            final_response = resp
            break

        if not final_response:
            if best_non_error:
                final_response = best_non_error
            elif last_response:
                final_response = last_response
            else:
                return self._error_response(
                    provider="orchestrator",
                    model="smart_router",
                    message="No available model candidates",
                    code="unknown",
                )

        routing_md["attempt_count"] = len(routing_md["attempts"])
        routing_md["final_tier"] = current_tier.value

        md = final_response.metadata or {}
        md["routing"] = routing_md
        final_response = replace(final_response, metadata=md)

        return final_response

    # ---------- public API ----------
    def ask(
        self,
        prompt: str,
        model_type: str | None = None,
        context: UserContext | None = None,
        model_name: str | None = None,
        token_tracker: TokenTracker | None = None,
        research_mode: str = "auto",
        routing_mode: str = "smart",
        routing_constraints: dict[str, Any] | None = None,
        **kwargs,
    ) -> UnifiedResponse:
        try:
            # Optimize prompt if enabled
            optimized_prompt, opt_metadata = self._optimize_prompt_if_enabled(prompt)
            if opt_metadata.get("optimization_used"):
                logger.debug("Using optimized prompt for request")

            messages = self._build_messages(optimized_prompt, context)

            # Apply research if needed (and if service is configured)
            if self.research_service:
                messages, research_metadata = self._apply_research_if_needed(
                    prompt=optimized_prompt,
                    messages=messages,
                    research_mode=research_mode,
                    context=context,
                )
            else:
                research_metadata = {
                    "research_used": False,
                    "research_reused": False,
                    "research_topic": None,
                    "research_error": "service_not_configured",
                    "sources": [],
                }

            routing_mode_norm = (routing_mode or "").lower().strip()
            # Only use smart routing when explicitly requested.
            # Any other value (e.g., "legacy") preserves direct model invocation.
            use_smart = routing_mode_norm in {"smart", "cheap", "strong"}
            explicit_model_selected = bool(model_type and model_name)

            if explicit_model_selected:
                is_valid, validation_error = self._validate_explicit_model_selection(
                    model_type, model_name
                )
                if not is_valid:
                    return self._error_response(
                        provider=model_type or "unknown",
                        model=model_name or "unknown",
                        message=validation_error,
                        code="bad_request",
                    )

                client = self._get_client(model_type, model_name)
                resp = client.get_completion(messages=messages, **kwargs)
                md = resp.metadata or {}
                md["routing"] = {
                    "mode": "explicit",
                    "initial_tier": "N/A",
                    "final_tier": "N/A",
                    "attempt_count": 1,
                    "fallback_used": False,
                    "attempts": [
                        {
                            "tier": "N/A",
                            "provider": model_type,
                            "model": model_name,
                            "validation": "ok",
                            "latency_ms": resp.latency_ms,
                        }
                    ],
                    "decision_reasons": ["explicit_model_selection"],
                }
                resp = replace(resp, metadata=md)
            elif use_smart:
                constraints = self._build_routing_constraints(routing_constraints)
                if model_type:
                    if constraints is None:
                        constraints = RoutingConstraints(preferred_provider=model_type)
                    elif not constraints.preferred_provider:
                        constraints = replace(constraints, preferred_provider=model_type)

                resp = self._run_smart_attempt_loop(
                    prompt=optimized_prompt,
                    context=context,
                    messages=messages,
                    routing_mode=routing_mode_norm,
                    routing_constraints=constraints,
                    **kwargs,
                )
            else:
                if not model_type:
                    return self._error_response(
                        provider="orchestrator",
                        model=model_name or "default",
                        message="provider is required when routing_mode is not smart/cheap/strong",
                        code="bad_request",
                    )

                if model_name:
                    is_valid, validation_error = self._validate_explicit_model_selection(
                        model_type, model_name
                    )
                    if not is_valid:
                        return self._error_response(
                            provider=model_type,
                            model=model_name,
                            message=validation_error,
                            code="bad_request",
                        )

                client = self._get_client(model_type, model_name)
                resp = client.get_completion(messages=messages, **kwargs)

            # Merge research and optimization metadata into response
            md = resp.metadata or {}
            merged_md = {**md, **research_metadata, **opt_metadata, "research_mode": research_mode}
            resp = replace(resp, metadata=merged_md)

            # Check for browse disclaimer if research was used or explicitly requested
            research_used = research_metadata.get("research_used", False)
            if self._enable_browse_disclaimer_check:
                resp = self._check_browse_disclaimer(resp, research_used, optimized_prompt)

            # CRITICAL: Check for fabricated numbers/facts
            if self._enable_fabrication_check:
                resp = self._check_fabrication(resp, research_used, optimized_prompt)

            # Update token tracker here (business layer)
            if token_tracker:
                token_tracker.update(resp)

            return resp

        except Exception as e:
            logger.exception("ask() failed")
            return self._error_response(
                provider=model_type or "orchestrator",
                model=model_name or "default",
                message=str(e),
                code="unknown",
            )

    def compare(
        self,
        prompt: str,
        models_list: list[dict[str, str]],
        context: UserContext | None = None,
        timeout_s: float | None = None,
        token_tracker: TokenTracker | None = None,
        research_mode: str = "auto",
        request_group_id: str | None = None,
        **kwargs,
    ) -> MultiUnifiedResponse:
        request_group_id = request_group_id or str(uuid.uuid4())
        responses: list[UnifiedResponse] = []

        try:
            # Optimize prompt if enabled (ONCE for all models - fair comparison)
            optimized_prompt, opt_metadata = self._optimize_prompt_if_enabled(prompt)
            if opt_metadata.get("optimization_used"):
                logger.debug("Using optimized prompt for comparison")

            messages = self._build_messages(optimized_prompt, context)

            # Apply research ONCE for all models (compare fairness)
            if self.research_service:
                messages, research_metadata = self._apply_research_if_needed(
                    prompt=optimized_prompt,
                    messages=messages,
                    research_mode=research_mode,
                    context=context,
                )
            else:
                research_metadata = {
                    "research_used": False,
                    "research_reused": False,
                    "research_topic": None,
                    "research_error": "service_not_configured",
                    "sources": [],
                }

            clients: list[BaseAIClient] = []
            client_meta: list[dict[str, str]] = []

            for cfg in models_list:
                provider = (cfg.get("provider") or "").lower().strip()
                model = (cfg.get("model") or "").strip()

                if not provider or not model:
                    responses.append(
                        self._error_response(
                            provider=provider or "unknown",
                            model=model or "unknown",
                            message=f"Invalid model config: {cfg}",
                            code="bad_request",
                        )
                    )
                    continue

                try:
                    c = self._get_client(provider, model)
                    clients.append(c)
                    client_meta.append({"provider": provider, "model": model})
                except Exception as init_err:
                    responses.append(
                        self._error_response(
                            provider=provider,
                            model=model,
                            message=str(init_err),
                            code="auth" if "API_KEY" in str(init_err) else "unknown",
                        )
                    )

            # If we have no valid clients, still return a MultiUnifiedResponse (no exceptions)
            if not clients:
                if token_tracker:
                    for r in responses:
                        token_tracker.update(r)
                return MultiUnifiedResponse.from_responses(request_group_id, prompt, responses)

            # Execute comparisons with research-injected messages (parallel inside MultiModelOrchestrator)
            result = self._multi_orchestrator.get_comparisons_sync(
                prompt=prompt,
                clients=clients,
                timeout_s=timeout_s,
                request_group_id=request_group_id,
                messages=messages,  # Pass research-injected messages to all models
                **kwargs,
            )

            # Merge init-time failures + runtime results
            responses.extend(result.responses)

            # Merge research metadata into each response and check for browse disclaimer + fabrication
            research_used = research_metadata.get("research_used", False)
            updated_responses = []
            for resp in responses:
                md = resp.metadata or {}
                merged_md = {**md, **research_metadata, "research_mode": research_mode}
                resp_with_metadata = replace(resp, metadata=merged_md)
                # Check for browse disclaimer if research was used or explicitly requested
                resp_checked = resp_with_metadata
                if self._enable_browse_disclaimer_check:
                    resp_checked = self._check_browse_disclaimer(
                        resp_with_metadata, research_used, prompt
                    )
                # Check for fabricated numbers/facts
                resp_final = resp_checked
                if self._enable_fabrication_check:
                    resp_final = self._check_fabrication(resp_checked, research_used, prompt)
                updated_responses.append(resp_final)

            if token_tracker:
                for r in updated_responses:
                    token_tracker.update(r)

            return MultiUnifiedResponse.from_responses(request_group_id, prompt, updated_responses)

        except Exception as e:
            logger.exception("compare() failed")
            responses.append(
                self._error_response(
                    provider="orchestrator",
                    model="compare",
                    message=str(e),
                    code="unknown",
                )
            )
            if token_tracker:
                for r in responses:
                    token_tracker.update(r)
            return MultiUnifiedResponse.from_responses(request_group_id, prompt, responses)

    # --- keep these helpers (your CLI uses them) ---
    def create_token_tracker(self, model_type: str, model_name: str | None = None) -> TokenTracker:
        return TokenTracker(model_type=model_type, model_name=model_name)

    def create_cost_calculator(
        self, model_type: str, model_name: str | None = None
    ) -> CostCalculator:
        if not model_name:
            if model_type.lower() == "openai":
                model_name = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-3.5-turbo")
            elif model_type.lower() == "gemini":
                model_name = os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.5-flash-lite")
            elif model_type.lower() == "deepseek":
                model_name = os.getenv("DEFAULT_DEEPSEEK_MODEL", "deepseek-chat")
            elif model_type.lower() == "grok":
                model_name = os.getenv("DEFAULT_GROK_MODEL", "grok-4-latest")
        return CostCalculator(model_type=model_type, model_name=model_name)
