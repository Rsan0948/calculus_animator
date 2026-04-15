# Research Engine

Automated research paper formalization, mathematical solving, and MVP generation. The primary product surface is the `research-engine` CLI and the persisted workflow behind it.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Current Product Boundary

The current source of truth is:
- `cli.py`
- `startup_checks.py`
- `engine/`
- `ingestion/`
- `math_engine/`
- `mvp_generator/`
- `helicops_critic/`

Legacy and transitional modules still exist in the repo, including `ai_tutor/`, `api/`, `slide_renderer/`, `ui/`, `window.py`, and `calculus_animator/`. They are not the primary product boundary for current development.

## What The Active Platform Does

1. Validates and ingests research PDFs.
2. Extracts and formalizes structured mathematical problems.
3. Routes problems through domain-specific math plugins.
4. Generates MVP implementations from solved results.
5. Persists run history, artifacts, and quality reports.
6. Audits generated output with HelicOps and math validation.

## Main CLI Paths

```bash
research-engine solve "derivative of x^3"
research-engine run paper.pdf
research-engine runs
research-engine show-run <run-id>
research-engine resume <run-id>
research-engine retry-stage <run-id> formalize
research-engine domains
research-engine surfaces
```

`pipeline` remains available as a compatibility wrapper around `run`.

## Quick Start

```bash
pip install -e ".[dev]"
research-engine solve "derivative of x^3"
research-engine domains
```

For document workflows:

```bash
pip install -e ".[dev,llm,pdf,guardrails]"
export GOOGLE_API_KEY="your-key"
research-engine run paper.pdf
```

## Documentation

Operational and handoff docs:
- [User Guide](docs/user-guide.md)
- [Architecture Guide](docs/architecture.md)
- [Code Map](docs/code-map.md)
- [Run Lifecycle](docs/run-lifecycle.md)
- [Ingestion And Formalization](docs/ingestion-formalization.md)
- [Math Engine](docs/math-engine.md)
- [MVP Generation And Audit](docs/mvp-generation.md)

## Domain Coverage

Reliable:
- Calculus
- Number Theory
- Logic

Beta:
- Linear Algebra
- Statistics
- Combinatorics
- Graph Theory

Experimental:
- Optimization

Use `research-engine domains` for the current in-code support map.

## Project Structure

```text
engine/             Shared models, persistence, run graph orchestration
ingestion/          PDF extraction, chunking, validation, formalization
math_engine/        Router, parser, registry, and domain plugins
mvp_generator/      Multi-agent MVP generation and local validators
helicops_critic/    HelicOps integration and math-oracle validation
cli.py              Primary entry point for the product
```

## Development

```bash
pytest tests/ -v
```

When working on the active product path, prioritize:
- `tests/integration/test_cli.py`
- `tests/unit/test_run_service.py`
- `tests/unit/test_state_manager.py`
- `tests/unit/test_formalizer.py`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

## License

Apache 2.0. See [LICENSE](LICENSE) for details.
