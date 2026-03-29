"""slide_renderer package — drop-in replacement for the original slide_renderer.py module.

All public names are re-exported here so existing imports like:
    from slide_renderer import SlideEngine, Slide, TextBox, Shape, BulletList
continue to work without any changes.
"""

from ._enums import Anchor, EntryAnim, Transition
from ._themes import register_theme
from ._elements import (
    SlideElement,
    TextBox,
    ImageBox,
    Shape,
    DynamicGraphic,
    BulletList,
    CodeBlock,
    ProgressBar,
    Divider,
    Slide,
)
from .engine import SlideEngine

__all__ = [
    "Anchor",
    "Transition",
    "EntryAnim",
    "SlideElement",
    "TextBox",
    "ImageBox",
    "Shape",
    "DynamicGraphic",
    "BulletList",
    "CodeBlock",
    "ProgressBar",
    "Divider",
    "Slide",
    "SlideEngine",
    "register_theme",
]
