# Math Engine

This document explains how the active solver layer decides what kind of math problem it has been given and how it executes the correct domain plugin.

## Goal

The math engine should do three things well:
- understand which domain is being requested
- normalize the input into a plugin-friendly shape
- return a `MathResult` with explicit success or failure

The router should not contain domain solving logic. That belongs inside plugins.

## Main Files

- `math_engine/base_plugin.py`
- `math_engine/input_parser.py`
- `math_engine/router.py`
- `math_engine/plugin_registry.py`
- `math_engine/plugins/*/plugin.py`

## Plugin Contract

`MathPlugin` defines the contract every solver must follow.

Required properties and methods:
- `name`
- `supported_domains`
- `can_solve(problem)`
- `solve(problem)`

Expected behavior:
- `can_solve()` returns a score in `[0.0, 1.0]`
- `solve()` returns `MathResult`
- failures are explicit with `success=False` and `failure_reason`
- plugins should not invent hidden defaults for missing required inputs

## Input Normalization

`InputParser` is a rule-based helper, not a general reasoning system.

Its job is to turn obvious natural-language inputs into structured payloads that plugins already know how to consume.

Examples of what it can do:
- extract matrices for linear algebra
- extract lists of numbers for statistics
- recognize graph edges and shortest-path inputs
- normalize logic expressions and operations
- infer simple operations in number theory and combinatorics

Important limitation:
- the parser is intentionally shallow and best used for common CLI-style inputs, not arbitrary free-form mathematical prose

## Routing

`Router` separates analysis from execution.

### `analyze(problem)`

This method:
- scores every registered plugin
- sorts candidates by score
- decides whether a plugin is confident enough to use
- pre-parses the objective into JSON for non-calculus plugins when needed
- returns a structured routing decision payload

This is the right place to inspect routing behavior without executing solver logic.

### `solve_with_analysis(problem, analysis)`

This method:
- trusts a precomputed routing decision
- looks up the selected plugin
- substitutes the normalized objective into a copy of the problem
- executes the plugin
- optionally persists the result through `StateManager`

### `route(problem)`

This is the convenience wrapper that does both steps.

## Plugin Registry

`plugin_registry.py` performs two jobs:

1. registration
   - instantiate and register all available plugins with the router
2. support metadata
   - publish support status, summary text, and recommended input shape for each domain

This metadata is what powers `research-engine domains`.

## Active Plugins

### `calculus`

File:
- `math_engine/plugins/calculus/plugin.py`

Role:
- strongest path in the current system
- still routes through legacy SymPy-oriented calculus code

### `linear_algebra`

Role:
- matrix operations and related algebraic workflows
- prefers structured inputs, but the CLI parser can build them from simple prompts

### `statistics`

Role:
- descriptive statistics, common tests, and simple regression-style inputs
- supports natural-language summaries through parser-assisted input normalization

### `optimization`

Role:
- exploratory optimization support
- not currently a domain to oversell in production workflows

### `number_theory`

Role:
- prime checks, gcd/lcm, factorization, and similar integer workflows

### `combinatorics`

Role:
- permutations, combinations, factorial-related counting, and selected sequences

### `graph_theory`

Role:
- lightweight shortest-path and graph-structure examples
- currently limited in graph modeling richness

### `logic`

Role:
- boolean simplification and satisfiability-style flows
- should fail clearly when parsing cannot interpret the requested expression

## Solver Output Contract

All plugins return `MathResult`.

The important fields are:
- `problem_id`
- `plugin_used`
- `success`
- `final_answer`
- `steps`
- `metadata`
- `failure_reason`

That allows the rest of the system to treat every solver uniformly.

## Where To Change What

When improving the math engine:
- change `InputParser` when the CLI cannot normalize a common prompt shape
- change `Router` when selection logic or routing metadata is wrong
- change a plugin when domain-specific solving behavior is wrong
- change `plugin_registry.py` when support status or domain visibility should change

Do not hide plugin weaknesses in the router. The router should describe uncertainty, not fake confidence.
