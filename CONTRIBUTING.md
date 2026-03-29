# Contributing to Calculus Animator

Thank you for your interest in contributing! This document provides guidelines and workflows for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Testing Requirements](#testing-requirements)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Architecture Guidelines](#architecture-guidelines)
- [AI Integration Guidelines](#ai-integration-guidelines)
- [Release Process](#release-process)

## Code of Conduct

This project and everyone participating in it is governed by our commitment to:

- **Be respectful**: Constructive criticism is welcome; personal attacks are not
- **Be collaborative**: This is an educational tool; prioritize learning outcomes
- **Be patient**: Reviewers are volunteers; response times may vary
- **Focus on the problem**: Mathematical correctness and pedagogical value matter most

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- A LaTeX distribution (for testing parser edge cases)

### Setup Development Environment

```bash
# 1. Fork and clone
git clone https://github.com/your-username/calculus_animator.git
cd calculus_animator

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Run tests to verify setup
python scripts/run_tests.py quick

# 5. Start the application
python run.py
```

## Development Workflow

### Branch Naming

- `feature/description` — New features or enhancements
- `fix/description` — Bug fixes
- `docs/description` — Documentation improvements
- `refactor/description` — Code refactoring
- `test/description` — Test additions or improvements

Example: `feature/add-partial-derivatives`, `fix/integral-constant-handling`

### Commit Messages

Follow conventional commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `style:` Code style (formatting, missing semicolons, etc.)
- `refactor:` Code refactoring
- `test:` Adding or correcting tests
- `chore:` Build process or auxiliary tool changes

**Examples:**
```
feat(solver): add support for implicit differentiation

fix(parser): handle escaped braces in LaTeX input

docs(readme): update AI tutor setup instructions

test(animation): add edge case for empty expression
```

## Testing Requirements

All contributions must include appropriate tests.

### Test Categories

| Change Type | Required Tests | Example |
|-------------|----------------|---------|
| Core logic changes | Unit tests | New differentiation rule → `test_solver.py` |
| Parser changes | Unit + fuzz tests | LaTeX pattern → `test_parser.py` + hypothesis |
| API changes | Integration tests | New endpoint → `test_e2e_backend_smoke.py` |
| UI changes | E2E tests | Button behavior → `test_e2e_ui_smoke.py` |
| Rendering changes | Snapshot tests | Visual output → snapshot regression |

### Running Tests Locally

```bash
# Before committing, always run:
python scripts/run_tests.py quick

# Before PR, run full suite:
python scripts/run_tests.py full

# If you modified the parser:
python scripts/run_tests.py fuzz

# If you modified the bridge API:
python scripts/run_tests.py e2e
```

### Test Coverage

- New features: Minimum 80% coverage
- Bug fixes: Must include regression test
- Refactoring: Coverage must not decrease

Check coverage:
```bash
pytest --cov=api --cov=core --cov-report=html
open htmlcov/index.html
```

## Code Style

We use automated tooling to enforce consistency.

### Linting and Formatting

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check . --fix

# Format code
ruff format .
```

### Type Hints

All new code must include type annotations:

```python
# Good
def solve_derivative(expr: sympy.Expr, var: sympy.Symbol) -> Solution:
    ...

# Avoid
def solve_derivative(expr, var):
    ...
```

Run type checker:
```bash
mypy api core
```

### Documentation

- Public functions: Google-style docstrings
- Complex logic: Inline comments explaining "why", not "what"
- Type annotations: Required for all public APIs

```python
def extract_steps(solution: sympy.Expr) -> list[Step]:
    """Extract pedagogical steps from a SymPy solution.
    
    Converts SymPy's internal computation trace into a sequence
    of human-readable steps suitable for animation.
    
    Args:
        solution: The solved expression from SymPy
        
    Returns:
        Ordered list of Step objects containing LaTeX representations,
        explanations, and timing information for animation.
        
    Raises:
        ExtractionError: If the solution trace cannot be parsed
        
    Example:
        >>> sol = sympy.diff(x**2 * sin(x), x)
        >>> steps = extract_steps(sol)
        >>> len(steps)
        3  # Product rule, power rule, sine derivative
    """
    ...
```

## Pull Request Process

### Before Submitting

1. **Sync with main:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run quality checks:**
   ```bash
   python scripts/run_quality.py
   ```

3. **Update documentation:**
   - README.md if user-facing changes
   - ARCHITECTURE.md if structural changes
   - docs/AI_TUTOR_QUICKSTART.md if AI features modified

4. **Verify no regressions:**
   ```bash
   python scripts/run_tests.py full
   ```

### PR Description Template

```markdown
## Summary
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactoring
- [ ] Performance improvement

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] E2E tests pass (if UI/API changes)
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Type hints added
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

## Screenshots (if UI changes)
[Add screenshots]

## Additional Notes
[Any context reviewers need]
```

### Review Process

1. **Automated checks** must pass (CI runs tests and linting)
2. **At least one review** from a maintainer
3. **Mathematical correctness** verified for solver changes
4. **Performance impact** assessed for rendering changes
5. **Accessibility** considered for UI changes

## Architecture Guidelines

### Adding New Calculus Operations

1. **Parser** (`core/parser.py`): Add LaTeX pattern recognition
2. **Detector** (`core/detector.py`): Add operation classification
3. **Solver** (`core/solver.py`): Implement SymPy logic + step extraction
4. **Step Generator** (`core/step_generator.py`): Define animation sequence
5. **Tests**: Add to `test_solver.py`, `test_parser.py`
6. **Documentation**: Update README.md operations table

### Adding New AI Providers

1. **Create provider class** (`ai_tutor/providers/`):
   ```python
   class NewProvider(BaseProvider):
       def __init__(self, config: dict):
           ...
       
       async def chat(self, messages: list, **kwargs) -> str:
           ...
       
       def supports_vision(self) -> bool:
           ...
   ```

2. **Register in router** (`ai_tutor/providers/router.py`)

3. **Add configuration** (`ai_tutor/config.py`)

4. **Update documentation**: `docs/AI_TUTOR_QUICKSTART.md`

5. **Add tests**: Mock provider for unit tests

### Worker Subprocess Pattern

When adding new CPU-intensive operations:

1. **Create worker module** (`api/new_worker.py`)
2. **Implement IPC**: JSON-serializable request/response
3. **Handle timeouts**: Set appropriate limits
4. **Clean up resources**: Always terminate workers
5. **Add health checks**: `/health` endpoint for worker status

Example:
```python
# api/new_worker.py
def main():
    while True:
        request = json.loads(sys.stdin.readline())
        try:
            result = process(request)
            print(json.dumps({"status": "ok", "result": result}))
        except Exception as e:
            print(json.dumps({"status": "error", "error": str(e)}))
        sys.stdout.flush()
```

## AI Integration Guidelines

### Prompt Engineering

- **Version prompts**: Include version number in prompts
- **Test for consistency**: Same input should yield similar output
- **Handle edge cases**: Empty input, very long input, special characters
- **Respect rate limits**: Implement exponential backoff

### RAG Best Practices

- **Chunk size**: 500-1000 tokens for curriculum content
- **Overlap**: 10-20% overlap between chunks
- **Metadata**: Include concept type, difficulty, prerequisites
- **Relevance threshold**: Minimum 0.7 cosine similarity

### Vision Pipeline

- **Image validation**: Check size/format before sending
- **Compression**: Scale large images to <1MB
- **Privacy**: Never send student work to third parties without consent
- **Fallback**: Text-only mode if vision fails

## Release Process

### Version Numbering

We follow [SemVer](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- Major: Breaking changes
- Minor: New features, backward compatible
- Patch: Bug fixes

### Release Checklist

```bash
# 1. Update version
# Edit pyproject.toml and __init__.py

# 2. Run full QA
python scripts/run_release_checklist.py

# 3. Update CHANGELOG.md

# 4. Create git tag
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin v1.2.0

# 5. Build release
python scripts/build_release.py

# 6. Create GitHub release with binaries
```

## Questions?

- **Technical questions**: Open a [Discussion](https://github.com/Rsan0948/calculus_animator/discussions)
- **Bug reports**: Open an [Issue](https://github.com/Rsan0948/calculus_animator/issues)
- **Security issues**: Email directly (see SECURITY.md)

## Recognition

Contributors will be recognized in:
- README.md Contributors section
- Release notes
- Project documentation

Thank you for helping make math education more accessible!
