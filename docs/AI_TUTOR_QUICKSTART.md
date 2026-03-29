# AI Tutor Quickstart

## What You Got

An AI tutor that:
- Appears as a 🎓 floating button (bottom-right, or press **?** key)
- Asks Socratic questions (doesn't just give answers)
- Knows what step you're on in the solver
- Supports multiple AI providers:
  - **DeepSeek** (default - your existing key)
  - **Google Gemini** (free tier, supports vision/screenshots!)
  - **OpenAI/Anthropic** (if you have keys)
  - **Local Ollama** (free, runs locally)

## How to Run

### Option 1: DeepSeek (Default)

Uses your existing DeepSeek key:

```bash
cd ~/Desktop/calculus_animator
python run.py
```

### Option 2: Google Gemini API (with Vision!)

For screenshot/vision support via API:

```bash
# 1. Get a free API key: https://aistudio.google.com/app/apikey
# 2. Set it
export GOOGLE_API_KEY="your-key-here"
export LLM_PROVIDER="google"

# 3. Run
python run.py
```

Or create a `.env` file:
```bash
echo "GOOGLE_API_KEY=your-key" > .env
echo "LLM_PROVIDER=google" >> .env
python run.py
```

### Option 3: Gemini CLI (Local - FREE!)

Uses your locally installed Gemini CLI (brew install):

```bash
# 1. Install Gemini CLI (one-time)
brew install google-gemini

# 2. Run (completely free, no API key needed!)
export LLM_PROVIDER=gemini_cli
python run.py
```

**Note:** Gemini CLI uses your logged-in Google account and is completely free. However, vision/screenshot support depends on the CLI version.

### Option 4: Manual Steps

```bash
# 1. Set the API key
export DEEPSEEK_API_KEY="your-deepseek-key"
# OR
export GOOGLE_API_KEY="your-key"

# 2. Choose provider
export LLM_PROVIDER="deepseek"  # or "google" / "openai" / "anthropic"

# 3. Install dependencies (first time only)
pip install fastapi uvicorn httpx chromadb sentence-transformers

# 4. Build curriculum index (first time only)
python -m ai_tutor.services.ingest

# 5. Start backend
python -m uvicorn ai_tutor.main:app --host 127.0.0.1 --port 8000

# 6. In another terminal, run desktop app
python run.py
```

## How to Use

### Basic Chat
1. **Enter a calculus problem** and click Solve
2. **Click the 🎓 button** in the bottom-right corner (or press **?** key)
3. **Type a question** and click Ask
4. The AI responds with Socratic guidance

### With Screenshot (Vision Mode)
1. **Click 📷 Attach Screenshot**
   - You'll see "📷 Screenshot attached" appear above the input
2. **Type your question** about what you're seeing
3. **Click Ask** to send both question + screenshot
4. The AI can "see" your work and reference specific parts

### Example Questions
- "Why do we use the product rule here?"
- "Help me understand step 3"
- "What's wrong with this derivative?" [+screenshot]
- "Explain the graph I'm looking at" [+screenshot]

The AI will:
- See what expression you're working on
- Know which step you're viewing
- **See your screenshot** (if attached)
- Retrieve relevant calculus concepts
- Ask guiding questions (not give answers)

## Where the AI Mode Actually Is

The AI tutor is integrated into your existing app:

```
ui/index.html              ← Added 🎓 AI Tutor button
ui/ai_tutor/tutor-panel.js ← The chat panel (slide-out from right)
ai_tutor/                  ← Python backend (FastAPI)
  ├── main.py              ← API server (port 8000)
  ├── providers/router.py  ← DeepSeek/OpenAI/etc
  ├── rag/concept_engine.py← RAG (curriculum search)
  └── routers/tutor.py     ← /tutor/chat endpoint
```

## API Key Setup

Create a `.env` file in the project root:
```bash
cp .env.example .env
# Edit .env and add your keys
```

`run.py` reads `.env` automatically on startup.

## Troubleshooting

**"Backend not responding"**
```bash
# Check if backend is running
curl http://127.0.0.1:8000/health

# Should show: {"status":"healthy","llm_provider":"deepseek",...}
```

**"No concepts found"**
```bash
# Rebuild curriculum index
python -m ai_tutor.services.ingest
```

**"DeepSeek API error"**
- Check your API key is valid
- Or switch to Google Gemini (free tier available):
```bash
export GOOGLE_API_KEY="your-key"
export LLM_PROVIDER=google
python run.py
```
- Or switch to local mode with Ollama:
```bash
export LLM_PROVIDER=local
ollama pull mistral
python run.py
```

**"Vision/screenshot not working"**
- DeepSeek doesn't support vision
- Use Gemini CLI: `export LLM_PROVIDER=gemini_cli && python run.py` ← **Recommended!** (local, free, supports vision)
- Or use Google Gemini API: `export LLM_PROVIDER=google && python run.py`
- Or use OpenAI: `export LLM_PROVIDER=openai` (requires GPT-4V)

**"Gemini CLI not found"**
```bash
# Install Gemini CLI
brew install google-gemini

# Verify it's in PATH
which gemini

# Then run
export LLM_PROVIDER=gemini_cli
python run.py
```

## Provider Quick Reference

| Provider | Command | Vision | Cost | Notes |
|----------|---------|--------|------|-------|
| **DeepSeek** | `python run.py` | ❌ | Cheap | Default provider |
| **Gemini CLI** | `LLM_PROVIDER=gemini_cli python run.py` | ✅ | **FREE** | **Recommended!** Local CLI tool |
| **Gemini API** | `LLM_PROVIDER=google python run.py` | ✅ | Free tier | Requires API key from Google AI Studio |
| **OpenAI** | `LLM_PROVIDER=openai python run.py` | ✅ | $$$ | Best quality, but paid |
| **Ollama** | `LLM_PROVIDER=local python run.py` | ❌ | Free | Runs entirely offline |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Desktop App (PyWebView)                                    │
│  ├── Existing solver UI                                     │
│  └── 🎓 AI Tutor Panel (slide-out, right side)              │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP localhost:8000
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  AI Tutor Backend (FastAPI)                                 │
│  ├── /tutor/chat         ← Main endpoint                    │
│  ├── /settings/          ← Provider config                  │
│  └── RAG Engine          ← Curriculum search                │
└──────────────────┬──────────────────────────────────────────┘
                   │ Provider: DeepSeek / Gemini / OpenAI
                   │   OR local: Ollama / Gemini CLI
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  AI Provider                                                │
│  • DeepSeek API (cheap)                                     │
│  • Google Gemini API (free tier)                            │
│  • Google Gemini CLI (free, local)                          │
│  • OpenAI/Anthropic (paid)                                  │
│  • Ollama (local, offline)                                  │
└─────────────────────────────────────────────────────────────┘
```

That's it! The AI tutor is now part of your calculus app.
