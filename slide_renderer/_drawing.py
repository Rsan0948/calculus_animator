"""Color parsing and pygame drawing helpers."""

import math

import pygame


def _parse_color(c) -> tuple:
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

def _draw_gradient_rect(surface, rect, color_top, color_bottom, vertical: bool=True) -> None:
    x, y, w, h = rect
    for i in range(h if vertical else w):
        t = i / max(1, (h if vertical else w) - 1)
        c = _lerp_color(color_top, color_bottom, t)
        if vertical:
            pygame.draw.line(surface, c, (x, y + i), (x + w - 1, y + i))
        else:
            pygame.draw.line(surface, c, (x + i, y), (x + i, y + h - 1))

def _draw_rounded_rect(surface, color, rect, radius, border: int=0) -> None:
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

def _draw_shadow(surface, rect, radius, shadow_color: tuple=(0, 0, 0, 40), offset: tuple=(4, 4), blur: int=8) -> None:
    sx, sy = offset
    for i in range(blur, 0, -1):
        alpha = int((shadow_color[3] if len(shadow_color) > 3 else 40) * (1 - i / blur))
        c = (*shadow_color[:3], alpha)
        s = pygame.Surface((int(rect[2]) + 2 * i, int(rect[3]) + 2 * i), pygame.SRCALPHA)
        _draw_rounded_rect(s, c, (0, 0, s.get_width(), s.get_height()), radius + i)
        surface.blit(s, (int(rect[0]) + sx - i, int(rect[1]) + sy - i))
