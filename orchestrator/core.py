"""
CortexOrchestrator - Core business logic layer for CortexAI.

Key guarantees:
- CLI/API layers stay thin (no provider imports there)
- No exceptions bubble up from ask() / compare()
- TokenTracker updates happen here (business layer)
"""

import os
import uuid
import hashlib
import threading
from dataclasses import replace
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from api.base_client import BaseAIClient
from models.unified_response import UnifiedResponse, MultiUnifiedResponse, NormalizedError, TokenUsage
from models.user_context import UserContext
from utils.token_tracker import TokenTracker
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger
from utils.prompt_optimizer import PromptOptimizer
from orchestrator.multi_orchestrator import MultiModelOrchestrator
from tools.web import create_research_service_from_env
from tools.web.intent import (
    should_use_web, is_followup_meta, is_same_topic_followup, rewrite_query,
    is_explicit_web_request, is_meta_followup, is_short_year_followup,
    build_anchored_query, should_reuse_research, should_search,
    sanitize_query, normalize_topic, wants_more_sources, is_meta_clarification
)
from tools.web.session_state import get_session_store
from tools.web.research_state import ResearchState, ResearchSource, create_initial_state, compute_topic_key

logger = get_logger(__name__)


class CortexOrchestrator:
    def __init__(self):
        self._multi_orchestrator = MultiModelOrchestrator()
        self._client_cache: Dict[str, BaseAIClient] = {}
        self._research_states: Dict[str, Any] = {}  # session_id -> ResearchState
        self._research_lock = threading.Lock()  # thread-safe access to states

        # Initialize prompt optimizer (optional - controlled by env var)
        self._prompt_optimizer = None
        if os.getenv('ENABLE_PROMPT_OPTIMIZATION', 'false').lower() == 'true':
            try:
                provider = os.getenv('PROMPT_OPTIMIZER_PROVIDER', 'gemini')
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

    # ---------- helpers ----------

    def _error_response(
        self,
        *,
        provider: str,
        model: str,
        message: str,
        code: str = "unknown",
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
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

    def _get_client(self, model_type: str, model_name: Optional[str] = None) -> BaseAIClient:
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

    def _build_messages(self, prompt: str, context: Optional[UserContext]) -> List[Dict[str, str]]:
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

These rules prevent misinformation. Follow them carefully."""
        }

        if context and context.conversation_history:
            msgs = context.get_messages()
            msgs.append({"role": "user", "content": prompt})
            # Inject system instruction at the beginning
            return [system_instruction] + msgs
        return [system_instruction, {"role": "user", "content": prompt}]

    def _generate_session_id(self, messages: List[Dict[str, str]]) -> str:
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

    def _get_session_id(self, context: Optional[UserContext], messages: List[Dict[str, str]]) -> str:
        """
        Get session ID from context or generate from messages.

        Args:
            context: UserContext (may have session_id)
            messages: Conversation messages

        Returns:
            Session ID string
        """
        if context and hasattr(context, 'session_id') and context.session_id:
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
            
            if "error" in result and result["error"]:
                logger.warning(f"Prompt optimization failed: {result['error']['message']}")
                return prompt, {"optimization_error": result["error"]["message"]}
            
            optimized = result.get("optimized_prompt", prompt)
            metadata = {
                "optimization_used": True,
                "original_prompt": prompt,
                "optimization_steps": result.get("steps", []),
                "optimization_metrics": result.get("metrics", {})
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
                    session_id=session_id,
                    mode=research_mode,
                    ttl_seconds=ttl_seconds
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
        messages: List[Dict[str, str]],
        research_mode: str,
        context: Optional[UserContext] = None
    ) -> tuple[List[Dict[str, str]], Dict[str, Any]]:
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
            injected_messages = [
                {"role": "system", "content": state.injected_text},
                *messages
            ]

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
                    {
                        "id": s.id,
                        "title": s.title,
                        "url": s.url,
                        "fetched_at": s.fetched_at
                    }
                    for s in state.sources
                ]
            }
            return injected_messages, metadata

        # 4) Check if we should perform new search
        should_do_search = should_search(prompt, research_mode, state)
        logger.info(f"Research decision - search: {should_do_search}, mode: {research_mode}, prompt: {prompt[:50]}...")

        if not should_do_search:
            logger.info(f"No research needed (mode={research_mode})")
            return messages, {
                "research_used": False,
                "research_reused": False,
                "research_topic": None,
                "research_error": None,
                "sources": []
            }

        # 5) Perform new search
        if not self.research_service:
            return messages, {
                "research_used": False,
                "research_reused": False,
                "research_topic": None,
                "research_error": "service_not_configured",
                "sources": []
            }

        # Extract PREVIOUS user message for context (helps with meta-commands like "check again")
        # Skip the current prompt (last user message) and get the one before it
        last_user_msg = None
        user_messages = [msg["content"] for msg in messages if msg.get("role") == "user" and msg.get("content")]
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
                "sources": []
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
                    id=s.id,
                    title=s.title,
                    url=s.url,
                    fetched_at=s.fetched_at,
                    excerpt=s.excerpt
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
                ttl_seconds=state.ttl_seconds
            )

            # Store new state (thread-safe)
            with self._research_lock:
                self._research_states[session_id] = new_state

            # Inject research
            injected_messages = [
                {"role": "system", "content": research_ctx.injected_text},
                *messages
            ]

            metadata = {
                "research_used": True,
                "research_reused": False,
                "research_topic": topic,
                "research_error": None,
                "sources": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "url": s.url,
                        "fetched_at": s.fetched_at
                    }
                    for s in sources
                ]
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
                "sources": []
            }

    def _check_browse_disclaimer(self, response: UnifiedResponse, research_used: bool, prompt: str = "") -> UnifiedResponse:
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
                extra={"extra_fields": {
                    "provider": response.provider,
                    "model": response.model,
                    "research_used": research_used,
                    "disclaimer_found": found_disclaimer
                }}
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

    def _check_fabrication(self, response: UnifiedResponse, research_used: bool, prompt: str = "") -> UnifiedResponse:
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
            "how much", "what was", "what is", "what were",
            "how many", "percentage", "percent", "return",
            "performance", "growth", "decline", "gained", "lost",
            "price", "value", "rate", "score", "number"
        ]

        requires_facts = any(ind in prompt_lower for ind in factual_query_indicators)

        if not requires_facts:
            return response  # General questions OK without research

        # Detect fabricated numbers/stats in response
        fabrication_patterns = [
            r'\d+\.?\d*%',  # Percentages: "28.7%", "5%"
            r'\$\d+',  # Dollar amounts: "$1000"
            r'\d{4}',  # Years when talking about performance: "2025"
            r'around \d+',  # "around 28"
            r'approximately \d+',  # "approximately 15"
            r'about \d+',  # "about 20"
            r'reached .* high',  # "reached new highs" without citation
            r'strong performance',  # Vague claims without data
            r'record high',  # "record highs" without citation
            r'significant growth',  # Vague claims
            r'delivered .* return',  # "delivered X% return" without citation
        ]

        import re
        has_numbers = any(re.search(pattern, response_lower) for pattern in fabrication_patterns)

        # Check if numbers are cited (has [1], [2], [3])
        has_citations = bool(re.search(r'\[\d+\]', response.text))

        if has_numbers and not has_citations:
            logger.error(
                "FABRICATION DETECTED: Model provided numbers/facts without web research",
                extra={"extra_fields": {
                    "provider": response.provider,
                    "model": response.model,
                    "research_used": research_used,
                    "prompt": prompt[:100],
                    "response_preview": response.text[:200]
                }}
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

    # ---------- public API ----------
    def ask(
        self,
        prompt: str,
        model_type: str,
        context: Optional[UserContext] = None,
        model_name: Optional[str] = None,
        token_tracker: Optional[TokenTracker] = None,
        research_mode: str = "auto",
        **kwargs,
    ) -> UnifiedResponse:
        try:
            # Optimize prompt if enabled
            optimized_prompt, opt_metadata = self._optimize_prompt_if_enabled(prompt)
            if opt_metadata.get("optimization_used"):
                logger.debug(f"Using optimized prompt for request")
            
            client = self._get_client(model_type, model_name)
            messages = self._build_messages(optimized_prompt, context)

            # Apply research if needed (and if service is configured)
            if self.research_service:
                messages, research_metadata = self._apply_research_if_needed(
                    prompt=optimized_prompt,
                    messages=messages,
                    research_mode=research_mode,
                    context=context
                )
            else:
                research_metadata = {
                    "research_used": False,
                    "research_reused": False,
                    "research_topic": None,
                    "research_error": "service_not_configured",
                    "sources": []
                }

            resp = client.get_completion(messages=messages, **kwargs)

            # Merge research and optimization metadata into response
            md = resp.metadata or {}
            merged_md = {**md, **research_metadata, **opt_metadata}
            resp = replace(resp, metadata=merged_md)

            # Check for browse disclaimer if research was used or explicitly requested
            research_used = research_metadata.get("research_used", False)
            resp = self._check_browse_disclaimer(resp, research_used, optimized_prompt)

            # CRITICAL: Check for fabricated numbers/facts
            resp = self._check_fabrication(resp, research_used, optimized_prompt)

            # Update token tracker here (business layer)
            if token_tracker:
                token_tracker.update(resp)

            return resp

        except Exception as e:
            logger.exception("ask() failed")
            return self._error_response(
                provider=model_type,
                model=model_name or "default",
                message=str(e),
                code="unknown",
            )

    def compare(
        self,
        prompt: str,
        models_list: List[Dict[str, str]],
        context: Optional[UserContext] = None,
        timeout_s: Optional[float] = None,
        token_tracker: Optional[TokenTracker] = None,
        research_mode: str = "auto",
        **kwargs,
    ) -> MultiUnifiedResponse:
        request_group_id = str(uuid.uuid4())
        responses: List[UnifiedResponse] = []

        try:
            # Optimize prompt if enabled (ONCE for all models - fair comparison)
            optimized_prompt, opt_metadata = self._optimize_prompt_if_enabled(prompt)
            if opt_metadata.get("optimization_used"):
                logger.debug(f"Using optimized prompt for comparison")
            
            messages = self._build_messages(optimized_prompt, context)

            # Apply research ONCE for all models (compare fairness)
            if self.research_service:
                messages, research_metadata = self._apply_research_if_needed(
                    prompt=optimized_prompt,
                    messages=messages,
                    research_mode=research_mode,
                    context=context
                )
            else:
                research_metadata = {
                    "research_used": False,
                    "research_reused": False,
                    "research_topic": None,
                    "research_error": "service_not_configured",
                    "sources": []
                }

            clients: List[BaseAIClient] = []
            client_meta: List[Dict[str, str]] = []

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
                merged_md = {**md, **research_metadata}
                resp_with_metadata = replace(resp, metadata=merged_md)
                # Check for browse disclaimer if research was used or explicitly requested
                resp_checked = self._check_browse_disclaimer(resp_with_metadata, research_used, prompt)
                # Check for fabricated numbers/facts
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
    def create_token_tracker(self, model_type: str, model_name: Optional[str] = None) -> TokenTracker:
        return TokenTracker(model_type=model_type, model_name=model_name)

    def create_cost_calculator(self, model_type: str, model_name: Optional[str] = None) -> CostCalculator:
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
