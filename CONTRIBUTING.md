# Contributing to Research Engine

Thank you for your interest in contributing! This document will help you get started.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- GOOGLE_API_KEY (for LLM features)

### Local Development

```bash
# Clone the repository
git clone https://github.com/rubensanchez/research-engine.git
cd research-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev,llm,pdf,guardrails]"

# Set environment variables
export GOOGLE_API_KEY="your-key"

# Run tests
pytest tests/unit/ -v

# Try the CLI
research-engine quickstart
```

## Project Structure

```
research_engine/
├── engine/              # Core state management
├── math_engine/         # Math plugins and routing
├── ingestion/           # PDF processing pipeline
├── mvp_generator/       # AI agent swarms
├── helicops_critic/     # Quality enforcement
├── cli.py              # Command-line interface
└── tests/              # Test suites
```

## Adding a New Math Plugin

1. Create a new directory in `math_engine/plugins/`
2. Implement `plugin.py` with the `MathPlugin` interface
3. Add to `math_engine/plugin_registry.py`
4. Add tests in `tests/unit/test_your_plugin.py`
5. Update documentation

Example plugin structure:

```python
from math_engine.base_plugin import MathPlugin
from engine.state import FormalizedProblem, MathResult, MathStep

class MyDomainPlugin(MathPlugin):
    @property
    def name(self) -> str:
        return "my_domain"
    
    @property
    def supported_domains(self) -> list[str]:
        return ["my_domain", "related_tags"]
    
    def can_solve(self, problem: FormalizedProblem) -> float:
        # Return confidence score 0.0-1.0
        pass
    
    def solve(self, problem: FormalizedProblem) -> MathResult:
        # Implement solving logic
        pass
```

## Code Style

We use:
- **ruff** for linting and formatting
- **mypy** for type checking

```bash
# Run linting
ruff check .

# Run type checking
mypy engine/ math_engine/ ingestion/

# Auto-fix issues
ruff check . --fix
```

## Testing

All code must include tests:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_input_parser.py -v

# Run with coverage
pytest tests/ --cov=research_engine --cov-report=html
```

### Test Guidelines

- Unit tests: Test individual functions in isolation
- Integration tests: Test full pipeline end-to-end
- Benchmarks: Ensure performance doesn't regress

## Pull Request Process

1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/amazing-feature`)
3. **Make your changes** with tests
4. **Run tests** locally (`pytest tests/ -v`)
5. **Commit** with clear messages (`git commit -m "Add feature X"`)
6. **Push** to your fork (`git push origin feature/amazing-feature`)
7. **Open a Pull Request** with description of changes

## Reporting Issues

When reporting bugs, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages (if any)

## Code of Conduct

Be respectful and constructive. We're all here to build something useful!

## Questions?

- Open an issue for questions
- Check existing documentation in `docs/`
- Review test files for usage examples
