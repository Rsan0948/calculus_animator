"""SlideEngine - main engine: manages slides, themes, rendering, navigation, and animations."""

import copy
import io
import logging
import math
import os
from collections.abc import Callable

import pygame

from ._drawing import _draw_gradient_rect, _draw_rounded_rect, _draw_shadow, _parse_color
from ._elements import (
    BulletList, CodeBlock, Divider, DynamicGraphic, ImageBox,
    ProgressBar, Shape, Slide, TextBox,
)
from ._enums import EntryAnim, Transition
from ._font import _font_cache, _render_text_surface
from ._themes import THEMES


logger = logging.getLogger(__name__)


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

        self.slides: list[Slide] = []
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
        self.on_slide_change: Callable | None = None
        self.on_key: Callable | None = None

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
            except (OSError, ValueError, RuntimeError, TypeError) as exc:
                logger.debug("bg_image load/scale failed: %s", exc)
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
            except Exception as exc:  # noqa: BLE001 — render_fn is user-supplied; failure must not break the slide.
                logger.debug("dynamic render_fn raised: %s", exc)

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
