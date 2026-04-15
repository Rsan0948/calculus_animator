"""
Persistent isolated pygame slide renderer worker.
Reads JSON tasks from stdin (one per line) and writes JSON results to stdout.
"""
from __future__ import annotations
import os
import sys

# Force fully headless SDL and hide prompts BEFORE anything else
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import base64
import io
import json
import math
import re
import traceback
from pathlib import Path

# Add project root to path for imports
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_logger

logger = get_logger("slide_render_worker")

import pygame

from slide_renderer import BulletList, Shape, Slide, SlideEngine, TextBox

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
    for _ in range(6):
        ns = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", s)
        if ns == s:
            break
        s = ns
    s = s.replace("{", "(").replace("}", ")")
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)
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
    s = re.sub(r"\^\{([^}]+)\}", lambda m: _to_sup(m.group(1)), s)
    s = re.sub(r"\^\(([^)]+)\)", lambda m: _to_sup("(" + m.group(1) + ")"), s)
    s = re.sub(r"\^([a-zA-Z0-9+\-]+)", lambda m: _to_sup(m.group(1)), s)
    s = re.sub(r"_\{([^}]+)\}", lambda m: _to_sub(m.group(1)), s)
    s = re.sub(r"_\(([^)]+)\)", lambda m: _to_sub("(" + m.group(1) + ")"), s)
    s = re.sub(r"_([a-zA-Z0-9+\-]+)", lambda m: _to_sub(m.group(1)), s)
    return re.sub(r"[ \t]+", " ", s).strip()

def render_slide(engine: SlideEngine, payload: dict) -> str:
    width = int(payload.get("width", 1200))
    height = int(payload.get("height", 675))
    chapter_title = payload.get("chapter_title", "Chapter")
    slide_title = payload.get("slide_title", "Slide")
    slide_index = int(payload.get("slide_index", 0))
    slide_total = max(1, int(payload.get("slide_total", 1)))
    blocks = payload.get("content_blocks") or []
    graphics = payload.get("graphics") or []

    slide = Slide(transition="fade", accent_bar=True, accent_bar_pos="top", accent_bar_thickness=5)
    slide.add(Shape("rounded_rect", pos=(0.5, 0.52), size=(0.95, 0.88), anchor="center", color=(18, 24, 46, 220), radius=20, shadow=True))
    slide.add(TextBox(f"{chapter_title}  •  Slide {slide_index + 1}/{slide_total}", pos=(0.07, 0.09), style="caption", font_size=0.033, color="#9fb3d9", anchor="top_left"))
    
    title_ratio = 0.072
    if len(str(slide_title)) > 40: title_ratio = 0.064
    if len(str(slide_title)) > 56: title_ratio = 0.058
    slide.add(TextBox(slide_title, pos=(0.07, 0.14), style="heading", font_size=title_ratio, width=0.88, anchor="top_left"))

    y = 0.255
    step_idx = 1
    for block in blocks[:7]:
        kind = (block.get("kind") or "text").lower()
        txt = (block.get("text") or "").strip()
        if not txt: continue
        prefix = {"step": f"Step {step_idx}: ", "problem": "Problem: ", "example": "Example: ", "note": "Note: "}.get(kind, "")
        if kind == "step": step_idx += 1
        if prefix and not txt.lower().startswith(prefix.lower()): txt = f"{prefix}{txt}"
        txt = "• " + _pretty_math_text(txt)
        if len(txt) > 280: txt = txt[:277] + "..."
        est_lines = max(1, min(5, math.ceil(len(txt) / 50)))
        slide.add(TextBox(txt, pos=(0.09, y), anchor="top_left", width=0.84, style="body", font_size=0.041, line_spacing=1.58))
        y += 0.043 * est_lines + 0.034
        if y > 0.82: break

    if graphics:
        items = [f"{g.get('kind', 'graphic')}: {g.get('name', '')}".strip(": ") for g in graphics[:2]]
        slide.add(BulletList(items=items, pos=(0.73, 0.84), anchor="top_left", width=0.2, style="caption", font_size=0.026))

    engine.slides = []
    engine.add_slide(slide)
    surf = engine.render_slide_to_surface(0, width, height)
    
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "png")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

def main() -> None:
    engine = SlideEngine(width=1200, height=675, theme="modern_dark", auto_init_pygame=True)
    
    for line in sys.stdin:
        if not line.strip(): continue
        try:
            payload = json.loads(line)
            data_url = render_slide(engine, payload)
            sys.stdout.write(json.dumps({"success": True, "data_url": data_url}) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Worker task failed: {e}")
            sys.stdout.write(json.dumps({"success": False, "error": str(e), "traceback": traceback.format_exc()}) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
