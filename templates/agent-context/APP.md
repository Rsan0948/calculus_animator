# Application Architecture — [PROJECT NAME]

> This document gives AI agents a detailed map of the application architecture.
> Update it whenever modules, data models, or key interfaces change.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.11+ |
| API Framework | [e.g., FastAPI] | [version] |
| Database | [e.g., PostgreSQL] | [version] |
| ORM | [e.g., SQLAlchemy] | [version] |
| Task Queue | [e.g., Celery + Redis] | [version] |
| Frontend | [e.g., React + TypeScript] | [version] |
| Containerization | Docker | latest |
| CI/CD | GitHub Actions | — |

---

## Repository Structure

```
[project-name]/
├── src/
│   └── [package]/
│       ├── __init__.py
│       ├── api/              # HTTP layer (routes, middleware, schemas)
│       ├── core/             # Business logic (no framework dependencies here)
│       ├── db/               # Models, migrations, session management
│       ├── services/         # External integrations (email, storage, third-party APIs)
│       └── utils/            # Shared utilities (logging, config, helpers)
├── tests/
│   ├── unit/                 # Tests for core/ (fast, no DB)
│   ├── integration/          # Tests for API layer (uses test DB)
│   └── conftest.py           # Shared fixtures
├── migrations/               # Alembic database migrations
├── scripts/                  # One-off scripts and tooling
├── docs/                     # Documentation
├── guardrails/               # Engineering guardrails (from engineering-guardrails)
├── metrics/                  # DORA metrics (from engineering-guardrails)
├── .env.example              # Required environment variables
├── pyproject.toml            # Project config and dependencies
└── AGENTS.md                 # AI agent context (read this first)
```

---

## Key Modules

### `src/[package]/api/`

**Purpose:** HTTP layer — routes, request validation, response serialization.

**Rules:**
- Routes delegate immediately to `core/` or `services/` — no business logic here
- All request/response types defined as Pydantic models in `schemas.py`
- Authentication handled in `middleware/auth.py`

**Key files:**
- `main.py` — FastAPI app setup, middleware registration
- `routes/` — one file per resource (e.g., `users.py`, `orders.py`)
- `schemas.py` — Pydantic request/response models
- `middleware/` — auth, logging, error handling

### `src/[package]/core/`

**Purpose:** Pure business logic — no HTTP, no DB, no external dependencies.

**Rules:**
- Functions here take plain Python types, return plain Python types
- No imports from `api/` or `db/` — dependencies flow one way
- All business rules and invariants enforced here

### `src/[package]/db/`

**Purpose:** Database models and session management.

**Rules:**
- Use SQLAlchemy 2.0 style (not legacy `session.query()`)
- All migrations in `migrations/` via Alembic
- Never raw SQL strings — use parameterized queries or ORM

### `src/[package]/services/`

**Purpose:** External integrations.

**Rules:**
- Each service has a client class with explicit interface
- All credentials from environment variables — never hardcoded
- Services are mockable — tests use dependency injection, not monkey-patching

---

## Data Flow

```
HTTP Request
    ↓
API Routes (validation, auth check)
    ↓
Core Logic (business rules, orchestration)
    ↓
Services/DB (external calls, persistence)
    ↓
HTTP Response
```

---

## Database Schema

> Replace with your actual schema.

```
users
  id           UUID PK
  email        VARCHAR(255) UNIQUE NOT NULL
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()

[table_name]
  id           UUID PK
  user_id      UUID FK -> users.id
  ...
```

---

## External Services

| Service | Purpose | Credentials |
|---------|---------|-------------|
| [e.g., SendGrid] | [e.g., Transactional email] | `SENDGRID_API_KEY` env var |
| [e.g., AWS S3] | [e.g., File storage] | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| [e.g., Stripe] | [e.g., Payments] | `STRIPE_SECRET_KEY` |

---

## Environment Variables

All required variables are in `.env.example`. Copy to `.env` for local development.

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# [Service 1]
SERVICE_1_API_KEY=

# [Service 2]
SERVICE_2_BASE_URL=https://api.service2.com
```

**Never hardcode these values.** Use `os.getenv("VAR_NAME")` in code.

---

## Testing Strategy

- **Unit tests** (`tests/unit/`): test `core/` functions in isolation. No DB, no network. Fast.
- **Integration tests** (`tests/integration/`): test API endpoints with a real test database.
- **Coverage target**: 80% minimum (enforced by CI).

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=term-missing
```

---

## Known Constraints

- [e.g., The `payments/` module must not be changed without security review]
- [e.g., The `db/migrations/` files must never be edited after they're applied in prod]
- [e.g., The `services/legacy_api.py` client is read-only — do not refactor it]
