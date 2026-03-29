# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- AI Tutor integration with multi-provider support (DeepSeek, Gemini, OpenAI, Ollama)
- RAG-based curriculum search for context-aware tutoring
- Vision-enabled tutoring with screenshot analysis
- GitHub issue templates and PR template
- Security policy and vulnerability reporting process

### Changed
- Improved subprocess worker isolation for rendering
- Enhanced LaTeX parser edge case handling

### Fixed
- Parser handling of escaped braces in expressions
- Memory leak in slide rendering worker

## [1.0.0] - 2024-03-20

### Added
- Initial release of Calculus Animator
- Auto-detection of 8 calculus operation types
  - Derivatives (including higher-order and partial)
  - Indefinite and definite integrals
  - Limits
  - Series expansions
  - Taylor/Maclaurin series
  - Ordinary differential equations
  - Simplification
- Step-by-step animation with live graphs
- PyWebView-based desktop application
- SymPy integration for symbolic computation
- Subprocess worker architecture for rendering isolation
- FastAPI bridge for Python-JavaScript communication
- Comprehensive test suite
  - Unit tests
  - Integration tests
  - End-to-end tests
  - Property-based fuzz tests
  - Snapshot regression tests
- Cross-platform packaging (Windows, macOS, Linux)
- ruff linting and mypy type checking
- GitHub Actions CI/CD

### Security
- Established security policy for vulnerability reporting

---

## Template for Future Releases

```
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Now removed features

### Fixed
- Bug fixes

### Security
- Security improvements
```
