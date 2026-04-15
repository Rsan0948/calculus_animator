"""Font cache and text rendering helpers."""

from pathlib import Path

import pygame


class _FontCache:
    def __init__(self) -> None:
        self._fonts = {}
        self._mono_name = None
        self._sans_name = None
        self._initialized = False
        self._registered = {}

    def register_font(self, name, path) -> None:
        self._registered[str(name)] = str(path)

    def _init_fonts(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        # Pre-register bundled fallback fonts so headless/minimal systems always
        # have a known-good font rather than falling back to pygame's bitmap default.
        _assets = Path(__file__).parent.parent / "assets" / "fonts"
        for _fname, _key in [("DejaVuSans.ttf", "dejavusans"), ("DejaVuSansMono.ttf", "dejavusansmono")]:
            _p = _assets / _fname
            if _p.exists():
                self._registered.setdefault(_key, str(_p))
        available = pygame.font.get_fonts()
        mono_prefs = ["dejavusansmono", "consolas", "couriernew", "liberationmono",
                       "ubuntumono", "sourcecodepro", "monospace"]
        sans_prefs = ["dejavusans", "segoeui", "arial", "helvetica", "roboto",
                       "liberationsans", "ubuntu", "noto", "sans"]
        for m in mono_prefs:
            if m in available:
                self._mono_name = m
                break
        for s in sans_prefs:
            if s in available:
                self._sans_name = s
                break

    def get(self, name: None=None, size: int=16, bold: bool=False, italic: bool=False, monospace: bool=False):
        self._init_fonts()
        if monospace and not name:
            name = self._mono_name
        elif not name:
            name = self._sans_name
        key = (name, size, bold, italic)
        if key not in self._fonts:
            try:
                if name in self._registered:
                    font = pygame.font.Font(self._registered[name], size)
                    if bold:
                        font.set_bold(True)
                    if italic:
                        font.set_italic(True)
                else:
                    font = pygame.font.SysFont(name, size, bold=bold, italic=italic)
            except Exception:
                font = pygame.font.Font(None, size)
                if bold:
                    font.set_bold(True)
                if italic:
                    font.set_italic(True)
            self._fonts[key] = font
        return self._fonts[key]

_font_cache = _FontCache()


def _wrap_text(text, font, max_width) -> list:
    if max_width <= 0:
        return [text]
    words = text.split(" ")
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            # handle word wider than max_width
            if font.size(w)[0] > max_width:
                while w:
                    for i in range(len(w), 0, -1):
                        if font.size(w[:i])[0] <= max_width or i == 1:
                            lines.append(w[:i])
                            w = w[i:]
                            break
                current = ""
            else:
                current = w
    if current:
        lines.append(current)
    return lines if lines else [""]

_TEXT_SURFACE_CACHE: dict = {}


def _render_text_surface(text, font, color, max_width: int=0, line_spacing: float=1.4,
                          align: str="left", underline: bool=False, max_lines: None=None):
    cache_key = (
        text, id(font), tuple(color) if isinstance(color, (list, tuple)) else color,
        int(max_width or 0), float(line_spacing), align, bool(underline), int(max_lines or 0),
    )
    cache = _TEXT_SURFACE_CACHE
    cached = cache.get(cache_key)
    if cached is not None:
        return cached.copy()

    if underline:
        font.set_underline(True)
    lines_raw = text.split("\n")
    all_lines = []
    for lr in lines_raw:
        if max_width > 0:
            all_lines.extend(_wrap_text(lr, font, max_width))
        else:
            all_lines.append(lr)
    if max_lines and len(all_lines) > max_lines:
        all_lines = all_lines[:max_lines]
        all_lines[-1] = all_lines[-1][:max(0, len(all_lines[-1]) - 3)] + "..."

    base_h = max(1, font.get_height())
    lh = max(base_h, int(base_h * line_spacing))
    widths = [font.size(line_text)[0] for line_text in all_lines]
    total_w = max(widths) if widths else 1
    # Preserve full glyph height on the final line (descenders like g/y/p),
    # then add a tiny safety pad to avoid renderer/backend clipping.
    total_h = ((len(all_lines) - 1) * lh + base_h + 2) if all_lines else 1
    total_h = max(total_h, 1)

    surf = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
    for i, line in enumerate(all_lines):
        if not line.strip():
            continue
        ls = font.render(line, True, color)
        x = 0
        if align == "center":
            x = (total_w - widths[i]) // 2
        elif align == "right":
            x = total_w - widths[i]
        surf.blit(ls, (x, i * lh))

    if underline:
        font.set_underline(False)
    # Keep a bounded cache to avoid unbounded memory growth.
    if len(cache) > 1200:
        cache.clear()
    cache[cache_key] = surf.copy()
    return surf
