"""Programmatic icon generation using Pillow.

Generates system tray icons in 4 states — no external asset files needed.
Each icon is a 64x64 image of a stylized coffee cup / power symbol.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


def _create_base(size: int = 64) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Create a transparent base image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    return img, draw


def _draw_cup(draw: ImageDraw.ImageDraw, color: tuple[int, int, int], size: int = 64) -> None:
    """Draw a stylized coffee cup."""
    # Cup body
    margin = size // 8
    cup_top = size // 3
    cup_bottom = size - margin
    cup_left = margin
    cup_right = size - margin - size // 6

    draw.rounded_rectangle(
        [cup_left, cup_top, cup_right, cup_bottom],
        radius=size // 12,
        fill=color,
    )

    # Cup handle
    handle_left = cup_right - 2
    handle_top = cup_top + size // 8
    handle_bottom = cup_bottom - size // 6
    handle_right = size - margin + 2
    draw.arc(
        [handle_left, handle_top, handle_right, handle_bottom],
        start=-90,
        end=90,
        fill=color,
        width=max(2, size // 16),
    )

    # Steam lines (3 wavy lines above cup)
    steam_color = (*color, 180)
    for i in range(3):
        x = cup_left + (cup_right - cup_left) * (i + 1) // 4
        y_start = cup_top - 4
        y_end = margin
        mid_y = (y_start + y_end) // 2
        offset = 3 if i % 2 == 0 else -3
        draw.line(
            [(x, y_start), (x + offset, mid_y), (x, y_end)],
            fill=steam_color,
            width=max(1, size // 32),
        )


def create_active_icon(size: int = 64) -> Image.Image:
    """Green cup — at least one power request is active."""
    img, draw = _create_base(size)
    _draw_cup(draw, (76, 175, 80), size)  # Material Green 500
    return img


def create_idle_icon(size: int = 64) -> Image.Image:
    """Gray cup — monitoring but nothing triggered."""
    img, draw = _create_base(size)
    _draw_cup(draw, (158, 158, 158), size)  # Gray
    return img


def create_error_icon(size: int = 64) -> Image.Image:
    """Red cup with X — error state."""
    img, draw = _create_base(size)
    _draw_cup(draw, (244, 67, 54), size)  # Material Red 500

    # Draw X overlay
    m = size // 4
    draw.line([(m, m), (size - m, size - m)], fill=(255, 255, 255, 220), width=3)
    draw.line([(size - m, m), (m, size - m)], fill=(255, 255, 255, 220), width=3)
    return img


def create_paused_icon(size: int = 64) -> Image.Image:
    """Gray cup with pause bars — manually paused."""
    img, draw = _create_base(size)
    _draw_cup(draw, (120, 120, 120), size)  # Dark gray

    # Draw pause bars
    bar_w = size // 10
    bar_h = size // 3
    cx = size // 2
    cy = size // 2 + size // 8
    gap = size // 8

    draw.rectangle(
        [cx - gap - bar_w, cy - bar_h // 2, cx - gap, cy + bar_h // 2],
        fill=(255, 255, 255, 200),
    )
    draw.rectangle(
        [cx + gap - bar_w, cy - bar_h // 2, cx + gap, cy + bar_h // 2],
        fill=(255, 255, 255, 200),
    )
    return img
