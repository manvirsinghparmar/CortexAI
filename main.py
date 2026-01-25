import os
import threading
import time
import sys
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Import configuration
MODEL_TYPE = os.getenv('MODEL_TYPE', 'openai').lower()
COMPARE_MODE = os.getenv('COMPARE_MODE', 'false').lower() == 'true'
RESEARCH_MODE = os.getenv('RESEARCH_MODE', 'auto').lower()  # Default to 'auto'

# Import orchestrator and utilities
from orchestrator.core import CortexOrchestrator
from models.user_context import UserContext
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger
from context.conversation_manager import ConversationManager
from config.config import COMPARE_TARGETS

logger = get_logger(__name__)


def _convert_to_user_context(conversation: ConversationManager) -> UserContext:
    """
    Convert ConversationManager to UserContext for orchestrator.
    """
    return UserContext(conversation_history=conversation.get_messages())


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
        for char in '|/-\\':
            if stop_event.is_set():
                break
            sys.stdout.write(f'\r\033[93mThinking {char}\033[0m')
            sys.stdout.flush()
            time.sleep(0.1)

    # Clear the loading line
    sys.stdout.write('\r' + ' ' * 20 + '\r')
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

    logger.info(
        "Application starting",
        extra={"extra_fields": {"model_type": MODEL_TYPE, "compare_mode": COMPARE_MODE}}
    )

    try:
        orchestrator = CortexOrchestrator()

        # Track tokens via orchestrator (pass token_tracker into ask/compare)
        token_tracker = orchestrator.create_token_tracker(MODEL_TYPE)

        # CostCalculator is meaningful only in Single Mode (single provider pricing)
        cost_calculator = orchestrator.create_cost_calculator(MODEL_TYPE)

        conversation = ConversationManager()

        if COMPARE_MODE and not COMPARE_TARGETS:
            print("ERROR: COMPARE_MODE=true but no COMPARE_TARGETS configured in config.py")
            print("Please configure COMPARE_TARGETS or set COMPARE_MODE=false\n")
            return

        logger.info(
            "Initialized CLI session",
            extra={"extra_fields": {"max_messages": conversation.max_messages, "compare_mode": COMPARE_MODE}}
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

                if user_input.lower() in ('exit', 'quit'):
                    print("\nGoodbye!")
                    break

                if user_input.lower() == 'stats':
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

                if user_input.lower() == '/reset':
                    conversation.reset(keep_system_prompt=True)
                    print("\n[Conversation history cleared]\n")
                    logger.info("User reset conversation history")
                    continue

                if user_input.lower() == '/history':
                    print(f"\n{conversation.get_conversation_summary(last_n=10)}\n")
                    logger.debug("User requested conversation history")
                    continue

                if user_input.lower() == 'help':
                    print("\n=== Available Commands ===")
                    print("help          - Show this help message")
                    print("stats         - Show token usage statistics")
                    print("/reset        - Clear conversation history")
                    print("/history      - Show recent conversation")
                    print("exit/quit     - Exit the program")
                    if COMPARE_MODE:
                        print("\nCurrent Mode: Compare Mode (COMPARE_MODE=true)")
                        print("All prompts are sent to multiple models for comparison")
                    else:
                        print(f"\nCurrent Mode: Single Model ({MODEL_TYPE.upper()})")
                        print("Set COMPARE_MODE=true in .env to enable multi-model comparison")
                    print(f"\nResearch Mode: {selected_research_mode}")
                    print("  - off  : No web research")
                    print("  - auto : Research for current events/news (keywords: latest, recent, 2026, etc.)")
                    print("  - on   : Always research")
                    print()
                    continue

                # Add user message to conversation
                conversation.add_user(user_input)

                # Loading animation
                stop_animation = threading.Event()
                loading_thread = threading.Thread(target=show_loading_animation, args=(stop_animation,))
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
                            research_mode=selected_research_mode
                        )

                        stop_animation.set()
                        loading_thread.join()

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

                                text_preview = resp.text if len(resp.text) <= 200 else resp.text[:200] + "..."
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
                            extra={"extra_fields": {
                                "request_group_id": multi_resp.request_group_id,
                                "success_count": multi_resp.success_count,
                                "error_count": multi_resp.error_count,
                                "total_tokens": multi_resp.total_tokens,
                                "total_cost": multi_resp.total_cost,
                                "conversation_length": conversation.get_message_count()
                            }}
                        )

                    else:
                        # ===== SINGLE MODE =====
                        resp = orchestrator.ask(
                            prompt=user_input,
                            model_type=MODEL_TYPE,
                            context=context,
                            token_tracker=token_tracker,
                            research_mode=selected_research_mode
                        )

                        stop_animation.set()
                        loading_thread.join()

                        if resp.is_error:
                            conversation.pop_last_user()
                            print(f"\n[ERROR] {resp.error.code.upper()}: {resp.error.message}")
                            if resp.error.retryable:
                                print("(This error may be retryable)")
                            print()
                            logger.error(
                                "Completion failed",
                                extra={"extra_fields": {
                                    "request_id": resp.request_id,
                                    "error_code": resp.error.code,
                                    "error_message": resp.error.message,
                                    "retryable": resp.error.retryable
                                }}
                            )
                            continue

                        if resp.text:
                            print(f"\nAI: {resp.text}\n")

                            # Display research info if available
                            display_research_info(resp)

                            conversation.add_assistant(resp.text)

                            # Single-mode cost tracking (CostCalculator is single-provider)
                            cost_calculator.update_cumulative_cost(
                                resp.token_usage.prompt_tokens,
                                resp.token_usage.completion_tokens
                            )

                            logger.info(
                                "Completion successful",
                                extra={"extra_fields": {
                                    "request_id": resp.request_id,
                                    "provider": resp.provider,
                                    "model": resp.model,
                                    "latency_ms": resp.latency_ms,
                                    "tokens": resp.token_usage.total_tokens,
                                    "cost": resp.estimated_cost
                                }}
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
                        f"Unexpected error in main loop: {str(e)}",
                        extra={"extra_fields": {"error_type": type(e).__name__}}
                    )
                    print(f"\nError: {str(e)}\n")
                    continue

            except KeyboardInterrupt:
                logger.info("User interrupted session with Ctrl+C")
                print("\nExiting...")
                break
            except Exception as e:
                logger.error(
                    f"Error during chat interaction: {str(e)}",
                    extra={"extra_fields": {"error_type": type(e).__name__}}
                )
                print(f"\nError: {str(e)}")
                continue

    except Exception as e:
        logger.error(
            f"Error initializing client: {str(e)}",
            extra={"extra_fields": {"error_type": type(e).__name__}}
        )
        print(f"Error initializing client: {str(e)}")
        return

    finally:
        if token_tracker and token_tracker.requests > 0:
            summary = token_tracker.get_summary()
            logger.info(
                "Session ended",
                extra={"extra_fields": {
                    "total_requests": summary.get('requests', 0),
                    "total_tokens": summary.get('total_tokens', 0),
                    "total_cost": cost_calculator.total_cost if (cost_calculator and not COMPARE_MODE) else session_total_cost
                }}
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