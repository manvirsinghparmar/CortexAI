"""
Flask web server for CortexAI.

Responsibilities:
  - Serve the static UI from the `ui/` folder
  - Provide lightweight session utility endpoints (history, reset, stats)
  - Health check and config endpoints

All AI inference is handled by the FastAPI server (run_server.py / uvicorn).
The UI calls the FastAPI server directly for /v1/chat and /v1/compare.
"""

import os
import time
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from orchestrator.core import CortexOrchestrator
from models.user_context import UserContext
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger
from context.conversation_manager import ConversationManager

load_dotenv()
logger = get_logger(__name__)

app = Flask(__name__, static_folder='ui', static_url_path='')
CORS(app)

# Read-only config (informational only — inference config lives in FastAPI server)
MODEL_TYPE    = os.getenv('MODEL_TYPE', 'openai').lower()
COMPARE_MODE  = os.getenv('COMPARE_MODE', 'false').lower() == 'true'
RESEARCH_MODE = os.getenv('RESEARCH_MODE', 'auto').lower()

# In-memory sessions (for conversation history tracking only)
sessions: dict = {}


def get_or_create_session(session_id: str) -> dict:
    """Get or create a lightweight session for conversation tracking."""
    if session_id not in sessions:
        orchestrator   = CortexOrchestrator()
        conversation   = ConversationManager()
        token_tracker  = orchestrator.create_token_tracker(MODEL_TYPE)
        cost_calculator = orchestrator.create_cost_calculator(MODEL_TYPE)

        sessions[session_id] = {
            'orchestrator':    orchestrator,
            'conversation':    conversation,
            'token_tracker':   token_tracker,
            'cost_calculator': cost_calculator,
            'total_cost':      0.0,
            'total_tokens':    0,
            'research_mode':   RESEARCH_MODE,
            'created_at':      time.time(),
        }
        logger.info(f"Created new session: {session_id}")

    return sessions[session_id]


# ── Static UI ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the main UI page."""
    return send_from_directory('ui', 'index.html')


# ── Session utilities ─────────────────────────────────────────────────────────

@app.route('/api/session/<session_id>/history', methods=['GET'])
def get_history(session_id: str):
    """Return conversation history for a session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    conversation = sessions[session_id]['conversation']
    return jsonify({
        'messages':      conversation.get_messages(),
        'message_count': conversation.get_message_count(),
        'summary':       conversation.get_conversation_summary(last_n=10),
    })


@app.route('/api/session/<session_id>/reset', methods=['POST'])
def reset_session(session_id: str):
    """Clear conversation history for a session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    sessions[session_id]['conversation'].reset(keep_system_prompt=True)
    logger.info(f"Reset session: {session_id}")
    return jsonify({'message': 'Session reset successfully'})


@app.route('/api/session/<session_id>/stats', methods=['GET'])
def get_stats(session_id: str):
    """Return token/cost statistics for a session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    session       = sessions[session_id]
    token_tracker = session['token_tracker']
    summary       = token_tracker.get_summary()

    return jsonify({
        'session_id':     session_id,
        'total_requests': summary.get('requests', 0),
        'total_tokens':   summary.get('total_tokens', 0),
        'total_cost':     session['cost_calculator'].total_cost,
        'research_mode':  session['research_mode'],
        'created_at':     session['created_at'],
        'uptime_seconds': time.time() - session['created_at'],
    })


# ── Informational endpoints ───────────────────────────────────────────────────

@app.route('/api/config', methods=['GET'])
def get_config():
    """Return current server configuration (read-only)."""
    return jsonify({
        'model_type':                  MODEL_TYPE,
        'compare_mode':                COMPARE_MODE,
        'research_mode':               RESEARCH_MODE,
        'prompt_optimization_enabled': os.getenv('ENABLE_PROMPT_OPTIMIZATION', 'false').lower() == 'true',
        'prompt_optimizer_provider':   os.getenv('PROMPT_OPTIMIZER_PROVIDER', 'gemini'),
    })


@app.route('/api/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({
        'status':          'healthy',
        'active_sessions': len(sessions),
        'timestamp':       time.time(),
    })


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port  = int(os.getenv('WEB_PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'

    logger.info(f"Starting CortexAI UI server on port {port}")

    print(f"\n{'='*60}")
    print(f">> CortexAI UI Server")
    print(f"{'='*60}")
    print(f"UI:          http://localhost:{port}")
    print(f"FastAPI:     http://localhost:8000  (run separately)")
    print(f"{'='*60}\n")

    app.run(host='0.0.0.0', port=port, debug=debug)
