"""Slide element classes: base class, all element types, and Slide container."""

import pygame

from ._drawing import _parse_color
from ._enums import Anchor, EntryAnim, _parse_anchor, _parse_entry, _parse_transition


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


class Slide:
    """A single slide containing elements."""
    def __init__(self, transition="fade", transition_duration=0.4,
                 bg_color=None, bg_gradient=None, bg_image=None,
                 accent_bar=True, accent_bar_pos="bottom",
                 accent_bar_thickness=4, slide_number=True,
                 footer_text=None, on_enter=None, on_exit=None,
                 duration=None, auto_advance=False, name=None):
        self.elements: list[SlideElement] = []
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
