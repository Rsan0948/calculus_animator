"""Enums and parsing helpers for slide_renderer."""

from enum import Enum, auto


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
