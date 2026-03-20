# Calculus Animator

An interactive desktop app for visualizing and animating calculus problem-solving step by step. Enter a LaTeX expression, and the app automatically detects the operation, solves it symbolically, and walks through each step with animated transitions and live graphs.

## Features

- **Auto-detection** — paste any calculus expression and the app identifies what operation to perform
- **Step-by-step animation** — each rule application (product rule, chain rule, substitution, etc.) is animated with timing and visual highlights
- **Live graphs** — original function, derivative, antiderivative, area fills, and limit approach lines rendered in real time
- **8 operation types** — derivatives (including higher-order and partial), indefinite/definite integrals, limits, series expansions, Taylor/Maclaurin series, ordinary differential equations, and simplification
- **Learning curriculum** — structured slide-based lessons with a built-in formula library and math symbol reference
- **Demo problems** — curated collection of worked examples to explore

## Requirements

- Python 3.13
- macOS, Windows, or Linux

## Installation

```bash
git clone https://github.com/Rsan0948/calculus_animator.git
cd calculus_animator
pip install -r requirements.txt
python run.py
```

`run.py` checks for missing dependencies and installs them automatically before launching.

For packaged/frozen builds, see [BUILD.md](BUILD.md).

## Usage

**Problem Solver tab**

1. Type or paste a LaTeX expression into the input field (e.g. `\frac{d}{dx} x^3 \sin x`)
2. The operation type is detected automatically — or select one manually from the dropdown
3. Press **Solve** to generate the step-by-step solution
4. Use the playback controls to step through the animation or let it run automatically
5. The graph panel updates live alongside the solution

**Learning tab**

Browse the curriculum pathways, formula library, and symbol reference. Each slide is rendered with the same visual engine used for animations.

## Supported Operations

| Operation | Example input |
|---|---|
| Derivative | `\frac{d}{dx} x^3 \sin x` |
| Higher-order derivative | `\frac{d^2}{dx^2} e^x \cos x` |
| Indefinite integral | `\int x^2 e^x \, dx` |
| Definite integral | `\int_0^1 x^2 \, dx` |
| Limit | `\lim_{x \to 0} \frac{\sin x}{x}` |
| Series expansion | `\sum_{n=0}^{\infty}` or series around a point |
| Taylor / Maclaurin series | `e^x`, `\sin x`, any differentiable function |
| ODE | `y' - 2y = 0` |
| Simplify | any algebraic expression |

## Development

**Run tests**

```bash
python run_tests.py quick      # fast unit + integration suite
python run_tests.py full       # includes snapshot regressions
python run_tests.py fuzz       # property-based fuzz tests (slow)
python run_tests.py e2e        # end-to-end backend smoke tests
```

**Lint and type check**

```bash
ruff check .
mypy api core
```

**Project structure**

```
calculus_animator/
├── run.py                  # dev entry point (auto-installs deps)
├── app_main.py             # packaged entry point
├── config.py               # global constants
├── slide_renderer.py       # pygame-based slide rendering engine
├── api/
│   ├── bridge.py           # Python ↔ JavaScript API bridge
│   ├── slide_render_worker.py     # subprocess worker: renders slides
│   └── capacity_slide_worker.py   # subprocess worker: measures text fit
├── core/
│   ├── parser.py           # LaTeX → SymPy expression parser
│   ├── detector.py         # auto-detects calculus operation type
│   ├── extractor.py        # extracts inner expression and parameters
│   ├── solver.py           # SymPy-based solver with step extraction
│   ├── step_generator.py   # converts solver steps to animation frames
│   ├── animation_engine.py # graph data generation
│   └── slide_highlighting.py  # slide content scoring and extraction
├── ui/
│   ├── index.html
│   ├── js/app.js
│   └── css/styles.css
├── data/                   # JSON data files (curriculum, formulas, symbols, demos)
└── tests/                  # full test suite (unit, integration, E2E, fuzz, perf)
```

## License

MIT — see [LICENSE](LICENSE).
