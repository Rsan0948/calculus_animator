"""SlideEngine - A drop-in PowerPoint/Google Slides aesthetic renderer for Python apps.

Coordinate system: All positions and sizes use NORMALIZED coords (0.0–1.0)
relative to the slide area. (0,0) = top-left, (1,1) = bottom-right.
This means layouts are resolution-independent.

Usage:
    from slide_renderer import SlideEngine, Slide, TextBox, ImageBox, Shape, DynamicGraphic

    engine = SlideEngine(theme="modern_dark")
    s = Slide()
    s.add(TextBox("Hello World", pos=(0.5, 0.4), anchor="center", style="title"))
    engine.add_slide(s)
    engine.run()
"""

import copy
import io
import math
import os
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, List, Optional
)

import pygame
import pygame.gfxdraw

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Anchor(Enum):
    TOP_LEFT = auto()
    TOP_CENTER = auto()
    TOP_RIGHT = auto()
    CENTER_LEFT = auto()
    CENTER = auto()
    CENTER_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_CENTER = auto()
    BOTTOM_RIGHT = auto()

class Transition(Enum):
    NONE = auto()
    FADE = auto()
    SLIDE_LEFT = auto()
    SLIDE_RIGHT = auto()
    SLIDE_UP = auto()
    SLIDE_DOWN = auto()

class EntryAnim(Enum):
    NONE = auto()
    FADE_IN = auto()
    SLIDE_IN_LEFT = auto()
    SLIDE_IN_RIGHT = auto()
    SLIDE_IN_UP = auto()
    SLIDE_IN_DOWN = auto()
    ZOOM_IN = auto()
    TYPEWRITER = auto()

ANCHOR_MAP = {
    "top_left": Anchor.TOP_LEFT, "topleft": Anchor.TOP_LEFT,
    "top_center": Anchor.TOP_CENTER, "topcenter": Anchor.TOP_CENTER,
    "top_right": Anchor.TOP_RIGHT, "topright": Anchor.TOP_RIGHT,
    "center_left": Anchor.CENTER_LEFT, "centerleft": Anchor.CENTER_LEFT,
    "center": Anchor.CENTER,
    "center_right": Anchor.CENTER_RIGHT, "centerright": Anchor.CENTER_RIGHT,
    "bottom_left": Anchor.BOTTOM_LEFT, "bottomleft": Anchor.BOTTOM_LEFT,
    "bottom_center": Anchor.BOTTOM_CENTER, "bottomcenter": Anchor.BOTTOM_CENTER,
    "bottom_right": Anchor.BOTTOM_RIGHT, "bottomright": Anchor.BOTTOM_RIGHT,
}

def _parse_anchor(val) -> Anchor:
    if isinstance(val, Anchor):
        return val
    return ANCHOR_MAP.get(str(val).lower().replace("-", "_"), Anchor.TOP_LEFT)

def _parse_transition(val) -> Transition:
    if isinstance(val, Transition):
        return val
    mapping = {
        "none": Transition.NONE, "fade": Transition.FADE,
        "slide_left": Transition.SLIDE_LEFT, "slide_right": Transition.SLIDE_RIGHT,
        "slide_up": Transition.SLIDE_UP, "slide_down": Transition.SLIDE_DOWN,
    }
    return mapping.get(str(val).lower().replace("-", "_"), Transition.NONE)

def _parse_entry(val) -> EntryAnim:
    if isinstance(val, EntryAnim):
        return val
    mapping = {
        "none": EntryAnim.NONE, "fade_in": EntryAnim.FADE_IN, "fade": EntryAnim.FADE_IN,
        "slide_in_left": EntryAnim.SLIDE_IN_LEFT, "slide_left": EntryAnim.SLIDE_IN_LEFT,
        "slide_in_right": EntryAnim.SLIDE_IN_RIGHT, "slide_right": EntryAnim.SLIDE_IN_RIGHT,
        "slide_in_up": EntryAnim.SLIDE_IN_UP, "slide_up": EntryAnim.SLIDE_IN_UP,
        "slide_in_down": EntryAnim.SLIDE_IN_DOWN, "slide_down": EntryAnim.SLIDE_IN_DOWN,
        "zoom_in": EntryAnim.ZOOM_IN, "zoom": EntryAnim.ZOOM_IN,
        "typewriter": EntryAnim.TYPEWRITER,
    }
    return mapping.get(str(val).lower().replace("-", "_"), EntryAnim.NONE)

# ---------------------------------------------------------------------------
# Color / gradient helpers
# ---------------------------------------------------------------------------

def _parse_color(c):
    if isinstance(c, (list, tuple)):
        return tuple(c)
    if isinstance(c, str):
        c = c.lstrip("#")
        if len(c) == 6:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        if len(c) == 8:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16))
    return (255, 255, 255)

def _lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(min(len(a), len(b))))

def _draw_gradient_rect(surface, rect, color_top, color_bottom, vertical=True):
    x, y, w, h = rect
    for i in range(h if vertical else w):
        t = i / max(1, (h if vertical else w) - 1)
        c = _lerp_color(color_top, color_bottom, t)
        if vertical:
            pygame.draw.line(surface, c, (x, y + i), (x + w - 1, y + i))
        else:
            pygame.draw.line(surface, c, (x + i, y), (x + i, y + h - 1))

def _draw_rounded_rect(surface, color, rect, radius, border=0):
    x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
    r = min(radius, w // 2, h // 2)
    if r <= 0:
        pygame.draw.rect(surface, color, (x, y, w, h), border)
        return
    if border == 0:
        pygame.draw.rect(surface, color, (x + r, y, w - 2 * r, h))
        pygame.draw.rect(surface, color, (x, y + r, w, h - 2 * r))
        pygame.draw.circle(surface, color, (x + r, y + r), r)
        pygame.draw.circle(surface, color, (x + w - r - 1, y + r), r)
        pygame.draw.circle(surface, color, (x + r, y + h - r - 1), r)
        pygame.draw.circle(surface, color, (x + w - r - 1, y + h - r - 1), r)
    else:
        pygame.draw.rect(surface, color, (x + r, y, w - 2 * r, border))
        pygame.draw.rect(surface, color, (x + r, y + h - border, w - 2 * r, border))
        pygame.draw.rect(surface, color, (x, y + r, border, h - 2 * r))
        pygame.draw.rect(surface, color, (x + w - border, y + r, border, h - 2 * r))
        pygame.draw.arc(surface, color, (x, y, 2 * r, 2 * r), math.pi / 2, math.pi, max(1, border))
        pygame.draw.arc(surface, color, (x + w - 2 * r, y, 2 * r, 2 * r), 0, math.pi / 2, max(1, border))
        pygame.draw.arc(surface, color, (x, y + h - 2 * r, 2 * r, 2 * r), math.pi, 3 * math.pi / 2, max(1, border))
        pygame.draw.arc(surface, color, (x + w - 2 * r, y + h - 2 * r, 2 * r, 2 * r), 3 * math.pi / 2, 2 * math.pi, max(1, border))

def _draw_shadow(surface, rect, radius, shadow_color=(0, 0, 0, 40), offset=(4, 4), blur=8):
    sx, sy = offset
    for i in range(blur, 0, -1):
        alpha = int((shadow_color[3] if len(shadow_color) > 3 else 40) * (1 - i / blur))
        c = (*shadow_color[:3], alpha)
        s = pygame.Surface((int(rect[2]) + 2 * i, int(rect[3]) + 2 * i), pygame.SRCALPHA)
        _draw_rounded_rect(s, c, (0, 0, s.get_width(), s.get_height()), radius + i)
        surface.blit(s, (int(rect[0]) + sx - i, int(rect[1]) + sy - i))

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------

THEMES: Dict[str, Dict[str, Any]] = {
    "modern_dark": {
        "bg_gradient": ("#1a1a2e", "#16213e"),
        "accent": "#e94560",
        "accent2": "#0f3460",
        "title_color": "#ffffff",
        "subtitle_color": "#a0a0c0",
        "body_color": "#d0d0e0",
        "muted_color": "#606080",
        "card_bg": (30, 30, 55, 220),
        "card_border": (233, 69, 96, 80),
        "code_bg": (15, 15, 30, 240),
        "code_color": "#80ffaa",
        "shadow_color": (0, 0, 0, 60),
        "bullet_color": "#e94560",
        "link_color": "#4fc3f7",
        "slide_number_color": "#606080",
        "fonts": {
            "title": {"name": None, "size_ratio": 0.065, "bold": True},
            "subtitle": {"name": None, "size_ratio": 0.035, "bold": False},
            "heading": {"name": None, "size_ratio": 0.045, "bold": True},
            "subheading": {"name": None, "size_ratio": 0.032, "bold": True},
            "body": {"name": None, "size_ratio": 0.028, "bold": False},
            "caption": {"name": None, "size_ratio": 0.022, "bold": False},
            "code": {"name": None, "size_ratio": 0.024, "bold": False, "monospace": True},
            "label": {"name": None, "size_ratio": 0.020, "bold": True},
        },
    },
    "modern_light": {
        "bg_gradient": ("#f5f7fa", "#e4e9f2"),
        "accent": "#4361ee",
        "accent2": "#3a0ca3",
        "title_color": "#1a1a2e",
        "subtitle_color": "#555580",
        "body_color": "#2d2d44",
        "muted_color": "#8888aa",
        "card_bg": (255, 255, 255, 230),
        "card_border": (67, 97, 238, 60),
        "code_bg": (240, 240, 250, 240),
        "code_color": "#d63384",
        "shadow_color": (0, 0, 40, 35),
        "bullet_color": "#4361ee",
        "link_color": "#0077b6",
        "slide_number_color": "#8888aa",
        "fonts": {
            "title": {"name": None, "size_ratio": 0.065, "bold": True},
            "subtitle": {"name": None, "size_ratio": 0.035, "bold": False},
            "heading": {"name": None, "size_ratio": 0.045, "bold": True},
            "subheading": {"name": None, "size_ratio": 0.032, "bold": True},
            "body": {"name": None, "size_ratio": 0.028, "bold": False},
            "caption": {"name": None, "size_ratio": 0.022, "bold": False},
            "code": {"name": None, "size_ratio": 0.024, "bold": False, "monospace": True},
            "label": {"name": None, "size_ratio": 0.020, "bold": True},
        },
    },
    "gradient_ocean": {
        "bg_gradient": ("#0f0c29", "#302b63", "#24243e"),
        "accent": "#00d2ff",
        "accent2": "#7b2ff7",
        "title_color": "#ffffff",
        "subtitle_color": "#a0c4ff",
        "body_color": "#d0e0ff",
        "muted_color": "#5566aa",
        "card_bg": (20, 20, 60, 200),
        "card_border": (0, 210, 255, 60),
        "code_bg": (10, 10, 40, 240),
        "code_color": "#00ffa0",
        "shadow_color": (0, 0, 0, 50),
        "bullet_color": "#00d2ff",
        "link_color": "#00d2ff",
        "slide_number_color": "#5566aa",
        "fonts": {
            "title": {"name": None, "size_ratio": 0.065, "bold": True},
            "subtitle": {"name": None, "size_ratio": 0.035, "bold": False},
            "heading": {"name": None, "size_ratio": 0.045, "bold": True},
            "subheading": {"name": None, "size_ratio": 0.032, "bold": True},
            "body": {"name": None, "size_ratio": 0.028, "bold": False},
            "caption": {"name": None, "size_ratio": 0.022, "bold": False},
            "code": {"name": None, "size_ratio": 0.024, "bold": False, "monospace": True},
            "label": {"name": None, "size_ratio": 0.020, "bold": True},
        },
    },
    "warm_sunset": {
        "bg_gradient": ("#2d1b36", "#6b2737"),
        "accent": "#ff6b6b",
        "accent2": "#ffa07a",
        "title_color": "#ffffff",
        "subtitle_color": "#ffb4a2",
        "body_color": "#f0d0c0",
        "muted_color": "#886666",
        "card_bg": (50, 25, 40, 210),
        "card_border": (255, 107, 107, 60),
        "code_bg": (30, 15, 25, 240),
        "code_color": "#ffd166",
        "shadow_color": (0, 0, 0, 50),
        "bullet_color": "#ff6b6b",
        "link_color": "#ffa07a",
        "slide_number_color": "#886666",
        "fonts": {
            "title": {"name": None, "size_ratio": 0.065, "bold": True},
            "subtitle": {"name": None, "size_ratio": 0.035, "bold": False},
            "heading": {"name": None, "size_ratio": 0.045, "bold": True},
            "subheading": {"name": None, "size_ratio": 0.032, "bold": True},
            "body": {"name": None, "size_ratio": 0.028, "bold": False},
            "caption": {"name": None, "size_ratio": 0.022, "bold": False},
            "code": {"name": None, "size_ratio": 0.024, "bold": False, "monospace": True},
            "label": {"name": None, "size_ratio": 0.020, "bold": True},
        },
    },
    "corporate": {
        "bg_gradient": ("#ffffff", "#f0f2f5"),
        "accent": "#0066cc",
        "accent2": "#003d7a",
        "title_color": "#1a1a1a",
        "subtitle_color": "#4a4a6a",
        "body_color": "#333344",
        "muted_color": "#999999",
        "card_bg": (255, 255, 255, 240),
        "card_border": (0, 102, 204, 50),
        "code_bg": (245, 245, 250, 245),
        "code_color": "#c7254e",
        "shadow_color": (0, 0, 50, 25),
        "bullet_color": "#0066cc",
        "link_color": "#0066cc",
        "slide_number_color": "#999999",
        "fonts": {
            "title": {"name": None, "size_ratio": 0.060, "bold": True},
            "subtitle": {"name": None, "size_ratio": 0.032, "bold": False},
            "heading": {"name": None, "size_ratio": 0.042, "bold": True},
            "subheading": {"name": None, "size_ratio": 0.030, "bold": True},
            "body": {"name": None, "size_ratio": 0.026, "bold": False},
            "caption": {"name": None, "size_ratio": 0.020, "bold": False},
            "code": {"name": None, "size_ratio": 0.022, "bold": False, "monospace": True},
            "label": {"name": None, "size_ratio": 0.018, "bold": True},
        },
    },
}

def register_theme(name: str, theme_dict: dict):
    """Register a custom theme for use with SlideEngine."""
    THEMES[name] = theme_dict

# ---------------------------------------------------------------------------
# Slide Elements
# ---------------------------------------------------------------------------

class SlideElement:
    """Base class for all slide elements."""
    def __init__(self, pos=(0, 0), anchor="top_left", z_order=0,
                 entry_anim="none", anim_delay=0.0, anim_duration=0.5,
                 visible=True, opacity=1.0, name=None, group=None, **kwargs):
        # Friendly aliases for host integrations.
        if "anim" in kwargs:
            entry_anim = kwargs.pop("anim")
        if "delay" in kwargs:
            anim_delay = kwargs.pop("delay")
        if "dur" in kwargs:
            anim_duration = kwargs.pop("dur")
        self.pos = pos  # normalized (x, y)
        self.anchor = _parse_anchor(anchor)
        self.z_order = z_order
        self.entry_anim = _parse_entry(entry_anim)
        self.anim_delay = anim_delay
        self.anim_duration = max(0.05, anim_duration)
        self.visible = visible
        self.opacity = opacity
        self.name = name
        self.group = group
        # runtime state
        self._anim_progress = 0.0 if self.entry_anim != EntryAnim.NONE else 1.0
        self._started = False

    def _resolve_rect(self, elem_w, elem_h, slide_w, slide_h):
        px = self.pos[0] * slide_w
        py = self.pos[1] * slide_h
        a = self.anchor
        if a in (Anchor.TOP_CENTER, Anchor.CENTER, Anchor.BOTTOM_CENTER):
            px -= elem_w / 2
        elif a in (Anchor.TOP_RIGHT, Anchor.CENTER_RIGHT, Anchor.BOTTOM_RIGHT):
            px -= elem_w
        if a in (Anchor.CENTER_LEFT, Anchor.CENTER, Anchor.CENTER_RIGHT):
            py -= elem_h / 2
        elif a in (Anchor.BOTTOM_LEFT, Anchor.BOTTOM_CENTER, Anchor.BOTTOM_RIGHT):
            py -= elem_h
        return px, py

    def _ease(self, t):
        # ease-out cubic
        return 1 - (1 - t) ** 3

    def _apply_anim(self, surface, dest_x, dest_y, slide_w, slide_h, progress):
        p = self._ease(progress)
        anim = self.entry_anim
        alpha = int(255 * self.opacity * (p if anim in (
            EntryAnim.FADE_IN, EntryAnim.ZOOM_IN,
            EntryAnim.SLIDE_IN_LEFT, EntryAnim.SLIDE_IN_RIGHT,
            EntryAnim.SLIDE_IN_UP, EntryAnim.SLIDE_IN_DOWN
        ) else self.opacity))
        alpha = max(0, min(255, alpha))

        ox, oy = 0, 0
        if anim == EntryAnim.SLIDE_IN_LEFT:
            ox = -(1 - p) * slide_w * 0.15
        elif anim == EntryAnim.SLIDE_IN_RIGHT:
            ox = (1 - p) * slide_w * 0.15
        elif anim == EntryAnim.SLIDE_IN_UP:
            oy = -(1 - p) * slide_h * 0.1
        elif anim == EntryAnim.SLIDE_IN_DOWN:
            oy = (1 - p) * slide_h * 0.1

        if anim == EntryAnim.ZOOM_IN and p < 1.0:
            scale = 0.7 + 0.3 * p
            new_w = int(surface.get_width() * scale)
            new_h = int(surface.get_height() * scale)
            if new_w > 0 and new_h > 0:
                surface = pygame.transform.smoothscale(surface, (new_w, new_h))
                ox += (surface.get_width() - new_w) / 2 * (1 - p)
                oy += (surface.get_height() - new_h) / 2 * (1 - p)

        if alpha < 255:
            surface.set_alpha(alpha)

        return surface, dest_x + ox, dest_y + oy


class TextBox(SlideElement):
    """A text element with full styling control."""
    def __init__(self, text="", pos=(0, 0), anchor="top_left",
                 style="body", color=None, font_size=None,
                 bold=None, italic=False, underline=False,
                 width=None, line_spacing=1.4,
                 align="left", bg_color=None, bg_radius=8,
                 bg_padding=(10, 8), bg_pad=None, shadow=False, border_color=None,
                 border_width=2, bullet=None, bullet_indent=0.02,
                 max_lines=None, z_order=0, entry_anim="none",
                 anim_delay=0.0, anim_duration=0.5, opacity=1.0,
                 name=None, group=None, visible=True):
        if bg_pad is not None:
            bg_padding = bg_pad
        if isinstance(bg_padding, (int, float)):
            bg_padding = (bg_padding, bg_padding)
        super().__init__(pos, anchor, z_order, entry_anim, anim_delay,
                         anim_duration, visible, opacity, name, group)
        self.text = text
        self.style = style
        self.color = _parse_color(color) if color else None
        self.font_size = font_size  # override; absolute pixels or ratio if < 1
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.width = width  # normalized width for wrapping
        self.line_spacing = line_spacing
        self.align = align
        self.bg_color = _parse_color(bg_color) if bg_color else None
        self.bg_radius = bg_radius
        self.bg_padding = bg_padding if isinstance(bg_padding, (list, tuple)) else (bg_padding, bg_padding)
        self.shadow = shadow
        self.border_color = _parse_color(border_color) if border_color else None
        self.border_width = border_width
        self.bullet = bullet
        self.bullet_indent = bullet_indent
        self.max_lines = max_lines


class ImageBox(SlideElement):
    """An image element loaded from file path or pygame Surface."""
    def __init__(self, source=None, pos=(0, 0), anchor="top_left",
                 size=None, maintain_aspect=True,
                 border_radius=0, border_color=None, border_width=2,
                 shadow=True, opacity=1.0, tint=None,
                 z_order=0, entry_anim="none",
                 anim_delay=0.0, anim_duration=0.5,
                 name=None, group=None, visible=True):
        super().__init__(pos, anchor, z_order, entry_anim, anim_delay,
                         anim_duration, visible, opacity, name, group)
        self.source = source  # file path or pygame.Surface
        self.size = size  # (norm_w, norm_h) or None
        self.maintain_aspect = maintain_aspect
        self.border_radius = border_radius
        self.border_color = _parse_color(border_color) if border_color else None
        self.border_width = border_width
        self.shadow = shadow
        self.tint = _parse_color(tint) if tint else None
        self._cached_surface = None
        self._cached_key = None


class Shape(SlideElement):
    """A geometric shape: rect, rounded_rect, circle, ellipse, line, polygon."""
    def __init__(self, shape_type="rect", pos=(0, 0), size=(0.1, 0.1),
                 anchor="top_left", color="#ffffff", fill=True,
                 border_color=None, border_width=2, radius=12,
                 shadow=False, opacity=1.0,
                 points=None,  # for polygon/line: list of (norm_x, norm_y)
                 gradient=None,  # (color_top, color_bottom)
                 z_order=0, entry_anim="none",
                 anim_delay=0.0, anim_duration=0.5,
                 name=None, group=None, visible=True):
        super().__init__(pos, anchor, z_order, entry_anim, anim_delay,
                         anim_duration, visible, opacity, name, group)
        self.shape_type = shape_type
        self.size = size
        self.color = _parse_color(color)
        self.fill = fill
        self.border_color = _parse_color(border_color) if border_color else None
        self.border_width = border_width
        self.radius = radius
        self.shadow = shadow
        self.gradient = gradient
        self.points = points


class DynamicGraphic(SlideElement):
    """A dynamic/animated element rendered by a user callback.

    The callback signature is:
        def render(surface, rect, dt, elapsed, theme, **kwargs)
    where:
        surface = pygame surface to draw on (full slide size)
        rect    = (x, y, w, h) pixel rect allocated for this element
        dt      = delta time since last frame
        elapsed = total time on this slide
        theme   = current theme dict
    """
    def __init__(self, render_fn=None, pos=(0, 0), size=(0.3, 0.3),
                 anchor="top_left", z_order=0, entry_anim="none",
                 anim_delay=0.0, anim_duration=0.5, opacity=1.0,
                 name=None, group=None, visible=True, user_data=None):
        super().__init__(pos, anchor, z_order, entry_anim, anim_delay,
                         anim_duration, visible, opacity, name, group)
        self.render_fn = render_fn
        self.size = size
        self.user_data = user_data or {}


class BulletList(SlideElement):
    """Convenience element: a styled bullet-point list."""
    def __init__(self, items=None, pos=(0, 0), anchor="top_left",
                 style="body", color=None, bullet_char="●",
                 bullet_color=None, indent=0.03, item_spacing=1.6,
                 width=None, font_size=None, bold=None,
                 z_order=0, entry_anim="none", stagger_delay=0.15,
                 anim_delay=0.0, anim_duration=0.4, opacity=1.0,
                 name=None, group=None, visible=True,
                 sub_bullet_char="○", nested_indent=0.025):
        super().__init__(pos, anchor, z_order, entry_anim, anim_delay,
                         anim_duration, visible, opacity, name, group)
        self.items = items or []
        self.style = style
        self.color = _parse_color(color) if color else None
        self.bullet_char = bullet_char
        self.bullet_color = _parse_color(bullet_color) if bullet_color else None
        self.indent = indent
        self.item_spacing = item_spacing
        self.width = width
        self.font_size = font_size
        self.bold = bold
        self.stagger_delay = stagger_delay
        self.sub_bullet_char = sub_bullet_char
        self.nested_indent = nested_indent


class CodeBlock(SlideElement):
    """A syntax-highlighted (styled) code block."""
    def __init__(self, code="", pos=(0, 0), anchor="top_left",
                 width=None, height=None, font_size=None,
                 bg_color=None, text_color=None,
                 border_radius=10, shadow=True, line_numbers=False,
                 z_order=0, entry_anim="none",
                 anim_delay=0.0, anim_duration=0.5, opacity=1.0,
                 name=None, group=None, visible=True,
                 title=None, title_color=None):
        super().__init__(pos, anchor, z_order, entry_anim, anim_delay,
                         anim_duration, visible, opacity, name, group)
        self.code = code
        self.width = width
        self.height = height
        self.font_size = font_size
        self.bg_color = _parse_color(bg_color) if bg_color else None
        self.text_color = _parse_color(text_color) if text_color else None
        self.border_radius = border_radius
        self.shadow = shadow
        self.line_numbers = line_numbers
        self.title = title
        self.title_color = _parse_color(title_color) if title_color else None


class ProgressBar(SlideElement):
    """A progress/percentage bar."""
    def __init__(self, value=0.5, pos=(0, 0), anchor="top_left",
                 size=(0.3, 0.02), bg_color=None, fill_color=None,
                 border_radius=6, label=None, label_color=None,
                 animated=True, z_order=0, entry_anim="none",
                 anim_delay=0.0, anim_duration=0.8, opacity=1.0,
                 name=None, group=None, visible=True):
        super().__init__(pos, anchor, z_order, entry_anim, anim_delay,
                         anim_duration, visible, opacity, name, group)
        self.value = value
        self.size = size
        self.bg_color = _parse_color(bg_color) if bg_color else None
        self.fill_color = _parse_color(fill_color) if fill_color else None
        self.border_radius = border_radius
        self.label = label
        self.label_color = _parse_color(label_color) if label_color else None
        self.animated = animated


class Divider(SlideElement):
    """A horizontal or vertical divider line."""
    def __init__(self, pos=(0, 0), length=0.9, thickness=2,
                 color=None, orientation="horizontal",
                 anchor="top_left", z_order=0, entry_anim="none",
                 anim_delay=0.0, anim_duration=0.3, opacity=0.5,
                 name=None, group=None, visible=True,
                 gradient_fade=True):
        super().__init__(pos, anchor, z_order, entry_anim, anim_delay,
                         anim_duration, visible, opacity, name, group)
        self.length = length
        self.thickness = thickness
        self.color = _parse_color(color) if color else None
        self.orientation = orientation
        self.gradient_fade = gradient_fade


# ---------------------------------------------------------------------------
# Slide
# ---------------------------------------------------------------------------

class Slide:
    """A single slide containing elements."""
    def __init__(self, transition="fade", transition_duration=0.4,
                 bg_color=None, bg_gradient=None, bg_image=None,
                 accent_bar=True, accent_bar_pos="bottom",
                 accent_bar_thickness=4, slide_number=True,
                 footer_text=None, on_enter=None, on_exit=None,
                 duration=None, auto_advance=False, name=None):
        self.elements: List[SlideElement] = []
        self.transition = _parse_transition(transition)
        self.transition_duration = transition_duration
        self.bg_color = _parse_color(bg_color) if bg_color else None
        self.bg_gradient = bg_gradient
        self.bg_image = bg_image
        self.accent_bar = accent_bar
        self.accent_bar_pos = accent_bar_pos
        self.accent_bar_thickness = accent_bar_thickness
        self.slide_number = slide_number
        self.footer_text = footer_text
        self.on_enter = on_enter
        self.on_exit = on_exit
        self.duration = duration
        self.auto_advance = auto_advance
        self.name = name
        self._elapsed = 0.0

    def add(self, element: SlideElement):
        self.elements.append(element)
        return self  # chainable

    def add_all(self, *elements):
        for e in elements:
            self.elements.append(e)
        return self


# ---------------------------------------------------------------------------
# Font Cache
# ---------------------------------------------------------------------------

class _FontCache:
    def __init__(self):
        self._fonts = {}
        self._mono_name = None
        self._sans_name = None
        self._initialized = False
        self._registered = {}

    def register_font(self, name, path):
        self._registered[str(name)] = str(path)

    def _init_fonts(self):
        if self._initialized:
            return
        self._initialized = True
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

    def get(self, name=None, size=16, bold=False, italic=False, monospace=False):
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

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _wrap_text(text, font, max_width):
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

def _render_text_surface(text, font, color, max_width=0, line_spacing=1.4,
                          align="left", underline=False, max_lines=None):
    cache_key = (
        text, id(font), tuple(color) if isinstance(color, (list, tuple)) else color,
        int(max_width or 0), float(line_spacing), align, bool(underline), int(max_lines or 0),
    )
    cache = getattr(_render_text_surface, "_cache", None)
    if cache is None:
        cache = {}
        _render_text_surface._cache = cache
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

# ---------------------------------------------------------------------------
# SlideEngine
# ---------------------------------------------------------------------------

class SlideEngine:
    """Main engine: manages slides, themes, rendering, navigation, and animations."""

    def __init__(self, width=1280, height=720, theme="modern_dark",
                 fps=60, title="SlideEngine Presentation",
                 show_progress_bar=True, show_slide_count=True,
                 loop=False, bg_surface=None, auto_init_pygame=True):
        self.width = width
        self.height = height
        self.theme_name = theme
        self.theme = copy.deepcopy(THEMES.get(theme, THEMES["modern_dark"]))
        self.fps = fps
        self.title = title
        self.show_progress_bar = show_progress_bar
        self.show_slide_count = show_slide_count
        self.loop = loop
        self.bg_surface = bg_surface
        self.auto_init_pygame = auto_init_pygame

        self.slides: List[Slide] = []
        self.current_index = 0
        self._running = False
        self._clock = None
        self._screen = None
        self._slide_surface = None
        self._target_surface = None
        self._prev_surface = None
        self._transition_progress = 1.0
        self._transitioning = False
        self._transition_dir = 1
        self._bg_cache = None
        self._headless = False
        self._owns_pygame = False

        # external hooks
        self.on_slide_change: Optional[Callable] = None
        self.on_key: Optional[Callable] = None

    # -- public API --

    def add_slide(self, slide: Slide):
        self.slides.append(slide)
        return self

    def register_font(self, name, path):
        _font_cache.register_font(name, path)
        return self

    def set_theme(self, name_or_dict):
        if isinstance(name_or_dict, str):
            self.theme = copy.deepcopy(THEMES.get(name_or_dict, THEMES["modern_dark"]))
            self.theme_name = name_or_dict
        else:
            self.theme = copy.deepcopy(name_or_dict)
            self.theme_name = "custom"
        self._bg_cache = None

    def goto_slide(self, index):
        index = max(0, min(index, len(self.slides) - 1))
        if index != self.current_index:
            self._start_transition(index)

    def next_slide(self):
        if self.current_index < len(self.slides) - 1:
            self._start_transition(self.current_index + 1)
        elif self.loop and self.slides:
            self._start_transition(0)

    def prev_slide(self):
        if self.current_index > 0:
            self._start_transition(self.current_index - 1)
        elif self.loop and self.slides:
            self._start_transition(len(self.slides) - 1)

    def set_size(self, width, height):
        self.width, self.height = int(width), int(height)
        if not self._headless and self._screen is not None:
            self._screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        self._slide_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self._bg_cache = None

    def set_target_surface(self, surface):
        self._target_surface = surface
        if surface is not None:
            self.width, self.height = surface.get_size()
            self._slide_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self._bg_cache = None

    def initialize(self, headless=False, size=None, surface=None):
        if self.auto_init_pygame and not pygame.get_init():
            pygame.init()
            self._owns_pygame = True
        if not pygame.font.get_init():
            pygame.font.init()

        self._headless = bool(headless)
        if size:
            self.width, self.height = int(size[0]), int(size[1])

        if surface is not None:
            self.set_target_surface(surface)
        elif self._headless:
            self._target_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self._slide_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        else:
            self._screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
            pygame.display.set_caption(self.title)
            self._target_surface = self._screen
            self._slide_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        self._clock = self._clock or pygame.time.Clock()
        self._reset_slide_anims()
        return self

    def shutdown(self):
        self._running = False
        if self._owns_pygame:
            pygame.quit()
            self._owns_pygame = False

    def handle_action(self, action):
        action = str(action or "").lower()
        if action in ("next", "next_slide", "forward"):
            self.next_slide()
            return True
        if action in ("prev", "prev_slide", "back"):
            self.prev_slide()
            return True
        if action in ("home", "first"):
            self.goto_slide(0)
            return True
        if action in ("end", "last") and self.slides:
            self.goto_slide(len(self.slides) - 1)
            return True
        return False

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self._running = False
            return True
        if event.type == pygame.VIDEORESIZE:
            self.set_size(event.w, event.h)
            return True
        if event.type == pygame.KEYDOWN:
            if self.on_key and self.on_key(event):
                return True
            if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_PAGEDOWN):
                self.next_slide()
                return True
            if event.key in (pygame.K_LEFT, pygame.K_BACKSPACE, pygame.K_PAGEUP):
                self.prev_slide()
                return True
            if event.key == pygame.K_HOME:
                self.goto_slide(0)
                return True
            if event.key == pygame.K_END:
                self.goto_slide(len(self.slides) - 1)
                return True
            if event.key == pygame.K_ESCAPE:
                self._running = False
                return True
            if event.key == pygame.K_f and not self._headless and self._screen is not None:
                pygame.display.toggle_fullscreen()
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if event.pos[0] > self.width * 0.5:
                self.next_slide()
            else:
                self.prev_slide()
            return True
        return False

    def update(self, dt):
        self._update(dt)

    def render(self, target_surface=None):
        if target_surface is not None:
            self.set_target_surface(target_surface)
        if self._slide_surface is None:
            self._slide_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        target = self._target_surface or self._screen
        if target is None:
            target = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self._target_surface = target
        self._render_to_target(target)
        return target

    def run(self):
        """Start the presentation loop. Blocks until window is closed."""
        self.initialize(headless=False)
        self._running = True

        while self._running:
            dt = self._clock.tick(self.fps) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.render(self._screen)
            pygame.display.flip()
        self.shutdown()

    def render_slide_to_surface(self, index=None, width=None, height=None):
        """Render a single slide to a pygame.Surface (for embedding in other apps)."""
        if self.auto_init_pygame and not pygame.get_init():
            pygame.init()
            self._owns_pygame = True
        if not pygame.font.get_init():
            pygame.font.init()
        w = width or self.width
        h = height or self.height
        idx = index if index is not None else self.current_index
        if idx < 0 or idx >= len(self.slides):
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            surf.fill((0, 0, 0))
            return surf
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        self._render_slide(self.slides[idx], surf, w, h, force_full=True)
        return surf

    def export_slide_image(self, index, path, width=None, height=None):
        """Export a slide as a PNG image."""
        surf = self.render_slide_to_surface(index, width, height)
        pygame.image.save(surf, path)

    # -- internal --

    def _start_transition(self, new_index):
        old_slide = self.slides[self.current_index] if self.slides else None
        if old_slide and old_slide.on_exit:
            old_slide.on_exit(self.current_index)
        self._prev_surface = self._slide_surface.copy()
        self._transition_dir = 1 if new_index > self.current_index else -1
        self.current_index = new_index
        self._transition_progress = 0.0
        self._transitioning = True
        self._reset_slide_anims()
        new_slide = self.slides[self.current_index]
        new_slide._elapsed = 0.0
        if new_slide.on_enter:
            new_slide.on_enter(self.current_index)
        if self.on_slide_change:
            self.on_slide_change(self.current_index)

    def _reset_slide_anims(self):
        if not self.slides:
            return
        slide = self.slides[self.current_index]
        for e in slide.elements:
            if e.entry_anim != EntryAnim.NONE:
                e._anim_progress = 0.0
                e._started = False
            else:
                e._anim_progress = 1.0
                e._started = True

    def _update(self, dt):
        if not self.slides:
            return
        slide = self.slides[self.current_index]
        slide._elapsed += dt

        # update transition
        if self._transitioning:
            td = slide.transition_duration
            self._transition_progress += dt / max(0.01, td)
            if self._transition_progress >= 1.0:
                self._transition_progress = 1.0
                self._transitioning = False

        # update element anims
        for e in slide.elements:
            if e.entry_anim == EntryAnim.NONE:
                e._anim_progress = 1.0
                continue
            if slide._elapsed >= e.anim_delay:
                if not e._started:
                    e._started = True
                e._anim_progress += dt / e.anim_duration
                if e._anim_progress > 1.0:
                    e._anim_progress = 1.0

        # auto-advance
        if slide.auto_advance and slide.duration and slide._elapsed >= slide.duration:
            self.next_slide()

    def _render_to_target(self, target):
        if not self.slides:
            target.fill((0, 0, 0))
            return

        slide = self.slides[self.current_index]
        self._slide_surface.fill((0, 0, 0, 0))
        self._render_slide(slide, self._slide_surface, self.width, self.height)

        if self._transitioning and self._prev_surface:
            self._render_transition(slide, target)
        else:
            target.blit(self._slide_surface, (0, 0))

        # progress bar at bottom
        if self.show_progress_bar and len(self.slides) > 1:
            bar_h = 3
            frac = (self.current_index) / max(1, len(self.slides) - 1)
            accent = _parse_color(self.theme.get("accent", "#e94560"))
            bar_w = int(self.width * frac)
            pygame.draw.rect(target, (*accent[:3], 120), (0, self.height - bar_h, self.width, bar_h))
            pygame.draw.rect(target, accent, (0, self.height - bar_h, bar_w, bar_h))

    def _render_transition(self, slide, target):
        t = self._ease_transition(self._transition_progress)
        tr = slide.transition
        if tr == Transition.FADE:
            target.blit(self._prev_surface, (0, 0))
            self._slide_surface.set_alpha(int(255 * t))
            target.blit(self._slide_surface, (0, 0))
            self._slide_surface.set_alpha(255)
        elif tr == Transition.SLIDE_LEFT:
            d = self._transition_dir
            offset = int((1 - t) * self.width)
            target.blit(self._prev_surface, (-offset * d, 0))
            target.blit(self._slide_surface, (self.width * (1 - t) * (1 if d > 0 else -1), 0))
        elif tr == Transition.SLIDE_RIGHT:
            d = -self._transition_dir
            offset = int((1 - t) * self.width)
            target.blit(self._prev_surface, (-offset * d, 0))
            target.blit(self._slide_surface, (self.width * (1 - t) * (1 if d > 0 else -1), 0))
        elif tr in (Transition.SLIDE_UP, Transition.SLIDE_DOWN):
            d = 1 if tr == Transition.SLIDE_UP else -1
            offset = int((1 - t) * self.height)
            target.blit(self._prev_surface, (0, -offset * d))
            target.blit(self._slide_surface, (0, self.height * (1 - t) * d))
        else:
            target.blit(self._slide_surface, (0, 0))

    def _ease_transition(self, t):
        return t * t * (3 - 2 * t)  # smoothstep

    def _render_slide(self, slide, surface, w, h, force_full=False):
        # background
        self._render_background(slide, surface, w, h)

        # accent bar
        if slide.accent_bar:
            accent = _parse_color(self.theme.get("accent", "#e94560"))
            t = slide.accent_bar_thickness
            if slide.accent_bar_pos == "top":
                pygame.draw.rect(surface, accent, (0, 0, w, t))
            elif slide.accent_bar_pos == "bottom":
                pygame.draw.rect(surface, accent, (0, h - t, w, t))
            elif slide.accent_bar_pos == "left":
                pygame.draw.rect(surface, accent, (0, 0, t, h))
            elif slide.accent_bar_pos == "right":
                pygame.draw.rect(surface, accent, (w - t, 0, t, h))

        # sort by z_order
        sorted_elems = sorted(slide.elements, key=lambda e: e.z_order)
        for elem in sorted_elems:
            if not elem.visible:
                continue
            p = elem._anim_progress if not force_full else 1.0
            if p <= 0 and not force_full:
                continue
            self._render_element(elem, surface, w, h, p, slide)

        # slide number
        if slide.slide_number and self.show_slide_count:
            idx = self.slides.index(slide) if slide in self.slides else 0
            txt = f"{idx + 1} / {len(self.slides)}"
            nc = _parse_color(self.theme.get("slide_number_color", "#606080"))
            font = _font_cache.get(size=max(12, int(h * 0.02)))
            ts = font.render(txt, True, nc)
            surface.blit(ts, (w - ts.get_width() - 16, h - ts.get_height() - 12))

        # footer
        if slide.footer_text:
            nc = _parse_color(self.theme.get("muted_color", "#808080"))
            font = _font_cache.get(size=max(12, int(h * 0.018)))
            ts = font.render(slide.footer_text, True, nc)
            surface.blit(ts, (16, h - ts.get_height() - 12))

    def _render_background(self, slide, surface, w, h):
        slide_key = slide.name or id(slide)
        bg_key = (slide_key, w, h, str(slide.bg_gradient), str(slide.bg_color), str(slide.bg_image), self.theme_name)
        if isinstance(self._bg_cache, tuple) and self._bg_cache[0] == bg_key:
            surface.blit(self._bg_cache[1], (0, 0))
            return

        bg_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        grad = slide.bg_gradient
        if not grad:
            grad = self.theme.get("bg_gradient")

        if grad:
            colors = grad if isinstance(grad, (list, tuple)) else [grad]
            colors = [_parse_color(c) for c in colors]
            if len(colors) == 1:
                bg_surf.fill(colors[0])
            elif len(colors) == 2:
                _draw_gradient_rect(bg_surf, (0, 0, w, h), colors[0], colors[1])
            else:
                seg = len(colors) - 1
                seg_h = h // seg
                for i in range(seg):
                    sy = i * seg_h
                    sh = seg_h if i < seg - 1 else h - sy
                    _draw_gradient_rect(bg_surf, (0, sy, w, sh), colors[i], colors[i + 1])
        elif slide.bg_color:
            bg_surf.fill(slide.bg_color)
        else:
            bg_surf.fill(_parse_color(self.theme.get("bg_gradient", ["#1a1a2e"])[0]
                         if isinstance(self.theme.get("bg_gradient"), (list, tuple))
                         else self.theme.get("bg_gradient", "#1a1a2e")))

        if slide.bg_image:
            try:
                if isinstance(slide.bg_image, pygame.Surface):
                    img = slide.bg_image
                else:
                    img = pygame.image.load(slide.bg_image).convert_alpha()
                img = pygame.transform.smoothscale(img, (w, h))
                bg_surf.blit(img, (0, 0))
            except Exception:
                pass
        self._bg_cache = (bg_key, bg_surf.copy())
        surface.blit(bg_surf, (0, 0))

    def _render_element(self, elem, surface, w, h, progress, slide):
        if isinstance(elem, TextBox):
            self._render_textbox(elem, surface, w, h, progress)
        elif isinstance(elem, ImageBox):
            self._render_imagebox(elem, surface, w, h, progress)
        elif isinstance(elem, Shape):
            self._render_shape(elem, surface, w, h, progress)
        elif isinstance(elem, DynamicGraphic):
            self._render_dynamic(elem, surface, w, h, progress, slide)
        elif isinstance(elem, BulletList):
            self._render_bulletlist(elem, surface, w, h, progress)
        elif isinstance(elem, CodeBlock):
            self._render_codeblock(elem, surface, w, h, progress)
        elif isinstance(elem, ProgressBar):
            self._render_progressbar(elem, surface, w, h, progress)
        elif isinstance(elem, Divider):
            self._render_divider(elem, surface, w, h, progress)

    def _get_font_for_style(self, style_name, h, size_override=None, bold_override=None, italic=False):
        fstyles = self.theme.get("fonts", {})
        fdef = fstyles.get(style_name, fstyles.get("body", {"size_ratio": 0.028, "bold": False}))
        ratio = fdef.get("size_ratio", 0.028)
        if size_override is not None:
            if size_override < 1:
                ratio = size_override
            else:
                return _font_cache.get(
                    name=fdef.get("name"),
                    size=int(size_override),
                    bold=bold_override if bold_override is not None else fdef.get("bold", False),
                    italic=italic,
                    monospace=fdef.get("monospace", False),
                )
        sz = max(10, int(h * ratio))
        return _font_cache.get(
            name=fdef.get("name"),
            size=sz,
            bold=bold_override if bold_override is not None else fdef.get("bold", False),
            italic=italic,
            monospace=fdef.get("monospace", False),
        )

    def _color_for_style(self, style_name):
        mapping = {
            "title": "title_color", "subtitle": "subtitle_color",
            "heading": "title_color", "subheading": "title_color",
            "body": "body_color", "caption": "muted_color",
            "code": "code_color", "label": "body_color",
        }
        key = mapping.get(style_name, "body_color")
        return _parse_color(self.theme.get(key, "#ffffff"))

    def _render_textbox(self, tb: TextBox, surface, w, h, progress):
        font = self._get_font_for_style(tb.style, h, tb.font_size, tb.bold, tb.italic)
        color = tb.color or self._color_for_style(tb.style)
        max_w = int(tb.width * w) if tb.width else 0

        # handle typewriter
        display_text = tb.text
        if tb.entry_anim == EntryAnim.TYPEWRITER and progress < 1.0:
            chars = max(0, int(len(tb.text) * progress))
            display_text = tb.text[:chars]

        # bullet prefix
        prefix = ""
        indent_px = 0
        if tb.bullet:
            prefix = tb.bullet + " "
            indent_px = int(tb.bullet_indent * w)

        ts = _render_text_surface(
            prefix + display_text, font, color,
            max_width=max_w - indent_px if max_w else 0,
            line_spacing=tb.line_spacing, align=tb.align,
            underline=tb.underline, max_lines=tb.max_lines,
        )

        ew, eh = ts.get_width() + indent_px, ts.get_height()
        padx, pady = tb.bg_padding
        total_w = ew + 2 * padx
        total_h = eh + 2 * pady
        dx, dy = tb._resolve_rect(total_w, total_h, w, h)

        # shadow
        if tb.shadow:
            _draw_shadow(surface, (dx, dy, total_w, total_h), tb.bg_radius,
                         self.theme.get("shadow_color", (0, 0, 0, 40)))

        # background
        if tb.bg_color:
            bg_surf = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
            _draw_rounded_rect(bg_surf, tb.bg_color, (0, 0, total_w, total_h), tb.bg_radius)
            if tb.border_color:
                _draw_rounded_rect(bg_surf, tb.border_color, (0, 0, total_w, total_h),
                                   tb.bg_radius, tb.border_width)
            surface.blit(bg_surf, (int(dx), int(dy)))

        elem_surf = pygame.Surface((ew, eh), pygame.SRCALPHA)
        elem_surf.blit(ts, (indent_px, 0))

        final_surf, fx, fy = tb._apply_anim(elem_surf, dx + padx, dy + pady, w, h, progress)
        surface.blit(final_surf, (int(fx), int(fy)))

    def _render_imagebox(self, ib: ImageBox, surface, w, h, progress):
        # load/cache
        target_w = int(ib.size[0] * w) if ib.size else None
        target_h = int(ib.size[1] * h) if ib.size else None
        cache_key = (ib.source if isinstance(ib.source, str) else id(ib.source),
                     target_w, target_h, ib.maintain_aspect, ib.border_radius)

        if ib._cached_key != cache_key:
            try:
                if isinstance(ib.source, pygame.Surface):
                    img = ib.source.copy()
                elif isinstance(ib.source, (bytes, bytearray)):
                    img = pygame.image.load(io.BytesIO(ib.source)).convert_alpha()
                elif isinstance(ib.source, io.BytesIO):
                    img = pygame.image.load(ib.source).convert_alpha()
                elif isinstance(ib.source, str) and os.path.isfile(ib.source):
                    img = pygame.image.load(ib.source).convert_alpha()
                else:
                    # placeholder
                    img = pygame.Surface((target_w or 100, target_h or 100), pygame.SRCALPHA)
                    img.fill((80, 80, 80))
                    f = _font_cache.get(size=14)
                    txt = f.render("Image not found", True, (200, 200, 200))
                    img.blit(txt, (10, 10))

                if target_w and target_h:
                    if ib.maintain_aspect:
                        iw, ih = img.get_size()
                        scale = min(target_w / iw, target_h / ih)
                        nw, nh = int(iw * scale), int(ih * scale)
                    else:
                        nw, nh = target_w, target_h
                    img = pygame.transform.smoothscale(img, (nw, nh))

                # rounded corners via mask
                if ib.border_radius > 0:
                    mask = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                    _draw_rounded_rect(mask, (255, 255, 255, 255),
                                       (0, 0, img.get_width(), img.get_height()),
                                       ib.border_radius)
                    img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

                ib._cached_surface = img
                ib._cached_key = cache_key
            except Exception:
                ib._cached_surface = pygame.Surface((50, 50), pygame.SRCALPHA)
                ib._cached_surface.fill((80, 80, 80))
                ib._cached_key = cache_key

        img = ib._cached_surface
        iw, ih = img.get_size()
        dx, dy = ib._resolve_rect(iw, ih, w, h)

        if ib.shadow:
            _draw_shadow(surface, (dx, dy, iw, ih), ib.border_radius,
                         self.theme.get("shadow_color", (0, 0, 0, 50)),
                         offset=(5, 5), blur=10)

        final_surf, fx, fy = ib._apply_anim(img.copy(), dx, dy, w, h, progress)
        surface.blit(final_surf, (int(fx), int(fy)))

        if ib.border_color:
            _draw_rounded_rect(surface, ib.border_color,
                               (int(fx), int(fy), iw, ih),
                               ib.border_radius, ib.border_width)

    def _render_shape(self, sh: Shape, surface, w, h, progress):
        sw, s_h = int(sh.size[0] * w), int(sh.size[1] * h)
        dx, dy = sh._resolve_rect(sw, s_h, w, h)
        elem_surf = pygame.Surface((sw, s_h), pygame.SRCALPHA)

        if sh.shadow:
            _draw_shadow(surface, (dx, dy, sw, s_h), sh.radius,
                         self.theme.get("shadow_color", (0, 0, 0, 40)))

        stype = sh.shape_type.lower()
        if stype in ("rect", "rectangle"):
            if sh.gradient:
                gc = [_parse_color(c) for c in sh.gradient]
                _draw_gradient_rect(elem_surf, (0, 0, sw, s_h), gc[0], gc[-1])
            elif sh.fill:
                pygame.draw.rect(elem_surf, sh.color, (0, 0, sw, s_h))
            if sh.border_color:
                pygame.draw.rect(elem_surf, sh.border_color, (0, 0, sw, s_h), sh.border_width)

        elif stype in ("rounded_rect", "roundedrect", "card"):
            if sh.gradient:
                gc = [_parse_color(c) for c in sh.gradient]
                tmp = pygame.Surface((sw, s_h), pygame.SRCALPHA)
                _draw_gradient_rect(tmp, (0, 0, sw, s_h), gc[0], gc[-1])
                mask = pygame.Surface((sw, s_h), pygame.SRCALPHA)
                _draw_rounded_rect(mask, (255, 255, 255, 255), (0, 0, sw, s_h), sh.radius)
                tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                elem_surf.blit(tmp, (0, 0))
            elif sh.fill:
                _draw_rounded_rect(elem_surf, sh.color, (0, 0, sw, s_h), sh.radius)
            if sh.border_color:
                _draw_rounded_rect(elem_surf, sh.border_color, (0, 0, sw, s_h),
                                   sh.radius, sh.border_width)

        elif stype in ("circle", "ellipse"):
            cx, cy = sw // 2, s_h // 2
            if stype == "circle":
                r = min(cx, cy)
                if sh.fill:
                    pygame.draw.circle(elem_surf, sh.color, (cx, cy), r)
                if sh.border_color:
                    pygame.draw.circle(elem_surf, sh.border_color, (cx, cy), r, sh.border_width)
            else:
                if sh.fill:
                    pygame.draw.ellipse(elem_surf, sh.color, (0, 0, sw, s_h))
                if sh.border_color:
                    pygame.draw.ellipse(elem_surf, sh.border_color, (0, 0, sw, s_h), sh.border_width)

        elif stype in ("line",):
            pts = sh.points or [(0, 0.5), (1, 0.5)]
            if len(pts) >= 2:
                px = [(int(p[0] * sw), int(p[1] * s_h)) for p in pts]
                pygame.draw.lines(elem_surf, sh.color, False, px, sh.border_width or 2)

        elif stype in ("polygon",):
            pts = sh.points or []
            if len(pts) >= 3:
                px = [(int(p[0] * sw), int(p[1] * s_h)) for p in pts]
                if sh.fill:
                    pygame.draw.polygon(elem_surf, sh.color, px)
                if sh.border_color:
                    pygame.draw.polygon(elem_surf, sh.border_color, px, sh.border_width)

        final_surf, fx, fy = sh._apply_anim(elem_surf, dx, dy, w, h, progress)
        surface.blit(final_surf, (int(fx), int(fy)))

    def _render_dynamic(self, dg: DynamicGraphic, surface, w, h, progress, slide):
        dw, dh = int(dg.size[0] * w), int(dg.size[1] * h)
        dx, dy = dg._resolve_rect(dw, dh, w, h)

        if dg.render_fn:
            try:
                elem_surf = pygame.Surface((dw, dh), pygame.SRCALPHA)
                dt = 1.0 / max(1, self.fps)
                dg.render_fn(elem_surf, (0, 0, dw, dh), dt, slide._elapsed,
                             self.theme, **dg.user_data)
                final_surf, fx, fy = dg._apply_anim(elem_surf, dx, dy, w, h, progress)
                surface.blit(final_surf, (int(fx), int(fy)))
            except Exception:
                pass

    def _render_bulletlist(self, bl: BulletList, surface, w, h, progress):
        font = self._get_font_for_style(bl.style, h, bl.font_size, bl.bold)
        color = bl.color or self._color_for_style(bl.style)
        bullet_color = bl.bullet_color or _parse_color(self.theme.get("bullet_color", "#e94560"))
        max_w = int(bl.width * w) if bl.width else int(w * 0.8)
        indent_px = int(bl.indent * w)
        nested_indent_px = int(bl.nested_indent * w)
        lh = int(font.get_height() * bl.item_spacing)

        all_items = []
        for item in bl.items:
            if isinstance(item, (list, tuple)):
                all_items.append((0, str(item[0])))
                for sub in item[1:]:
                    all_items.append((1, str(sub)))
            else:
                all_items.append((0, str(item)))

        total_h = lh * len(all_items)
        total_w = max_w + indent_px
        base_dx, base_dy = bl._resolve_rect(total_w, total_h, w, h)

        for i, (level, text) in enumerate(all_items):
            item_progress = progress
            if bl.stagger_delay > 0 and bl.entry_anim != EntryAnim.NONE:
                delay = bl.anim_delay + i * bl.stagger_delay
                slide = None
                for s in self.slides:
                    if bl in s.elements:
                        slide = s
                        break
                if slide:
                    elapsed = slide._elapsed
                    if elapsed < delay:
                        continue
                    item_progress = min(1.0, (elapsed - delay) / bl.anim_duration)

            ep = bl._ease(item_progress)
            alpha = int(255 * bl.opacity * ep)

            bchar = bl.bullet_char if level == 0 else bl.sub_bullet_char
            extra_indent = nested_indent_px * level
            bfont = _font_cache.get(size=font.get_height() - 2)
            bs = bfont.render(bchar, True, bullet_color)
            ts = _render_text_surface(text, font, color,
                                       max_width=max_w - indent_px - extra_indent,
                                       line_spacing=1.2, align="left")

            y = base_dy + i * lh
            x_bullet = base_dx + extra_indent
            x_text = base_dx + indent_px + extra_indent

            if alpha < 255:
                bs.set_alpha(alpha)
                ts.set_alpha(alpha)

            ox = 0
            if bl.entry_anim == EntryAnim.SLIDE_IN_LEFT:
                ox = -(1 - ep) * w * 0.1
            elif bl.entry_anim == EntryAnim.SLIDE_IN_RIGHT:
                ox = (1 - ep) * w * 0.1

            surface.blit(bs, (int(x_bullet + ox), int(y + (lh - bs.get_height()) / 2)))
            surface.blit(ts, (int(x_text + ox), int(y + (lh - ts.get_height()) / 2)))

    def _render_codeblock(self, cb: CodeBlock, surface, w, h, progress):
        mono_font = self._get_font_for_style("code", h, cb.font_size)
        bg = cb.bg_color or _parse_color(self.theme.get("code_bg", (15, 15, 30, 240)))
        fg = cb.text_color or _parse_color(self.theme.get("code_color", "#80ffaa"))

        lines = cb.code.split("\n")
        lh = int(mono_font.get_height() * 1.5)
        pad = 16
        title_h = 0

        code_w = int(cb.width * w) if cb.width else int(w * 0.8)
        code_h = int(cb.height * h) if cb.height else (lh * len(lines) + 2 * pad + (32 if cb.title else 0))

        dx, dy = cb._resolve_rect(code_w, code_h, w, h)
        elem_surf = pygame.Surface((code_w, code_h), pygame.SRCALPHA)

        if cb.shadow:
            _draw_shadow(surface, (dx, dy, code_w, code_h), cb.border_radius,
                         self.theme.get("shadow_color", (0, 0, 0, 50)))

        _draw_rounded_rect(elem_surf, bg, (0, 0, code_w, code_h), cb.border_radius)

        # title bar
        if cb.title:
            title_h = 32
            bar_color = tuple(min(255, c + 15) for c in bg[:3]) + (bg[3] if len(bg) > 3 else 255,)
            _draw_rounded_rect(elem_surf, bar_color, (0, 0, code_w, title_h + cb.border_radius), cb.border_radius)
            _draw_rounded_rect(elem_surf, bg, (0, title_h, code_w, cb.border_radius + 2), 0)
            # dots
            for ci, cc in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
                pygame.draw.circle(elem_surf, cc, (16 + ci * 22, title_h // 2), 6)
            # title text
            tf = _font_cache.get(size=max(10, int(h * 0.018)), bold=True)
            tc = cb.title_color or _parse_color(self.theme.get("muted_color", "#808080"))
            tt = tf.render(cb.title, True, tc)
            elem_surf.blit(tt, (82, (title_h - tt.get_height()) // 2))

        # line numbers + code
        ln_w = 0
        if cb.line_numbers:
            ln_digits = len(str(len(lines)))
            ln_w = mono_font.size("0" * (ln_digits + 1))[0] + 8
            muted = _parse_color(self.theme.get("muted_color", "#606080"))

        for i, line in enumerate(lines):
            y = title_h + pad + i * lh
            if y + lh > code_h:
                break
            if cb.line_numbers:
                lns = mono_font.render(str(i + 1).rjust(len(str(len(lines)))), True, muted)
                elem_surf.blit(lns, (8, y))
            ls = mono_font.render(line, True, fg)
            elem_surf.blit(ls, (pad + ln_w, y))

        final_surf, fx, fy = cb._apply_anim(elem_surf, dx, dy, w, h, progress)
        surface.blit(final_surf, (int(fx), int(fy)))

    def _render_progressbar(self, pb: ProgressBar, surface, w, h, progress):
        pw, ph = int(pb.size[0] * w), int(pb.size[1] * h)
        dx, dy = pb._resolve_rect(pw, ph + (20 if pb.label else 0), w, h)
        accent = _parse_color(self.theme.get("accent", "#e94560"))
        bg = pb.bg_color or _parse_color(self.theme.get("muted_color", "#404060"))
        fill = pb.fill_color or accent

        actual_val = pb.value * (progress if pb.animated else 1.0)
        elem_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        _draw_rounded_rect(elem_surf, bg, (0, 0, pw, ph), pb.border_radius)
        fill_w = int(pw * actual_val)
        if fill_w > 0:
            _draw_rounded_rect(elem_surf, fill, (0, 0, fill_w, ph), pb.border_radius)

        label_surf = None
        label_h = 0
        if pb.label:
            lf = _font_cache.get(size=max(10, int(h * 0.018)), bold=True)
            lc = pb.label_color or _parse_color(self.theme.get("body_color", "#d0d0e0"))
            label_surf = lf.render(pb.label, True, lc)
            label_h = label_surf.get_height() + 4

        if label_surf:
            surface.blit(label_surf, (int(dx), int(dy)))

        final_surf, fx, fy = pb._apply_anim(elem_surf, dx, dy + label_h, w, h, progress)
        surface.blit(final_surf, (int(fx), int(fy)))

    def _render_divider(self, dv: Divider, surface, w, h, progress):
        color = dv.color or _parse_color(self.theme.get("muted_color", "#606080"))
        horiz = dv.orientation == "horizontal"
        length_px = int(dv.length * (w if horiz else h))
        thick = dv.thickness

        if horiz:
            ew, eh = length_px, thick
        else:
            ew, eh = thick, length_px

        dx, dy = dv._resolve_rect(ew, eh, w, h)
        elem_surf = pygame.Surface((ew, eh), pygame.SRCALPHA)

        if dv.gradient_fade:
            for i in range(length_px):
                t = i / max(1, length_px - 1)
                fade = math.sin(t * math.pi)
                c = (*color[:3], int((color[3] if len(color) > 3 else 255) * fade * dv.opacity))
                if horiz:
                    pygame.draw.line(elem_surf, c, (i, 0), (i, thick - 1))
                else:
                    pygame.draw.line(elem_surf, c, (0, i), (thick - 1, i))
        else:
            c = (*color[:3], int(255 * dv.opacity))
            elem_surf.fill(c)

        final_surf, fx, fy = dv._apply_anim(elem_surf, dx, dy, w, h, progress)
        surface.blit(final_surf, (int(fx), int(fy)))
