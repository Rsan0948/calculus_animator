"""Gradio Space entrypoint for Calculus Animator.

Hosted on Hugging Face Spaces. Mirrors the desktop app's solve pipeline
without spawning the pygame render worker (matplotlib renders the
visualization in-process for headless containers). The AI tutor routes
through the same multi-provider router the desktop app uses.

Configuration (set as Space secrets):
    LLM_PROVIDER          one of: deepseek, google, openai, anthropic
    DEEPSEEK_API_KEY
    GOOGLE_API_KEY
    OPENAI_API_KEY
    ANTHROPIC_API_KEY
"""

import os
import tempfile

import gradio as gr
import matplotlib

matplotlib.use("Agg")  # headless backend for container environments
import matplotlib.pyplot as plt  # noqa: E402

# ─── Gradio-client schema-introspection workaround ──────────────────────────
# gradio_client/utils.py:_json_schema_to_python_type does not guard against
# JSON Schema's bool form (additionalProperties: true). On Python 3.13 +
# Pydantic 2.x the generated schemas occasionally contain bool entries,
# which then crash the API-info endpoint with
# "TypeError: argument of type 'bool' is not iterable". Patching here makes
# the helper bail to "Any" for any non-dict schema so the UI keeps serving.
import gradio_client.utils as _gradio_client_utils  # noqa: E402

_original_json_schema_to_python_type = _gradio_client_utils._json_schema_to_python_type


def _safe_json_schema_to_python_type(schema, defs=None):  # noqa: ANN001 — match upstream sig
    if not isinstance(schema, dict):
        return "Any"
    return _original_json_schema_to_python_type(schema, defs)


_gradio_client_utils._json_schema_to_python_type = _safe_json_schema_to_python_type
# ────────────────────────────────────────────────────────────────────────────

from core.animation_engine import AnimationEngine  # noqa: E402
from core.detector import TypeDetector  # noqa: E402
from core.extractor import ExpressionExtractor  # noqa: E402
from core.parser import ExpressionParser  # noqa: E402
from core.solver import CalculusSolver  # noqa: E402
from core.step_generator import StepGenerator  # noqa: E402


# ─── Solve pipeline ─────────────────────────────────────────────────────────
# Module-level singletons mirror api/bridge.py:CalculusAPI.__init__ but skip
# the persistent render-worker spawn (pygame is unreliable in headless
# containers).

_parser = ExpressionParser()
_detector = TypeDetector()
_extractor = ExpressionExtractor()
_solver = CalculusSolver()
_step_gen = StepGenerator()
_animator = AnimationEngine()


def _solve_expression(latex_str: str) -> dict:
    """Run the solve pipeline; mirrors CalculusAPI.solve without render hop."""
    detected = _detector.detect(latex_str, None)
    inner_latex, merged = _extractor.extract(latex_str, None, {})
    parsed = _parser.parse(inner_latex)
    if not parsed.get("success"):
        return {"success": False, "error": parsed.get("error", "Parse failed")}
    expr = parsed["sympy_expr"]
    result = _solver.solve(expr, detected, merged)
    if not result.get("success"):
        return result
    anim_steps = _step_gen.generate(result, detected)
    result["animation_steps"] = [s.to_dict() for s in anim_steps]
    result["result"] = str(result["result"])
    result["detected_type"] = detected.name
    try:
        gd = _animator.generate_graph_data(expr)
        if gd.get("success"):
            result["graph_original"] = gd
    except (ValueError, TypeError, AttributeError):
        pass
    return result


def _format_steps(steps: list) -> str:
    """Render solver step dicts as readable Markdown."""
    if not steps:
        return "_(no detailed steps available)_"
    lines: list[str] = []
    for i, step in enumerate(steps, 1):
        desc = step.get("description") or step.get("rule", "step")
        lines.append(f"**{i}. {desc}**")
        if step.get("before"):
            lines.append(f"&nbsp;&nbsp;&nbsp;&nbsp;Before: `{step['before']}`")
        if step.get("after"):
            lines.append(f"&nbsp;&nbsp;&nbsp;&nbsp;After: `{step['after']}`")
        lines.append("")
    return "\n".join(lines)


def _plot_graph(graph_data: dict, title: str) -> str:
    """Plot the solver's x/y data via matplotlib; return temp PNG path."""
    fig, ax = plt.subplots(figsize=(8, 5), dpi=110)
    xs = graph_data.get("x", []) or []
    ys = graph_data.get("y", []) or []
    cleaned = [(x, y) for x, y in zip(xs, ys) if y is not None]
    if cleaned:
        xs2, ys2 = zip(*cleaned)
        ax.plot(xs2, ys2, linewidth=2.0, color="#3b82f6")
    ax.axhline(0, color="#888", linewidth=0.5)
    ax.axvline(0, color="#888", linewidth=0.5)
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("f(x)")
    out = tempfile.NamedTemporaryFile(
        prefix="calc_anim_", suffix=".png", delete=False
    )
    fig.savefig(out.name, bbox_inches="tight")
    plt.close(fig)
    return out.name


def solve_and_animate(expression: str):
    """Gradio handler: parse + solve + render visualization."""
    if not (expression or "").strip():
        return "Enter a calculus expression to begin.", None
    try:
        result = _solve_expression(expression)
        if not result.get("success"):
            return (
                f"Could not solve: **{result.get('error', 'unknown error')}**",
                None,
            )
        steps_md = _format_steps(result.get("steps", []))
        title = f"{result.get('detected_type', 'Result')}: {result.get('result', '')}"
        graph = result.get("graph_original", {})
        png = _plot_graph(graph, title) if graph.get("success") else None
        return steps_md, png
    except Exception as e:  # noqa: BLE001 — surface any error cleanly to the UI
        return f"Error: {e}", None


# ─── AI Tutor pipeline ──────────────────────────────────────────────────────
# Defer importing the router until first use so the Space can boot even if
# no provider keys are configured. The user gets a clear error in the tutor
# tab rather than a launch crash.


def chat(message: str, history: list) -> str:
    """Gradio handler: route the user's message through the LLM router."""
    if not (message or "").strip():
        return ""
    try:
        from ai_tutor.providers.router import generate

        ctx_lines: list[str] = []
        for turn in history or []:
            if isinstance(turn, dict):
                role = str(turn.get("role", "user")).upper()
                content = str(turn.get("content", ""))
            elif isinstance(turn, (list, tuple)) and len(turn) == 2:
                # Older "tuples" history format: [user_msg, bot_msg]
                ctx_lines.append(f"USER: {turn[0]}")
                ctx_lines.append(f"ASSISTANT: {turn[1]}")
                continue
            else:
                continue
            ctx_lines.append(f"{role}: {content}")
        ctx = "\n".join(ctx_lines)
        prompt = f"{ctx}\n\nUSER: {message}\n\nASSISTANT:" if ctx else message
        return str(generate(prompt, mode="fast"))
    except Exception as e:  # noqa: BLE001 — surface tutor errors as chat replies
        provider = os.getenv("LLM_PROVIDER", "(unset)")
        return (
            f"AI tutor error: {e}\n\n"
            f"Active provider: `{provider}`. Make sure `LLM_PROVIDER` and the "
            "matching API key are set in the Space secrets — for example, "
            "`LLM_PROVIDER=deepseek` + `DEEPSEEK_API_KEY=...`."
        )


# ─── Gradio Blocks UI ───────────────────────────────────────────────────────
with gr.Blocks(title="Calculus Animator", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        "# Calculus Animator\n\n"
        "Symbolic calculus solver with step-by-step solutions and an AI tutor. "
        "Source: [github.com/Rsan0948/calculus_animator]"
        "(https://github.com/Rsan0948/calculus_animator)"
    )

    with gr.Tab("Solve"):
        with gr.Row():
            with gr.Column():
                expr_input = gr.Textbox(
                    label="Calculus expression (LaTeX)",
                    placeholder=r"\frac{d}{dx}(x^2 \sin x)",
                    lines=2,
                )
                solve_btn = gr.Button("Solve", variant="primary")
                steps_output = gr.Markdown()
            with gr.Column():
                visualization = gr.Image(label="Visualization", type="filepath")

        gr.Examples(
            examples=[
                [r"\frac{d}{dx}(x^3 \sin x)"],
                [r"\int x^2 e^x \, dx"],
                [r"\lim_{x \to 0} \frac{\sin x}{x}"],
                [r"\int_0^1 x^2 \, dx"],
                [r"\frac{d}{dx} \tan(x^2 + 1)"],
            ],
            inputs=[expr_input],
        )

        solve_btn.click(
            solve_and_animate,
            inputs=[expr_input],
            outputs=[steps_output, visualization],
        )

    with gr.Tab("AI Tutor"):
        gr.Markdown(
            "Ask any calculus question. Powered by the same multi-provider "
            "LLM router as the desktop app. Provider is selected via the "
            "`LLM_PROVIDER` Space secret."
        )
        gr.ChatInterface(chat, type="messages")


if __name__ == "__main__":
    # show_api=False sidesteps Gradio's auto-introspection of handler
    # signatures, which trips a bool-vs-dict bug in some Pydantic 2.x +
    # Python 3.13 combinations. The Space UI is unaffected.
    demo.launch(server_name="0.0.0.0", server_port=7860, show_api=False)
