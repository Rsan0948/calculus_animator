# QA Automation Pipeline

This project now supports a tiered automated quality workflow:

## Local Commands

- Install all runtime + dev tooling:
  - `python setup_test_env.py`
- Default quality run (lint + types + tests):
  - `python scripts/run_quality.py`
- Include dependency security audit:
  - `python scripts/run_quality.py --security`
- Default tests (excludes heavy markers):
  - `python scripts/run_tests.py`
- Quick tests:
  - `python scripts/run_tests.py --quick`
- Fuzz only:
  - `python scripts/run_tests.py --fuzz`
- Perf only:
  - `python scripts/run_tests.py --perf`
- E2E only:
  - `python scripts/run_tests.py --e2e`
- Full test suite:
  - `python scripts/run_tests.py --full`
- Release checklist runner (writes report to `reports/release_checklist_latest.md`):
  - `python scripts/run_release_checklist.py`
  - `python scripts/run_release_checklist.py --quick`

## Test Markers

- `fuzz`: property-based parser/extractor resilience tests
- `perf`: performance smoke tests with broad regression thresholds
- `e2e`: browser-level UI shell smoke tests

## CI Workflows

- `.github/workflows/ci.yml`
  - runs on push/PR
  - `ruff` + `mypy` + core/snapshot tests
- `.github/workflows/extended-quality.yml`
  - scheduled + manual
  - fuzz tests, perf tests, dependency audit, and E2E smoke tests
