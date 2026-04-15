# MVP Generation And Audit

This document explains how the code-generation path works after a math problem has been solved.

## Goal

The MVP path is supposed to take a validated `MathResult`, generate a small implementation package, audit it, and preserve enough history to understand what happened across retries.

## Main Files

- `mvp_generator/orchestrator.py`
- `mvp_generator/validators.py`
- `helicops_critic/integration.py`
- `helicops_critic/runner.py`
- `helicops_critic/math_validator.py`

## Orchestrator

`Orchestrator.generate_mvp()` coordinates the full generation loop.

The swarm roles are:
- architect
- algorithm
- tester
- integrator

The orchestrator’s lifecycle is:

1. create a workspace for the problem
2. ask the architect for a design manifest
3. ask the algorithm agent to implement core files
4. ask the tester agent for tests
5. ask the integrator to finalize the package
6. run local pre-write validators
7. write files to disk
8. run the HelicOps critic
9. feed violations back into the next attempt if needed

## Attempt History

Every iteration is recorded as `MVPAttempt`.

The attempt record stores:
- attempt number
- generated file list
- overall pass status
- math validation pass status
- violation count
- violation ids

This matters because the run system now preserves the full attempt history instead of collapsing everything into the final pass/fail result.

## Local Validators

`mvp_generator/validators.py` performs cheap checks before the critic stage.

Current checks:
- oversized files
- Python syntax errors
- missing required files

These checks are intentionally simple. Their job is to catch obvious breakage before the heavier audit runs.

## HelicOps Integration

`helicops_critic/integration.py` is the low-level Python integration layer.

It is supposed to:
- discover Python files in the generated workspace
- load the relevant HelicOps config
- run file-based guardrails
- convert guardrail failures into `Violation` records
- return a `GuardrailReport`

## Critic Runner

`helicops_critic/runner.py` is the higher-level orchestrator-facing wrapper.

It does two things:
- run HelicOps audit
- optionally run math validation against the expected oracle answer

It also maps violations back to the most relevant swarm role so retries are more targeted.

## Math Validator

`helicops_critic/math_validator.py` is a lightweight oracle checker.

It is supposed to:
- run the generated program
- extract an answer from stdout or stderr
- compare it to the solver’s expected final answer
- use SymPy equivalence checks when simple string matching is not enough

This is how the system distinguishes “code that passes style/security checks” from “code that still solves the original math problem.”

## Persisted MVP Outputs

The orchestrator returns `MVPOutput`, which contains:
- problem id
- generation timestamp
- workspace root directory
- generated files
- guardrail report
- attempt history
- install and run commands

`RunService` then converts this into run-stage artifacts and also persists the latest MVP output through `StateManager`.

## Operational Expectations

When someone debugs or extends this layer, these expectations should hold:

- failures should preserve attempt history
- guardrail violations should remain visible after the run ends
- math validation should be treated as part of success, not as optional decoration
- generated workspaces should be inspectable from the run artifacts
- the orchestrator should remain a coordinator, not a place to hide domain logic
