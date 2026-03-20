"""Isolated pygame slide renderer worker.

Reads JSON payload from stdin and writes JSON to stdout:
{
  "chapter_title": str,
  "slide_title": str,
  "slide_index": int,
  "slide_total": int,
  "content_blocks": [...],
  "graphics": [...],
  "width": int,
  "height": int
}
"""
from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
_log = logging.getLogger(__name__)


_SUP_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "(": "⁽", ")": "⁾", "=": "⁼",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "i": "ⁱ",
    "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ",
    "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
    "A": "ᴬ", "B": "ᴮ", "D": "ᴰ", "E": "ᴱ", "G": "ᴳ", "H": "ᴴ", "I": "ᴵ", "J": "ᴶ", "K": "ᴷ",
    "L": "ᴸ", "M": "ᴹ", "N": "ᴺ", "O": "ᴼ", "P": "ᴾ", "R": "ᴿ", "T": "ᵀ", "U": "ᵁ", "V": "ⱽ", "W": "ᵂ",
}

_SUB_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "(": "₍", ")": "₎", "=": "₌",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ",
    "o": "ₒ", "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}


def _to_sup(raw: str) -> str:
    return "".join(_SUP_MAP.get(ch, ch) for ch in str(raw))


def _to_sub(raw: str) -> str:
    return "".join(_SUB_MAP.get(ch, ch) for ch in str(raw))


def _pretty_math_text(text: str) -> str:
    s = str(text or "")
    s = s.replace("\\left", "").replace("\\right", "").replace("\\,", " ")
    s = s.replace("\\cdot", "·").replace("\\times", "×")
    s = s.replace("\\pi", "π").replace("\\infty", "∞")
    s = re.sub(r"\\to|\\rightarrow|->", "→", s)
    s = s.replace("\\lim", "lim").replace("\\int", "∫")
    s = s.replace("\\sin", "sin").replace("\\cos", "cos").replace("\\tan", "tan")
    s = s.replace("\\ln", "ln").replace("\\log", "log").replace("\\sqrt", "√")
    s = re.sub(
        r"\\frac\{d(?:\^(\d+)|\{([^{}]+)\})?\}\{d([a-zA-Z])(?:\^(\d+)|\{([^{}]+)\})?\}",
        lambda m: f"d{('^(' + (m.group(1) or m.group(2) or m.group(4) or m.group(5)) + ')') if (m.group(1) or m.group(2) or m.group(4) or m.group(5)) else ''}/d{m.group(3)}{('^(' + (m.group(1) or m.group(2) or m.group(4) or m.group(5)) + ')') if (m.group(1) or m.group(2) or m.group(4) or m.group(5)) else ''}",
        s,
    )
    # simple latex fraction flattening first
    for _ in range(6):
        ns = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", s)
        if ns == s:
            break
        s = ns
    s = s.replace("{", "(").replace("}", ")")
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)
    # pretty fractions: (a)/(b) -> a⁄b (with superscript/subscript where possible)
    for _ in range(6):
        ns = re.sub(
            r"\(([^()]+)\)\s*/\s*\(([^()]+)\)",
            lambda m: f"{_to_sup(m.group(1).strip())}⁄{_to_sub(m.group(2).strip())}",
            s,
        )
        if ns == s:
            break
        s = ns
    s = re.sub(
        r"(^|[\s=+\-*(])([a-zA-Z0-9.]+)\s*/\s*([a-zA-Z0-9.]+)(?=$|[\s=+\-*)])",
        lambda m: f"{m.group(1)}{_to_sup(m.group(2))}⁄{_to_sub(m.group(3))}",
        s,
    )
    # exponents/subscripts
    s = re.sub(r"\^\{([^}]+)\}", lambda m: _to_sup(m.group(1)), s)
    s = re.sub(r"\^\(([^)]+)\)", lambda m: _to_sup("(" + m.group(1) + ")"), s)
    s = re.sub(r"\^([a-zA-Z0-9+\-]+)", lambda m: _to_sup(m.group(1)), s)
    s = re.sub(r"_\{([^}]+)\}", lambda m: _to_sub(m.group(1)), s)
    s = re.sub(r"_\(([^)]+)\)", lambda m: _to_sub("(" + m.group(1) + ")"), s)
    s = re.sub(r"_([a-zA-Z0-9+\-]+)", lambda m: _to_sub(m.group(1)), s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def _build_data_url(payload: dict) -> str:
    # Force fully headless SDL in worker process.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import pygame  # noqa: PLC0415
    from slide_renderer import SlideEngine, Slide, TextBox, BulletList, Shape  # noqa: PLC0415

    width = int(payload.get("width", 1200))
    height = int(payload.get("height", 675))

    chapter_title = payload.get("chapter_title", "Chapter")
    slide_title = payload.get("slide_title", "Slide")
    slide_index = int(payload.get("slide_index", 0))
    slide_total = max(1, int(payload.get("slide_total", 1)))
    blocks = payload.get("content_blocks") or []
    graphics = payload.get("graphics") or []

    engine = SlideEngine(
        width=width,
        height=height,
        theme="modern_dark",
        show_progress_bar=False,
        show_slide_count=False,
        auto_init_pygame=True,
    )
    slide = Slide(
        transition="fade",
        accent_bar=True,
        accent_bar_pos="top",
        accent_bar_thickness=5,
        slide_number=False,
    )

    slide.add(
        Shape(
            "rounded_rect",
            pos=(0.5, 0.52),
            size=(0.95, 0.88),
            anchor="center",
            color=(18, 24, 46, 220),
            radius=20,
            shadow=True,
        )
    )
    slide.add(
        TextBox(
            f"{chapter_title}  •  Slide {slide_index + 1}/{slide_total}",
            pos=(0.07, 0.09),
            style="caption",
            font_size=0.033,
            color="#9fb3d9",
            anchor="top_left",
        )
    )
    title_len = len(str(slide_title or ""))
    title_ratio = 0.072
    if title_len > 40:
        title_ratio = 0.064
    if title_len > 56:
        title_ratio = 0.058
    if "worked example" in str(slide_title or "").lower():
        title_ratio = min(title_ratio, 0.056)
    slide.add(
        TextBox(
            slide_title,
            pos=(0.07, 0.14),
            style="heading",
            font_size=title_ratio,
            width=0.88,
            anchor="top_left",
            entry_anim="fade_in",
            anim_duration=0.35,
        )
    )

    y = 0.255
    step_idx = 1
    if len(blocks) > 7:
        _log.warning("slide_render_worker: truncating %d content blocks to 7", len(blocks))
    for block in blocks[:7]:
        kind = (block.get("kind") or "text").lower()
        txt = (block.get("text") or "").strip()
        if not txt:
            continue
        if kind in ("step", "problem", "example", "note"):
            prefix = {
                "step": f"Step {step_idx}: ",
                "problem": "Problem: ",
                "example": "Example: ",
                "note": "Note: ",
            }.get(kind, "")
            if kind == "step":
                step_idx += 1
            if prefix and not txt.lower().startswith(prefix.lower()):
                txt = f"{prefix}{txt}"
        txt = _pretty_math_text(txt)
        if len(txt) > 280:
            txt = txt[:277] + "..."
        txt = "• " + txt
        est_lines = max(1, min(5, math.ceil(len(txt) / 50)))
        block_h = 0.043 * est_lines + 0.018
        slide.add(
            TextBox(
                txt,
                pos=(0.09, y),
                anchor="top_left",
                width=0.84,
                style="body",
                font_size=0.041,
                line_spacing=1.58,
                entry_anim="fade_in",
                anim_delay=max(0.0, y - 0.20),
                anim_duration=0.3,
            )
        )
        y += block_h + 0.016
        if y > 0.82:
            break

    if graphics:
        chips = [f"{g.get('kind', 'graphic')}: {g.get('name', '')}".strip(": ") for g in graphics[:2]]
        slide.add(
            BulletList(
                items=chips,
                pos=(0.73, 0.84),
                anchor="top_left",
                width=0.2,
                style="caption",
                font_size=0.026,
                bullet_char="◆",
                bullet_color="#4fc3f7",
                entry_anim="fade_in",
                anim_delay=0.35,
                anim_duration=0.35,
            )
        )

    engine.add_slide(slide)
    surface = engine.render_slide_to_surface(index=0, width=width, height=height)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pygame.image.save(surface, tmp_path)
        png = Path(tmp_path).read_bytes()
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        data_url = _build_data_url(payload)
        sys.stdout.write(json.dumps({"success": True, "data_url": data_url}))
        return 0
    except Exception as exc:
        sys.stdout.write(json.dumps({"success": False, "error": str(exc), "traceback": traceback.format_exc()}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
