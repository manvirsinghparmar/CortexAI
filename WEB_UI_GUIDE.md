# CortexAI Web Interface - Quick Start Guide

## ✅ Setup Complete!

Your CortexAI web interface is now fully integrated with your existing backend!

## 🚀 How to Use

### 1. Start the Web Server

```bash
cd "c:\Users\Soumadeep Gupta\CortexAI\CortexAI"
python web_server.py
```

The server will start on **http://localhost:5000**

### 2. Open the UI

Open your web browser and navigate to:
```
http://localhost:5000
```

### 3. Start Chatting!

- Type your question in the search box
- Click the send button or press Enter
- Watch as your prompt is processed through the same `CortexOrchestrator` that powers the terminal UI
- See AI responses with research sources, stats, and metadata

## 🎯 Features

### What Works Now:
- ✅ **Full CortexAI Integration**: Uses your existing `orchestrator.core.CortexOrchestrator`
- ✅ **Chat Interface**: Beautiful, modern chat UI with message history
- ✅ **Research Display**: Shows web research sources when used
- ✅ **Stats Display**: Token usage, cost, latency for each response
- ✅ **Session Management**: Maintains conversation context
- ✅ **Research Mode Toggle**: Click the model selector to switch between auto/on/off
- ✅ **Keyboard Shortcuts**: 
  - `Ctrl/Cmd + K`: Focus search
  - `Ctrl/Cmd + R`: Reset conversation
  - `Enter`: Send message

### Example Queries:
Click on any of the example queries to try them out:
- "Explain quantum entanglement simply"
- "Generate a creative app name for task management"
- "Translate 'flutter like than never' into Latin"
- "Write a short riddle with the answer 'time'"

## 🔧 Configuration

The web server uses your existing `.env` configuration:

- `MODEL_TYPE`: Which AI model to use (gemini, openai, etc.)
- `COMPARE_MODE`: Enable multi-model comparison
- `RESEARCH_MODE`: Default research mode (auto/on/off)
- `ENABLE_PROMPT_OPTIMIZATION`: Enable prompt optimization
- `WEB_PORT`: Web server port (default: 5000)

## 📊 API Endpoints

The Flask server provides these REST endpoints:

- `GET /` - Serve the web UI
- `POST /api/chat` - Send a chat message
- `GET /api/session/{id}/history` - Get conversation history
- `POST /api/session/{id}/reset` - Reset conversation
- `GET /api/session/{id}/stats` - Get session statistics
- `GET /api/config` - Get current configuration
- `GET /api/health` - Health check

## 🎨 UI Components

### Files Created:
```
ui/
├── index.html      # Main HTML structure
├── styles.css      # Complete styling with chat UI
├── script.js       # API integration and interactivity
└── README.md       # UI documentation

web_server.py       # Flask backend server
```

## 🔄 How It Works

1. **User enters a prompt** in the web UI
2. **JavaScript sends POST request** to `/api/chat`
3. **Flask server receives request** and creates/retrieves session
4. **CortexOrchestrator processes** the prompt (same as terminal UI)
5. **Response flows back** through Flask → JavaScript → UI
6. **Chat message displayed** with research sources and stats

## 💡 Next Steps

### Immediate Improvements:
1. **Streaming Responses**: Add SSE (Server-Sent Events) for real-time streaming
2. **File Upload**: Implement document upload and processing
3. **Voice Input**: Add Web Speech API integration
4. **Dark Mode**: Add theme toggle
5. **Export Chat**: Download conversation history

### Advanced Features:
1. **User Authentication**: Add login/signup
2. **Multiple Conversations**: Save and switch between chats
3. **Prompt Templates**: Pre-built prompts for common tasks
4. **Code Highlighting**: Syntax highlighting for code responses
5. **Markdown Rendering**: Full markdown support in responses

## 🐛 Troubleshooting

### "Failed to fetch" Error
- Make sure the Flask server is running: `python web_server.py`
- Check that port 5000 is not in use by another application
- Verify the API_BASE_URL in `script.js` matches your server address

### No Response from AI
- Check your `.env` file has valid API keys
- Look at the Flask server console for error messages
- Check browser console (F12) for JavaScript errors

### Research Not Working
- Ensure `TAVILY_API_KEY` is set in `.env`
- Check research mode is not set to "off"
- Verify web search is enabled in your configuration

## 📝 Comparison: Terminal UI vs Web UI

| Feature | Terminal UI | Web UI |
|---------|-------------|--------|
| Interface | Text-based CLI | Modern web interface |
| Message History | Scrollback only | Persistent chat view |
| Research Display | Text list | Clickable links with formatting |
| Stats Display | Inline text | Formatted badges |
| Multi-session | Single session | Multiple browser tabs |
| Accessibility | Keyboard only | Mouse + Keyboard |
| Visual Appeal | Basic | Premium design |

## 🎓 Learning Resources

To understand the codebase better:

1. **Backend Flow**: `web_server.py` → `orchestrator/core.py` → AI clients
2. **Frontend Flow**: `script.js` → Fetch API → Flask endpoints
3. **Session Management**: In-memory dict (upgrade to Redis for production)
4. **Error Handling**: Try-catch in JS, error responses in Flask

## 📞 Support

If you encounter issues:
1. Check the Flask server console output
2. Check browser console (F12 → Console tab)
3. Verify all dependencies are installed: `pip install flask flask-cors`
4. Ensure your `.env` file is properly configured

---

**Enjoy your new CortexAI web interface!** 🎉

The same powerful AI orchestration you had in the terminal, now with a beautiful, modern UI.
