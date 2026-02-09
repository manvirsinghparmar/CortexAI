import os
import sys
import threading
import time
from uuid import UUID

from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Import configuration
MODEL_TYPE = os.getenv("MODEL_TYPE", "openai").lower()
COMPARE_MODE = os.getenv("COMPARE_MODE", "false").lower() == "true"
RESEARCH_MODE = os.getenv("RESEARCH_MODE", "auto").lower()  # Default to 'auto'

# Import orchestrator and utilities
from config.config import COMPARE_TARGETS
from context.conversation_manager import ConversationManager
from models.user_context import UserContext
from orchestrator.core import CortexOrchestrator
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger

# Database imports (with optional support - won't crash if DB not configured)
DB_ENABLED = False
try:
    from db import (
        check_usage_limit,
        create_llm_request,
        create_llm_response,
        create_session,
        get_active_session,
        get_db,
        get_or_create_cli_user,
        get_session_messages,
        save_compare_summary,
        save_message,
        update_session_timestamp,
        upsert_usage_daily,
    )

    # Check if DATABASE_URL is set
    if os.getenv("DATABASE_URL"):
        DB_ENABLED = True
except ImportError:
    # DB package not available or dependencies not installed
    pass
except Exception:
    # DATABASE_URL not set or other configuration issue
    pass

logger = get_logger(__name__)


def _convert_to_user_context(conversation: ConversationManager) -> UserContext:
    """
    Convert ConversationManager to UserContext for orchestrator.
    """
    return UserContext(conversation_history=conversation.get_messages())


def _persist_single_interaction(
    db_session, user_id: UUID, db_session_id: UUID, user_input: str, response, mode: str = "ask"
) -> None:
    """
    Persist a single LLM interaction to database in ONE TRANSACTION.

    Args:
        db_session: Database session
        user_id: User ID
        db_session_id: Session ID
        user_input: User's prompt
        response: UnifiedResponse object
        mode: Mode ('ask' or 'compare')
    """
    if not db_session or not user_id or not db_session_id:
        return

    try:
        # BEGIN TRANSACTION - All writes together
        # 1. Save user message
        save_message(db_session, db_session_id, "user", user_input)

        # 2. Persist LLM request
        llm_request_id = create_llm_request(
            db_session,
            user_id=user_id,
            request_id=response.request_id,
            route_mode=mode,
            provider=response.provider,
            model=response.model,
            prompt=user_input,
            session_id=db_session_id,
            api_key_id=None,  # CLI has no API key
            store_prompt=False,  # Privacy
        )

        # 3. Persist LLM response
        create_llm_response(db_session, llm_request_id, response)

        # 4. Save assistant message (only if not error)
        if not response.is_error:
            save_message(db_session, db_session_id, "assistant", response.text)

        # 5. Update session timestamp
        update_session_timestamp(db_session, db_session_id)

        # 6. Update usage stats
        upsert_usage_daily(
            db_session,
            user_id=user_id,
            total_tokens=response.token_usage.total_tokens,
            estimated_cost=response.estimated_cost,
        )

        # COMMIT - All-or-nothing
        db_session.commit()

        logger.info(
            f"Persisted single interaction: request_id={response.request_id}, "
            f"session_id={db_session_id}"
        )

    except Exception as e:
        # Rollback ALL changes if any write fails
        db_session.rollback()
        logger.error(f"Failed to persist single interaction to database: {e}")


def _persist_compare_interaction(
    db_session,
    user_id: UUID,
    db_session_id: UUID,
    user_input: str,
    multi_resp,
    mode: str = "compare",
) -> None:
    """
    Persist a compare mode interaction to database in ONE TRANSACTION.

    Args:
        db_session: Database session
        user_id: User ID
        db_session_id: Session ID
        user_input: User's prompt
        multi_resp: MultiUnifiedResponse object
        mode: Mode (default: 'compare')
    """
    if not db_session or not user_id or not db_session_id:
        return

    try:
        # BEGIN TRANSACTION - All writes together
        # 1. Save user message
        save_message(db_session, db_session_id, "user", user_input)

        # 2. Persist N LLM requests + responses (one per model)
        for response in multi_resp.responses:
            llm_request_id = create_llm_request(
                db_session,
                user_id=user_id,
                request_id=response.request_id,
                route_mode=mode,
                provider=response.provider,
                model=response.model,
                prompt=user_input,
                session_id=db_session_id,
                api_key_id=None,  # CLI has no API key
                store_prompt=False,  # Privacy
            )
            create_llm_response(db_session, llm_request_id, response)

        # 3. Save ONE assistant message (compare summary)
        if multi_resp.success_count > 0:
            # Find first successful response for selected index
            selected_index = 0
            for i, resp in enumerate(multi_resp.responses):
                if not resp.is_error:
                    selected_index = i
                    break

            save_compare_summary(
                db_session, db_session_id, multi_resp.responses, selected_model_index=selected_index
            )

        # 4. Update session timestamp
        update_session_timestamp(db_session, db_session_id)

        # 5. Update usage stats
        upsert_usage_daily(
            db_session,
            user_id=user_id,
            total_tokens=multi_resp.total_tokens,
            estimated_cost=multi_resp.total_cost,
        )

        # COMMIT - All-or-nothing
        db_session.commit()

        logger.info(
            f"Persisted compare interaction: request_group_id={multi_resp.request_group_id}, "
            f"session_id={db_session_id}"
        )

    except Exception as e:
        # Rollback ALL changes if any write fails
        db_session.rollback()
        logger.error(f"Failed to persist compare interaction to database: {e}")


def prompt_research_mode() -> str:
    """
    Prompt user to select research mode.
    Returns: 'off' or 'on'
    """
    print("\n=== Select Research Mode ===")
    print("1. off - No web research (fastest, cheapest)")
    print("2. on  - Always use web research (recommended)")
    print()

    while True:
        choice = input("Enter your choice (1/2) or press Enter for default [on]: ").strip()

        if not choice:
            return "on"

        if choice == "1":
            return "off"
        elif choice == "2":
            return "on"
        else:
            print("Invalid choice. Please enter 1 or 2.")


def display_research_info(response) -> None:
    """
    Display research metadata if research was used.
    """
    if not response.metadata:
        return

    research_used = response.metadata.get("research_used", False)
    research_reused = response.metadata.get("research_reused", False)
    sources = response.metadata.get("sources", [])
    research_error = response.metadata.get("research_error")
    research_topic = response.metadata.get("research_topic")

    # Only show error if search failed (not for mode_off or service_not_configured in normal flow)
    if research_error and research_error not in ["service_not_configured"]:
        if research_error != "invalid_query":  # Don't show blocked garbage queries to user
            print(f"\033[93m[Research Error: {research_error}]\033[0m")
        return

    if research_used and sources:
        reuse_label = " (reused)" if research_reused else ""
        print(f"\033[92m[✓ Web Research Used{reuse_label}]\033[0m")
        if research_topic:
            print(f"\033[92m[Topic: {research_topic}]\033[0m")
        print(f"\033[92m[Found {len(sources)} sources]\033[0m")
        print("\n📚 Sources:")
        for source in sources:
            print(f"  [{source['id']}] {source['title']}")
            print(f"      {source['url']}")
        print()


def show_loading_animation(stop_event: threading.Event) -> None:
    """
    Show a loading animation in the console.
    """
    while not stop_event.is_set():
        for char in "|/-\\":
            if stop_event.is_set():
                break
            sys.stdout.write(f"\r\033[93mThinking {char}\033[0m")
            sys.stdout.flush()
            time.sleep(0.1)

    # Clear the loading line
    sys.stdout.write("\r" + " " * 20 + "\r")
    sys.stdout.flush()


def main():
    """
    CLI entry point - thin layer that handles user I/O.
    All business logic is delegated to CortexOrchestrator.
    """
    token_tracker = None
    cost_calculator: CostCalculator | None = None
    conversation = None
    session_total_cost = 0.0
    session_total_tokens = 0

    # Database session and state
    db_session = None
    user_id: UUID | None = None
    db_session_id: UUID | None = None

    logger.info(
        "Application starting",
        extra={
            "extra_fields": {
                "model_type": MODEL_TYPE,
                "compare_mode": COMPARE_MODE,
                "db_enabled": DB_ENABLED,
            }
        },
    )

    try:
        orchestrator = CortexOrchestrator()

        # Track tokens via orchestrator (pass token_tracker into ask/compare)
        token_tracker = orchestrator.create_token_tracker(MODEL_TYPE)

        # CostCalculator is meaningful only in Single Mode (single provider pricing)
        cost_calculator = orchestrator.create_cost_calculator(MODEL_TYPE)

        # Initialize database if enabled
        if DB_ENABLED:
            try:
                db_session = next(get_db())
                user_id = get_or_create_cli_user(
                    db_session, email="cli@cortexai.local", display_name="CLI User"
                )
                db_session.commit()

                # Check for existing session
                db_session_id = get_active_session(
                    db_session, user_id, mode="compare" if COMPARE_MODE else "ask"
                )

                if db_session_id:
                    # Ask user if they want to resume
                    messages = get_session_messages(db_session, db_session_id, limit=3)
                    if messages:
                        print(
                            f"\n\033[92mFound existing session with {len(messages)} messages.\033[0m"
                        )
                        print("Last messages:")
                        for msg in messages[-2:]:
                            role = msg["role"].capitalize()
                            content = (
                                str(msg["content"])[:80] + "..."
                                if len(str(msg["content"])) > 80
                                else str(msg["content"])
                            )
                            print(f"  {role}: {content}")

                        resume = input("\nResume this session? (y/n): ").lower()
                        if resume != "y":
                            db_session_id = None

                # Create new session if needed
                if not db_session_id:
                    mode = "compare" if COMPARE_MODE else "ask"
                    db_session_id = create_session(db_session, user_id, mode=mode, title="CLI Chat")
                    db_session.commit()
                    print(
                        f"\033[92mCreated new database session: {str(db_session_id)[:8]}...\033[0m"
                    )
                else:
                    print(f"\033[92mResuming database session: {str(db_session_id)[:8]}...\033[0m")

                logger.info(
                    f"Database session initialized: user_id={user_id}, session_id={db_session_id}"
                )

            except Exception as e:
                logger.error(
                    f"Database initialization failed: {e}. Continuing without DB persistence."
                )
                db_session = None
                user_id = None
                db_session_id = None

        # Initialize conversation manager with DB support
        conversation = ConversationManager(db=db_session)
        if DB_ENABLED and db_session_id:
            conversation.set_session(db_session_id, db_session)

        if COMPARE_MODE and not COMPARE_TARGETS:
            print("ERROR: COMPARE_MODE=true but no COMPARE_TARGETS configured in config.py")
            print("Please configure COMPARE_TARGETS or set COMPARE_MODE=false\n")
            return

        logger.info(
            "Initialized CLI session",
            extra={
                "extra_fields": {
                    "max_messages": conversation.max_messages,
                    "compare_mode": COMPARE_MODE,
                }
            },
        )

        # Prompt user for research mode preference
        selected_research_mode = prompt_research_mode()
        print(f"\033[92m✓ Research Mode: {selected_research_mode}\033[0m")

        mode_text = "Compare Mode" if COMPARE_MODE else f"Single Model ({MODEL_TYPE.upper()})"
        print(f"\n=== CortexAI CLI ({mode_text}) ===")
        print("Type 'exit' to quit, 'stats' for session stats, 'help' for commands\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("exit", "quit"):
                    print("\nGoodbye!")
                    break

                if user_input.lower() == "stats":
                    logger.debug("User requested session statistics")
                    print("\n=== Session Statistics ===")
                    print(token_tracker.format_summary())

                    if COMPARE_MODE:
                        print(f"\nSession Total Tokens: {session_total_tokens}")
                        print(f"Session Total Cost: ${session_total_cost:.6f}")
                    else:
                        print(f"\n{cost_calculator.format_summary()}")

                    print(f"\nLast updated: {token_tracker.get_summary()['timestamp']}\n")
                    continue

                if user_input.lower() == "/reset":
                    conversation.reset(keep_system_prompt=True)
                    print("\n[Conversation history cleared]\n")
                    logger.info("User reset conversation history")
                    continue

                if user_input.lower() == "/history":
                    print(f"\n{conversation.get_conversation_summary(last_n=10)}\n")
                    logger.debug("User requested conversation history")
                    continue

                if user_input.lower() == "/new" or user_input.lower() == "new":
                    if DB_ENABLED and db_session and user_id:
                        mode = "compare" if COMPARE_MODE else "ask"
                        db_session_id = create_session(
                            db_session, user_id, mode=mode, title="CLI Chat"
                        )
                        db_session.commit()
                        conversation.reset(keep_system_prompt=True)
                        conversation.set_session(db_session_id, db_session)
                        print(
                            f"\n\033[92m✓ Created new database session: {str(db_session_id)[:8]}...\033[0m\n"
                        )
                    else:
                        conversation.reset(keep_system_prompt=True)
                        print("\n\033[92m✓ Created new session (DB not enabled)\033[0m\n")
                    logger.info("User created new session")
                    continue

                if user_input.lower() == "/dbstats" and DB_ENABLED and db_session and user_id:
                    from db.repository import get_usage_daily

                    usage = get_usage_daily(db_session, user_id)
                    if usage:
                        print("\n=== Database Usage (Today) ===")
                        print(f"Requests: {usage['total_requests']}")
                        print(f"Tokens: {usage['total_tokens']:,}")
                        print(f"Cost: ${float(usage['total_cost']):.6f}\n")
                    else:
                        print("\n\033[93mNo database usage today yet.\033[0m\n")
                    continue

                if user_input.lower() == "help":
                    print("\n=== Available Commands ===")
                    print("help          - Show this help message")
                    print("stats         - Show token usage statistics")
                    print("/reset        - Clear conversation history")
                    print("/history      - Show recent conversation")
                    print("/new          - Create new session")
                    if DB_ENABLED:
                        print("/dbstats      - Show database usage statistics")
                    print("exit/quit     - Exit the program")
                    if COMPARE_MODE:
                        print("\nCurrent Mode: Compare Mode (COMPARE_MODE=true)")
                        print("All prompts are sent to multiple models for comparison")
                    else:
                        print(f"\nCurrent Mode: Single Model ({MODEL_TYPE.upper()})")
                        print("Set COMPARE_MODE=true in .env to enable multi-model comparison")
                    print(f"\nResearch Mode: {selected_research_mode}")
                    print("  - off  : No web research")
                    print(
                        "  - auto : Research for current events/news (keywords: latest, recent, 2026, etc.)"
                    )
                    print("  - on   : Always research")

                    # Show prompt optimization status
                    if os.getenv("ENABLE_PROMPT_OPTIMIZATION", "false").lower() == "true":
                        provider = os.getenv("PROMPT_OPTIMIZER_PROVIDER", "gemini")
                        print(f"\nPrompt Optimization: ENABLED (using {provider.upper()})")
                        print("  All prompts are automatically optimized before sending to AI")
                    else:
                        print("\nPrompt Optimization: DISABLED")
                        print("  Set ENABLE_PROMPT_OPTIMIZATION=true in .env to enable")

                    print()
                    continue

                # ========================================================================
                # STEP 1: Usage Enforcement (Read-Only Check)
                # ========================================================================
                if DB_ENABLED and db_session and user_id:
                    token_cap = os.getenv("DAILY_TOKEN_CAP")
                    cost_cap = os.getenv("DAILY_COST_CAP")

                    if token_cap or cost_cap:
                        limit_check = check_usage_limit(
                            db_session,
                            user_id,
                            token_cap=int(token_cap) if token_cap else None,
                            cost_cap=float(cost_cap) if cost_cap else None,
                        )

                        if not limit_check["allowed"]:
                            print(f"\n\033[91m❌ {limit_check['reason']}\033[0m")
                            continue

                # Add user message to conversation
                conversation.add_user(user_input)

                # Loading animation
                stop_animation = threading.Event()
                loading_thread = threading.Thread(
                    target=show_loading_animation, args=(stop_animation,)
                )
                loading_thread.daemon = True
                loading_thread.start()

                try:
                    context = _convert_to_user_context(conversation)

                    if COMPARE_MODE:
                        # ===== COMPARE MODE =====
                        multi_resp = orchestrator.compare(
                            prompt=user_input,
                            models_list=COMPARE_TARGETS,
                            context=context,
                            token_tracker=token_tracker,
                            research_mode=selected_research_mode,
                        )

                        stop_animation.set()
                        loading_thread.join()

                        # Persist to database (compare mode)
                        if DB_ENABLED and db_session and user_id and db_session_id:
                            _persist_compare_interaction(
                                db_session,
                                user_id,
                                db_session_id,
                                user_input,
                                multi_resp,
                                mode="compare",
                            )

                        if multi_resp.success_count == 0:
                            print("\n=== All Models Failed ===\n")
                            for i, resp in enumerate(multi_resp.responses, 1):
                                print(f"[{i}] {resp.provider.upper()}/{resp.model}")
                                print(f"    [ERROR] {resp.error.code}: {resp.error.message}\n")

                            conversation.pop_last_user()
                            continue

                        print("\n=== Comparison Results ===\n")

                        # Display research info (from first response, as all share same research)
                        if multi_resp.responses:
                            display_research_info(multi_resp.responses[0])

                        first_successful_response = None

                        for i, resp in enumerate(multi_resp.responses, 1):
                            print(f"[{i}] {resp.provider.upper()}/{resp.model}")
                            print(
                                f"    Latency: {resp.latency_ms}ms | "
                                f"Tokens: {resp.token_usage.total_tokens} | "
                                f"Cost: ${resp.estimated_cost:.6f}"
                            )

                            if resp.is_error:
                                print(f"    [ERROR] {resp.error.code}: {resp.error.message}\n")
                            else:
                                if first_successful_response is None:
                                    first_successful_response = resp.text

                                text_preview = (
                                    resp.text if len(resp.text) <= 200 else resp.text[:200] + "..."
                                )
                                print(f"    Response: {text_preview}\n")

                        if first_successful_response:
                            conversation.add_assistant(first_successful_response)

                        # Session totals (compare)
                        session_total_cost += multi_resp.total_cost
                        session_total_tokens += multi_resp.total_tokens

                        print("=== Summary ===")
                        print(f"Successful: {multi_resp.success_count}/{len(multi_resp.responses)}")
                        print(f"Failed: {multi_resp.error_count}/{len(multi_resp.responses)}")
                        print(f"Total Tokens: {multi_resp.total_tokens}")
                        print(f"Total Cost: ${multi_resp.total_cost:.6f}")
                        print(f"Session Total Cost: ${session_total_cost:.6f}")
                        print(f"Session Total Tokens: {session_total_tokens}\n")

                        logger.info(
                            "Compare mode completed",
                            extra={
                                "extra_fields": {
                                    "request_group_id": multi_resp.request_group_id,
                                    "success_count": multi_resp.success_count,
                                    "error_count": multi_resp.error_count,
                                    "total_tokens": multi_resp.total_tokens,
                                    "total_cost": multi_resp.total_cost,
                                    "conversation_length": conversation.get_message_count(),
                                }
                            },
                        )

                    else:
                        # ===== SINGLE MODE =====
                        resp = orchestrator.ask(
                            prompt=user_input,
                            model_type=MODEL_TYPE,
                            context=context,
                            token_tracker=token_tracker,
                            research_mode=selected_research_mode,
                        )

                        stop_animation.set()
                        loading_thread.join()

                        # Persist to database (single mode) - even on errors for audit
                        if DB_ENABLED and db_session and user_id and db_session_id:
                            _persist_single_interaction(
                                db_session, user_id, db_session_id, user_input, resp, mode="ask"
                            )

                        if resp.is_error:
                            conversation.pop_last_user()
                            print(f"\n[ERROR] {resp.error.code.upper()}: {resp.error.message}")
                            if resp.error.retryable:
                                print("(This error may be retryable)")
                            print()
                            logger.error(
                                "Completion failed",
                                extra={
                                    "extra_fields": {
                                        "request_id": resp.request_id,
                                        "error_code": resp.error.code,
                                        "error_message": resp.error.message,
                                        "retryable": resp.error.retryable,
                                    }
                                },
                            )
                            continue

                        if resp.text:
                            print(f"\nAI: {resp.text}\n")

                            # Display optimization info if used
                            if resp.metadata and resp.metadata.get("optimization_used"):
                                print("\033[92m[✓ Prompt Optimized]\033[0m")
                                if resp.metadata.get("optimization_steps"):
                                    steps_count = len(resp.metadata["optimization_steps"])
                                    print(f"  Optimization steps: {steps_count}")

                            # Display research info if available
                            display_research_info(resp)

                            conversation.add_assistant(resp.text)

                            # Single-mode cost tracking (CostCalculator is single-provider)
                            cost_calculator.update_cumulative_cost(
                                resp.token_usage.prompt_tokens, resp.token_usage.completion_tokens
                            )

                            logger.info(
                                "Completion successful",
                                extra={
                                    "extra_fields": {
                                        "request_id": resp.request_id,
                                        "provider": resp.provider,
                                        "model": resp.model,
                                        "latency_ms": resp.latency_ms,
                                        "tokens": resp.token_usage.total_tokens,
                                        "cost": resp.estimated_cost,
                                    }
                                },
                            )

                            print(
                                f"[Tokens: {resp.token_usage.total_tokens} | "
                                f"Cost: {cost_calculator.format_cost(resp.estimated_cost)} | "
                                f"Latency: {resp.latency_ms}ms]\n"
                            )

                except Exception as e:
                    stop_animation.set()
                    loading_thread.join()
                    conversation.pop_last_user()
                    logger.error(
                        f"Unexpected error in main loop: {e!s}",
                        extra={"extra_fields": {"error_type": type(e).__name__}},
                    )
                    print(f"\nError: {e!s}\n")
                    continue

            except KeyboardInterrupt:
                logger.info("User interrupted session with Ctrl+C")
                print("\nExiting...")
                break
            except Exception as e:
                logger.error(
                    f"Error during chat interaction: {e!s}",
                    extra={"extra_fields": {"error_type": type(e).__name__}},
                )
                print(f"\nError: {e!s}")
                continue

    except Exception as e:
        logger.error(
            f"Error initializing client: {e!s}",
            extra={"extra_fields": {"error_type": type(e).__name__}},
        )
        print(f"Error initializing client: {e!s}")
        return

    finally:
        # Close database session
        if db_session:
            try:
                db_session.close()
                logger.info("Database session closed")
            except Exception as e:
                logger.error(f"Error closing database session: {e}")

        if token_tracker and token_tracker.requests > 0:
            summary = token_tracker.get_summary()
            logger.info(
                "Session ended",
                extra={
                    "extra_fields": {
                        "total_requests": summary.get("requests", 0),
                        "total_tokens": summary.get("total_tokens", 0),
                        "total_cost": (
                            cost_calculator.total_cost
                            if (cost_calculator and not COMPARE_MODE)
                            else session_total_cost
                        ),
                    }
                },
            )
            print("\n=== Final Session Statistics ===")
            print(token_tracker.format_summary())

            if COMPARE_MODE:
                print(f"\nSession Total Tokens: {session_total_tokens}")
                print(f"Session Total Cost: ${session_total_cost:.6f}")
            else:
                print(f"\n{cost_calculator.format_summary()}")


if __name__ == "__main__":
    main()
