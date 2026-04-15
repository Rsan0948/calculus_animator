# AI Tutor for Calculus Animator

Socratic AI tutoring system with multi-modal context (screenshots + solver state) and RAG-based concept retrieval.

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Desktop App   │──────│  FastAPI Backend │──────│  LLM Providers  │
│  (PyWebView)    │      │   (ai_tutor/)    │      │ (OpenAI/Anthropic
└─────────────────┘      └──────────────────┘      │  /Ollama/etc)   │
         │                        │                 └─────────────────┘
         │                        │                          │
         │ Capture screenshot     │ Retrieve concepts        │
         │ + solver state         │ from RAG                 │ Generate
         │                        │                          │ Socratic
         │                        │                          │ response
         ▼                        ▼                          │
┌────────────────────────────────────────────────────────────┘
│  ZDS Components:
│  • TOOL-102: Doctrine RAG Stack (hybrid retrieval)
│  • TOOL-305: Intelligent Cloud Failover
│  • TOOL-405: Teacher-in-the-Loop (TITL)
│  • TOOL-302: Interface-Agnostic Core
└───────────────────────────────────────────────────────────────
```

## Quick Start

### 1. Install Dependencies

```bash
cd ~/Desktop/calculus_animator
pip install -r requirements.txt
```

### 2. Configure API Keys (optional)

```bash
export OPENAI_API_KEY="sk-..."      # For GPT-4V vision support
export ANTHROPIC_API_KEY="sk-..."   # For Claude 3
# Or use local models with Ollama (no key needed)
```

### 3. Build RAG Index

```bash
python -m ai_tutor.services.ingest
```

This parses `curriculum.txt` and `calculus_library.json` into searchable ConceptCards.

### 4. Run

```bash
# Both backend and desktop
python run_ai_tutor.py

# Backend only
python run_ai_tutor.py --backend

# With RAG rebuild
python run_ai_tutor.py --ingest
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check + status |
| `POST /tutor/chat` | Main tutoring endpoint |
| `POST /tutor/chat/vision` | Tutoring with screenshot analysis |
| `POST /tutor/chat/stream` | Streaming response |
| `GET /tutor/concepts/search?q=...` | Search concept cards |
| `GET /settings/` | Get current configuration |
| `POST /settings/provider` | Update LLM provider |

## RAG Pipeline

1. **Ingest**: Parse curriculum → ConceptCards with metadata
2. **Index**: Vector embeddings (ChromaDB) + SQLite FTS5
3. **Retrieve**: Hybrid search (semantic + keyword + trigger matching)
4. **Rerank**: Cross-encoder for final ranking
5. **Generate**: Socratic prompt with retrieved concepts

## Socratic Prompting

The tutor uses constrained prompting to guide rather than answer:

❌ **Bad**: "The derivative of x²sin(x) is 2xsin(x) + x²cos(x)"

✅ **Good**: "You're working with a product of two functions. What does the product rule tell you about handling each part?"

## Configuration

Set via environment variables or `/settings/` endpoint:

```python
{
    "provider": "openai",  # or "anthropic", "local", etc.
    "fast_model": "gpt-4o-mini",
    "power_model": "gpt-4o",
    "vision_model": "gpt-4o",
    "socratic_mode": True,  # False = direct answers
    "max_context_cards": 3
}
```

## File Structure

```
ai_tutor/
├── __init__.py
├── main.py                 # FastAPI app
├── config.py               # Settings management
├── providers/
│   └── router.py           # Multi-provider LLM routing + failover
├── rag/
│   ├── vector_store.py     # ChromaDB wrapper
│   └── concept_engine.py   # RAG pipeline (Doctrine pattern)
├── routers/
│   ├── tutor.py            # Chat endpoints
│   └── settings_router.py  # Config endpoints
├── services/
│   └── ingest.py           # Curriculum ingestion
└── README.md
```

## ZDS IP Portfolio

This implementation demonstrates:

- **TOOL-102**: Production-grade RAG with quality gates
- **TOOL-302**: Unified backend serving multiple interfaces
- **TOOL-305**: Intelligent failover (local → cloud)
- **TOOL-303**: Local-first privacy (ChromaDB, optional cloud)
- **TOOL-401**: Resolution-independent rendering
- **TOOL-405**: Teacher-in-the-Loop reactive tutoring
- **TOOL-903**: Secrets guardrail (env vars, no hardcoded keys)
