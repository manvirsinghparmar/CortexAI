import os
import threading
import time
import sys
from dotenv import load_dotenv
from typing import Optional, Dict, Any, Type

# Load environment variables first
load_dotenv()

# Import clients based on configuration
MODEL_TYPE = os.getenv('MODEL_TYPE', 'openai').lower()

# Import the base client, token tracker, cost calculator, and logger
from api.base_client import BaseAIClient
from utils.token_tracker import TokenTracker
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger

logger = get_logger(__name__)

def initialize_client(model_type: str) -> tuple[BaseAIClient, str]:
    """
    Initialize the appropriate AI client based on the model type.

    Args:
        model_type: The type of model to initialize ('openai', 'gemini', 'deepseek', or 'grok')

    Returns:
        A tuple containing:
            - An instance of the appropriate AI client
            - The model name being used

    Raises:
        ValueError: If the model type is unsupported or required environment variables are missing
    """
    model_type = model_type.lower()

    if model_type == 'openai':
        from api.openai_client import OpenAIClient

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment variables")
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        model_name = os.getenv('DEFAULT_OPENAI_MODEL', 'gpt-3.5-turbo')
        client = OpenAIClient(api_key=api_key, model_name=model_name)
        logger.info(
            f"Initialized OpenAI client",
            extra={"extra_fields": {"model": model_name, "model_type": "openai"}}
        )
        print(f"Initialized OpenAI client with model: {model_name}")

    elif model_type == 'gemini':
        from api.google_gemini_client import GeminiClient

        api_key = os.getenv('GOOGLE_GEMINI_API_KEY')
        if not api_key:
            logger.error("GOOGLE_GEMINI_API_KEY not found in environment variables")
            raise ValueError("GOOGLE_GEMINI_API_KEY not found in environment variables")

        model_name = os.getenv('DEFAULT_GEMINI_MODEL', 'gemini-2.5-flash-lite')

        # List available models (one-time operation before initializing main client)
        GeminiClient.list_available_models(api_key=api_key, current_model=model_name)

        # Initialize the main client for chat functionality
        client = GeminiClient(api_key=api_key, model_name=model_name)
        logger.info(
            f"Initialized Gemini client",
            extra={"extra_fields": {"model": model_name, "model_type": "gemini"}}
        )
        print(f"\nInitialized Gemini client with model: {model_name}")

    elif model_type == 'deepseek':
        from api.deepseek_client import DeepSeekClient

        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            logger.error("DEEPSEEK_API_KEY not found in environment variables")
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")

        model_name = os.getenv('DEFAULT_DEEPSEEK_MODEL', 'deepseek-chat')

        # List available models (one-time operation before initializing main client)
        DeepSeekClient.list_available_models(api_key=api_key, current_model=model_name)

        # Initialize the main client for chat functionality
        client = DeepSeekClient(api_key=api_key, model_name=model_name)
        logger.info(
            f"Initialized DeepSeek client",
            extra={"extra_fields": {"model": model_name, "model_type": "deepseek"}}
        )
        print(f"\nInitialized DeepSeek client with model: {model_name}")

    elif model_type == 'grok':
        from api.grok_client import GrokClient

        api_key = os.getenv('GROK_API_KEY')
        if not api_key:
            logger.error("GROK_API_KEY not found in environment variables")
            raise ValueError("GROK_API_KEY not found in environment variables")

        model_name = os.getenv('DEFAULT_GROK_MODEL', 'grok-4-latest')

        # List available models (one-time operation before initializing main client)
        GrokClient.list_available_models(api_key=api_key, current_model=model_name)

        # Initialize the main client for chat functionality
        client = GrokClient(api_key=api_key, model_name=model_name)
        logger.info(
            f"Initialized Grok client",
            extra={"extra_fields": {"model": model_name, "model_type": "grok"}}
        )
        print(f"\nInitialized Grok client with model: {model_name}")

    else:
        logger.error(f"Unsupported MODEL_TYPE: {model_type}")
        raise ValueError(f"Unsupported MODEL_TYPE: {model_type}. Must be 'openai', 'gemini', 'deepseek', or 'grok'")

    return client, model_name


def show_loading_animation(stop_event: threading.Event) -> None:
    """
    Show a loading animation in the console.
    
    Args:
        stop_event: A threading.Event that will be set to stop the animation
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
    # Initialize variables to None for proper cleanup in finally block
    token_tracker = None
    cost_calculator = None

    logger.info("Application starting", extra={"extra_fields": {"model_type": MODEL_TYPE}})

    try:
        # Initialize the appropriate client
        client, model_name = initialize_client(MODEL_TYPE)

        # Initialize token tracker and cost calculator
        token_tracker = TokenTracker(model_type=MODEL_TYPE, model_name=model_name)
        cost_calculator = CostCalculator(model_type=MODEL_TYPE, model_name=model_name)

        # Start the chat interface
        print("\n=== AI Chat ===")
        print("Type 'exit' to quit, 'stats' to see token usage, or 'help' for commands\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                # Handle commands
                if not user_input:
                    continue
                    
                if user_input.lower() in ('exit', 'quit'):
                    print("\nGoodbye!")
                    break
                    
                if user_input.lower() == 'stats':
                    logger.debug("User requested session statistics")
                    print("\n=== Session Statistics ===")
                    print(token_tracker.format_summary())
                    print(f"\n{cost_calculator.format_summary()}")
                    print(f"\nLast updated: {token_tracker.get_summary()['timestamp']}\n")
                    continue
                    
                if user_input.lower() == 'help':
                    print("\n=== Available Commands ===")
                    print("help     - Show this help message")
                    print("stats    - Show token usage statistics")
                    print("exit/quit - Exit the program\n")
                    continue
                
                # Show loading animation in a separate thread
                stop_animation = threading.Event()
                loading_thread = threading.Thread(target=show_loading_animation, args=(stop_animation,))
                loading_thread.daemon = True
                loading_thread.start()
                
                try:
                    # Get completion with token tracking
                    logger.debug(f"User query length: {len(user_input)} characters")
                    response, usage = client.get_completion(user_input, return_usage=True)

                    # Stop the loading animation
                    stop_animation.set()
                    loading_thread.join()

                    if response:
                        print(f"\nAI: {response}")
                        if usage:
                            # Update token tracker
                            token_tracker.update(usage)

                            # Update cost calculator
                            cost_calculator.update_cumulative_cost(
                                usage.get('prompt_tokens', 0),
                                usage.get('completion_tokens', 0)
                            )

                            # Calculate cost for this specific request
                            request_cost = cost_calculator.calculate_cost(
                                usage.get('prompt_tokens', 0),
                                usage.get('completion_tokens', 0)
                            )

                            logger.info(
                                "Completion successful",
                                extra={"extra_fields": {
                                    "prompt_tokens": usage.get('prompt_tokens', 0),
                                    "completion_tokens": usage.get('completion_tokens', 0),
                                    "total_tokens": usage.get('total_tokens', 0),
                                    "cost": request_cost['total_cost']
                                }}
                            )

                            print(f"[Tokens: {usage.get('total_tokens', 'N/A')} | Cost: {cost_calculator.format_cost(request_cost['total_cost'])}]\n")
                except Exception as e:
                    # Ensure loading is stopped even if there's an error
                    stop_animation.set()
                    loading_thread.join()
                    raise e
                
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
        # Print final session statistics if any requests were made
        if token_tracker and token_tracker.requests > 0:
            summary = token_tracker.get_summary()
            logger.info(
                "Session ended",
                extra={"extra_fields": {
                    "total_requests": summary.get('requests', 0),
                    "total_tokens": summary.get('total_tokens', 0),
                    "total_cost": cost_calculator.cumulative_cost if cost_calculator else 0
                }}
            )
            print("\n=== Final Session Statistics ===")
            print(token_tracker.format_summary())
            if cost_calculator:
                print(f"\n{cost_calculator.format_summary()}")


if __name__ == "__main__":
    main()