"""Capacity test worker for slide text fit and rendering.

Input JSON (stdin):
{
  "text": str,
  "width": int,
  "height": int,
  "with_image": bool,
  "page_index": int,
  "metrics_only": bool
}
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path


def _wrap_paragraph_lines(text: str, font, max_width: int) -> list[str]:
    words = text.split(" ")
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if not cur or font.size(cand)[0] <= max_width:
            cur = cand
        else:
            lines.append(cur)
            # hard-break long words
            if font.size(w)[0] <= max_width:
                cur = w
            else:
                chunk = ""
                for ch in w:
                    cc = chunk + ch
                    if font.size(cc)[0] <= max_width:
                        chunk = cc
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                cur = chunk
    if cur:
        lines.append(cur)
    return lines


def _paginate(text: str, font, max_width: int, max_lines: int) -> list[str]:
    paras = text.replace("\r\n", "\n").split("\n")
    all_lines: list[str] = []
    for i, p in enumerate(paras):
        if p.strip():
            all_lines.extend(_wrap_paragraph_lines(p, font, max_width))
        else:
            all_lines.append("")
        if i != len(paras) - 1:
            all_lines.append("")
    pages = []
    for i in range(0, len(all_lines), max_lines):
        pages.append("\n".join(all_lines[i:i + max_lines]).strip("\n"))
    return pages or [""]


def _render(payload: dict) -> dict:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame  # noqa: PLC0415

    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()

    w = int(payload.get("width", 1300))
    h = int(payload.get("height", 812))
    with_image = bool(payload.get("with_image", False))
    metrics_only = bool(payload.get("metrics_only", False))
    text = str(payload.get("text", "") or "")
    req_page = max(0, int(payload.get("page_index", 0)))

    font_header = pygame.font.SysFont("dejavusans", max(22, int(h * 0.035)), bold=True)
    font_sub = pygame.font.SysFont("dejavusans", max(16, int(h * 0.022)))
    font_body = pygame.font.SysFont("dejavusans", max(20, int(h * 0.028)))

    panel = pygame.Rect(int(0.04 * w), int(0.05 * h), int(0.92 * w), int(0.9 * h))
    content = pygame.Rect(panel.x + 24, panel.y + 95, panel.w - 48, panel.h - 120)
    text_rect = content.inflate(-28, -24)
    image_rect = None
    if with_image:
        usable_area = text_rect.w * text_rect.h
        side = int(math.sqrt(usable_area * 0.12))  # ~12% area square
        side = max(70, min(side, int(text_rect.h * 0.38)))
        image_rect = pygame.Rect(text_rect.right - side, text_rect.y + 4, side, side)
        # text should not collide with image: reserve right gutter globally (simple + deterministic)
        text_rect.width -= (side + 16)

    line_h = int(font_body.get_height() * 1.45)
    max_lines = max(1, text_rect.h // line_h)
    pages = _paginate(text, font_body, text_rect.w, max_lines)
    page_index = min(req_page, len(pages) - 1)
    if page_index != req_page:
        print(f"[warn] capacity worker: page_index clamped from {req_page} to {page_index} (total pages: {len(pages)})", file=sys.stderr)
    page_text = pages[page_index]

    all_chars = len(page_text)
    non_space = len(re.sub(r"\s+", "", page_text))
    overflow_chars = max(0, len(text) - len("\n".join(pages[: page_index + 1])))

    if metrics_only:
        return {
            "success": True,
            "page_index": page_index,
            "total_pages": len(pages),
            "page_text": page_text,
            "all_pages_text": pages,
            "chars_on_page": all_chars,
            "usable_chars_on_page": non_space,
            "max_lines": int(max_lines),
            "line_height_px": int(line_h),
            "with_image": with_image,
            "overflow_chars": overflow_chars,
        }

    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    # slide background
    surf.fill((15, 21, 48))
    pygame.draw.rect(surf, (12, 17, 38), panel, border_radius=16)
    pygame.draw.rect(surf, (63, 79, 124), panel, width=2, border_radius=16)

    # header region (matches current conceptual slide structure)
    sub_txt = "Capacity Test · Slide Fit Meter"
    head_txt = "Text Capacity Measurement"
    sub_s = font_sub.render(sub_txt, True, (161, 178, 216))
    head_s = font_header.render(head_txt, True, (240, 245, 255))
    surf.blit(sub_s, (panel.x + 24, panel.y + 18))
    surf.blit(head_s, (panel.x + 24, panel.y + 46))

    # content box with hard clipping
    pygame.draw.rect(surf, (20, 28, 58), content, border_radius=12)
    pygame.draw.rect(surf, (70, 86, 130), content, width=1, border_radius=12)
    if with_image and image_rect is not None:
        pygame.draw.rect(surf, (42, 51, 87), image_rect, border_radius=8)
        pygame.draw.rect(surf, (113, 132, 189), image_rect, width=1, border_radius=8)

    # render text with hard clip
    old_clip = surf.get_clip()
    surf.set_clip(text_rect)
    y = text_rect.y
    for ln in page_text.split("\n"):
        if y + line_h > text_rect.bottom:
            break
        line_s = font_body.render(ln, True, (229, 236, 252))
        surf.blit(line_s, (text_rect.x, y))
        y += line_h
    surf.set_clip(old_clip)

    # page badge
    page_badge = font_sub.render(f"Page {page_index + 1} / {len(pages)}", True, (161, 178, 216))
    surf.blit(page_badge, (panel.right - page_badge.get_width() - 22, panel.y + 22))

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
    try:
        pygame.image.save(surf, path)
        png = Path(path).read_bytes()
    finally:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "success": True,
        "data_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        "page_index": page_index,
        "total_pages": len(pages),
        "page_text": page_text,
        "all_pages_text": pages,
        "chars_on_page": all_chars,
        "usable_chars_on_page": non_space,
        "max_lines": int(max_lines),
        "line_height_px": int(line_h),
        "with_image": with_image,
        "overflow_chars": overflow_chars,
    }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        out = _render(payload)
        sys.stdout.write(json.dumps(out))
        return 0
    except Exception as exc:
        sys.stdout.write(json.dumps({"success": False, "error": str(exc), "traceback": traceback.format_exc()}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
