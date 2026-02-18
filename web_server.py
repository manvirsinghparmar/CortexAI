"""
Flask web server for CortexAI chat interface.
Provides REST API endpoints for the web UI to interact with CortexOrchestrator.
"""

import os
import json
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
import time
from typing import Dict, Any

# Load environment variables
load_dotenv()

# Import CortexAI components
from orchestrator.core import CortexOrchestrator
from models.user_context import UserContext
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger
from context.conversation_manager import ConversationManager

logger = get_logger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='ui', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Configuration
MODEL_TYPE = os.getenv('MODEL_TYPE', 'openai').lower()
COMPARE_MODE = os.getenv('COMPARE_MODE', 'false').lower() == 'true'
RESEARCH_MODE = os.getenv('RESEARCH_MODE', 'auto').lower()

# Global state (in production, use Redis or database)
sessions: Dict[str, Dict[str, Any]] = {}


def get_or_create_session(session_id: str) -> Dict[str, Any]:
    """Get or create a session with conversation manager and orchestrator."""
    if session_id not in sessions:
        orchestrator = CortexOrchestrator()
        conversation = ConversationManager()
        token_tracker = orchestrator.create_token_tracker(MODEL_TYPE)
        cost_calculator = orchestrator.create_cost_calculator(MODEL_TYPE)
        
        sessions[session_id] = {
            'orchestrator': orchestrator,
            'conversation': conversation,
            'token_tracker': token_tracker,
            'cost_calculator': cost_calculator,
            'total_cost': 0.0,
            'total_tokens': 0,
            'research_mode': RESEARCH_MODE,
            'created_at': time.time()
        }
        logger.info(f"Created new session: {session_id}")
    
    return sessions[session_id]


def _convert_to_user_context(conversation: ConversationManager) -> UserContext:
    """Convert ConversationManager to UserContext for orchestrator."""
    return UserContext(conversation_history=conversation.get_messages())


@app.route('/')
def index():
    """Serve the main UI page."""
    return send_from_directory('ui', 'index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handle chat requests from the UI.
    
    Request body:
    {
        "message": "user prompt",
        "session_id": "optional-session-id",
        "research_mode": "auto|on|off" (optional)
    }
    
    Response:
    {
        "response": "AI response text",
        "metadata": {...},
        "session_id": "session-id",
        "stats": {...}
    }
    """
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        research_mode = data.get('research_mode', RESEARCH_MODE)
        enable_optimization = data.get('prompt_optimization_enabled', False)
        compare_mode = data.get('compare_mode', False)  # Get compare mode from UI
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get or create session
        session = get_or_create_session(session_id)
        orchestrator = session['orchestrator']
        conversation = session['conversation']
        token_tracker = session['token_tracker']
        cost_calculator = session['cost_calculator']
        
        # Update research mode if provided
        if research_mode:
            session['research_mode'] = research_mode
        
        # Add user message to conversation
        conversation.add_user(user_message)
        
        # Convert to context
        context = _convert_to_user_context(conversation)
        
        # Get AI response - use compare mode if enabled from UI or env
        logger.info(f"Compare mode from UI: {compare_mode}, from ENV: {COMPARE_MODE}")
        models_to_compare = data.get('models', [])  # Get selected models from request
        
        if compare_mode or COMPARE_MODE:
            logger.info(f"Compare mode ENABLED with models: {models_to_compare}")
            
            # If no models specified, use defaults
            if not models_to_compare:
                models_to_compare = ['gemini', 'openai', 'claude']
            
            comparisons_data = []
            
            # Call each selected model
            for model_type in models_to_compare:
                try:
                    logger.info(f"Calling {model_type} for comparison...")
                    
                    resp = orchestrator.ask(
                        prompt=user_message,
                        model_type=model_type,
                        context=context,
                        token_tracker=token_tracker,
                        research_mode=session['research_mode'],
                        enable_optimization=enable_optimization
                    )
                    
                    if resp.is_error:
                        comparisons_data.append({
                            'provider': model_type,
                            'model': resp.model or f'{model_type}-model',
                            'response': None,
                            'error': resp.error.message if resp.error else 'Unknown error',
                            'tokens': 0,
                            'cost': 0,
                            'latency_ms': 0
                        })
                    else:
                        comparisons_data.append({
                            'provider': model_type,
                            'model': resp.model or f'{model_type}-model',
                            'response': resp.text,
                            'error': None,
                            'tokens': resp.token_usage.total_tokens,
                            'cost': resp.estimated_cost,
                            'latency_ms': resp.latency_ms
                        })
                        
                        # Update session totals
                        session['total_cost'] += resp.estimated_cost
                        session['total_tokens'] += resp.token_usage.total_tokens
                        
                except Exception as e:
                    logger.error(f"Error calling {model_type}: {str(e)}")
                    comparisons_data.append({
                        'provider': model_type,
                        'model': f'{model_type}-model',
                        'response': None,
                        'error': str(e),
                        'tokens': 0,
                        'cost': 0,
                        'latency_ms': 0
                    })
            
            # Add the first successful response to conversation
            if comparisons_data:
                for comp in comparisons_data:
                    if comp['response']:
                        conversation.add_assistant(comp['response'])
                        break
            
            logger.info(f"Returning {len(comparisons_data)} REAL comparisons")
            
            # Calculate totals for response
            total_tokens = sum(c['tokens'] for c in comparisons_data)
            total_cost = sum(c['cost'] for c in comparisons_data)
            avg_latency = sum(c['latency_ms'] for c in comparisons_data) / len(comparisons_data) if comparisons_data else 0
            
            return jsonify({
                'response': comparisons_data[0]['response'] if comparisons_data else '',
                'metadata': {},
                'session_id': session_id,
                'stats': {
                    'tokens': total_tokens,
                    'cost': total_cost,
                    'latency_ms': int(avg_latency),
                    'session_total_cost': session['total_cost'],
                    'session_total_tokens': session['total_tokens']
                },
                'comparisons': comparisons_data
            })
        
        else:
            # Single model mode
            resp = orchestrator.ask(
                prompt=user_message,
                model_type=MODEL_TYPE,
                context=context,
                token_tracker=token_tracker,
                research_mode=session['research_mode'],
                enable_optimization=enable_optimization
            )
            
            if resp.is_error:
                conversation.pop_last_user()
                return jsonify({
                    'error': resp.error.message,
                    'error_code': resp.error.code,
                    'retryable': resp.error.retryable
                }), 500
            
            # Add assistant response to conversation
            conversation.add_assistant(resp.text)
            
            # Update cost calculator
            cost_calculator.update_cumulative_cost(
                resp.token_usage.prompt_tokens,
                resp.token_usage.completion_tokens
            )
            
            return jsonify({
                'response': resp.text,
                'metadata': resp.metadata or {},
                'session_id': session_id,
                'stats': {
                    'tokens': resp.token_usage.total_tokens,
                    'prompt_tokens': resp.token_usage.prompt_tokens,
                    'completion_tokens': resp.token_usage.completion_tokens,
                    'cost': resp.estimated_cost,
                    'latency_ms': resp.latency_ms,
                    'session_total_cost': cost_calculator.total_cost,
                    'provider': resp.provider,
                    'model': resp.model
                }
            })
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/stream', methods=['GET'])
def chat_stream():
    """
    Stream chat responses using Server-Sent Events (SSE).
    Chunks are sent as they're generated for progressive display.
    """
    try:
        # Get parameters from query string for GET request
        user_message = request.args.get('message', '').strip()
        session_id = request.args.get('session_id', 'default')
        research_mode = request.args.get('research_mode', RESEARCH_MODE)
        enable_optimization = request.args.get('prompt_optimization_enabled', 'false').lower() == 'true'
        compare_mode = request.args.get('compare_mode', 'false').lower() == 'true'
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        def generate():
            try:
                # Get or create session
                session = get_or_create_session(session_id)
                orchestrator = session['orchestrator']
                conversation = session['conversation']
                token_tracker = session['token_tracker']
                cost_calculator = session['cost_calculator']
                
                # Update research mode if provided
                if research_mode:
                    session['research_mode'] = research_mode
                
                # Add user message to conversation
                conversation.add_user(user_message)
                
                # Convert to context
                context = _convert_to_user_context(conversation)
                
                # For now, we'll get the full response and simulate streaming
                # TODO: Update orchestrator to support actual token streaming
                resp = orchestrator.ask(
                    prompt=user_message,
                    model_type=MODEL_TYPE,
                    context=context,
                    token_tracker=token_tracker,
                    research_mode=session['research_mode'],
                    enable_optimization=enable_optimization
                )
                
                if resp.is_error:
                    conversation.pop_last_user()
                    yield f"data: {json.dumps({'type': 'error', 'error': resp.error.message})}\n\n"
                    return
                
                # Simulate streaming by chunking the response
                text = resp.text
                chunk_size = 5  # words per chunk
                words = text.split(' ')
                
                for i in range(0, len(words), chunk_size):
                    chunk = ' '.join(words[i:i+chunk_size])
                    if i + chunk_size < len(words):
                        chunk += ' '
                    
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    time.sleep(0.05)  # Small delay to simulate streaming
                
                # Add assistant response to conversation
                conversation.add_assistant(resp.text)
                
                # Update cost calculator
                cost_calculator.update_cumulative_cost(
                    resp.token_usage.prompt_tokens,
                    resp.token_usage.completion_tokens
                )
                
                # Send completion event with metadata
                completion_data = {
                    'type': 'complete',
                    'metadata': resp.metadata or {},
                    'stats': {
                        'tokens': resp.token_usage.total_tokens,
                        'prompt_tokens': resp.token_usage.prompt_tokens,
                        'completion_tokens': resp.token_usage.completion_tokens,
                        'cost': resp.estimated_cost,
                        'latency_ms': resp.latency_ms,
                        'session_total_cost': cost_calculator.total_cost,
                        'provider': resp.provider,
                        'model': resp.model
                    }
                }
                
                yield f"data: {json.dumps(completion_data)}\n\n"
                
            except Exception as e:
                logger.error(f"Error in streaming: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
        
    except Exception as e:
        logger.error(f"Error in chat stream endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/session/<session_id>/history', methods=['GET'])
def get_history(session_id: str):
    """Get conversation history for a session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = sessions[session_id]
    conversation = session['conversation']
    
    return jsonify({
        'messages': conversation.get_messages(),
        'message_count': conversation.get_message_count(),
        'summary': conversation.get_conversation_summary(last_n=10)
    })


@app.route('/api/session/<session_id>/reset', methods=['POST'])
def reset_session(session_id: str):
    """Reset conversation history for a session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = sessions[session_id]
    conversation = session['conversation']
    conversation.reset(keep_system_prompt=True)
    
    logger.info(f"Reset session: {session_id}")
    return jsonify({'message': 'Session reset successfully'})


@app.route('/api/session/<session_id>/stats', methods=['GET'])
def get_stats(session_id: str):
    """Get statistics for a session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = sessions[session_id]
    token_tracker = session['token_tracker']
    cost_calculator = session['cost_calculator']
    
    summary = token_tracker.get_summary()
    
    return jsonify({
        'session_id': session_id,
        'total_requests': summary.get('requests', 0),
        'total_tokens': summary.get('total_tokens', 0),
        'total_cost': cost_calculator.total_cost if not COMPARE_MODE else session['total_cost'],
        'research_mode': session['research_mode'],
        'created_at': session['created_at'],
        'uptime_seconds': time.time() - session['created_at']
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    return jsonify({
        'model_type': MODEL_TYPE,
        'compare_mode': COMPARE_MODE,
        'research_mode': RESEARCH_MODE,
        'prompt_optimization_enabled': os.getenv('ENABLE_PROMPT_OPTIMIZATION', 'false').lower() == 'true',
        'prompt_optimizer_provider': os.getenv('PROMPT_OPTIMIZER_PROVIDER', 'gemini')
    })


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'active_sessions': len(sessions),
        'timestamp': time.time()
    })


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(e)}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.getenv('WEB_PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting CortexAI web server on port {port}")
    logger.info(f"Model Type: {MODEL_TYPE}")
    logger.info(f"Compare Mode: {COMPARE_MODE}")
    logger.info(f"Research Mode: {RESEARCH_MODE}")
    
    print(f"\n{'='*60}")
    print(f">> CortexAI Web Server Starting")
    print(f"{'='*60}")
    print(f"URL: http://localhost:{port}")
    print(f"Model: {MODEL_TYPE.upper()}")
    print(f"Compare Mode: {'ON' if COMPARE_MODE else 'OFF'}")
    print(f"Research Mode: {RESEARCH_MODE.upper()}")
    print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
