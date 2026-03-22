"""Generate GitHub banner and social preview images for Caffeinator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PIL import Image, ImageDraw, ImageFont


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try Segoe UI, fall back to default."""
    names = ["segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf"] if bold else [
        "segoeui.ttf", "arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_coffee_cup(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int,
                     color: tuple[int, int, int]) -> None:
    """Draw a stylized coffee cup centered at (cx, cy)."""
    # Cup body
    w = size
    h = int(size * 1.1)
    left = cx - w // 2
    top = cy - h // 3
    right = cx + w // 2 - size // 5
    bottom = cy + h // 2

    draw.rounded_rectangle([left, top, right, bottom], radius=size // 8, fill=color)

    # Handle
    handle_left = right - 3
    handle_top = top + size // 5
    handle_bottom = bottom - size // 5
    handle_right = cx + w // 2 + size // 6
    draw.arc([handle_left, handle_top, handle_right, handle_bottom],
             start=-90, end=90, fill=color, width=max(3, size // 10))

    # Steam
    steam_color = (*color, 160)
    for i in range(3):
        x = left + (right - left) * (i + 1) // 4
        y_top = top - size // 3
        y_mid = top - size // 6
        offset = 5 if i % 2 == 0 else -5
        draw.line([(x, top - 5), (x + offset, y_mid), (x, y_top)],
                  fill=steam_color, width=max(2, size // 15))


def generate_banner() -> None:
    """Generate the main README banner (1280x400)."""
    W, H = 1280, 400
    img = Image.new("RGBA", (W, H), (30, 30, 46, 255))  # Dark bg
    draw = ImageDraw.Draw(img)

    # Gradient overlay (subtle)
    for y in range(H):
        alpha = int(20 * (y / H))
        draw.line([(0, y), (W, y)], fill=(137, 180, 250, alpha))

    # Coffee cup icon
    _draw_coffee_cup(draw, 180, 200, 100, (137, 180, 250))

    # Title
    title_font = _get_font(72, bold=True)
    draw.text((300, 100), "Caffeinator", fill=(205, 214, 244), font=title_font)

    # Tagline
    tag_font = _get_font(28)
    draw.text((305, 195), 'Your screen stays awake. No questions asked.',
              fill=(166, 227, 161), font=tag_font)

    # Subtitle
    sub_font = _get_font(18)
    draw.text((305, 245), "Process-aware Windows sleep prevention  |  System tray app  |  Zero dependencies",
              fill=(127, 132, 156), font=sub_font)

    # Bottom accent line
    draw.rectangle([(0, H - 4), (W, H)], fill=(137, 180, 250))

    output = Path(__file__).parent.parent / "assets" / "banner.png"
    img.save(str(output), "PNG")
    print(f"Generated {output}")


def generate_social_preview() -> None:
    """Generate GitHub social preview (1280x640)."""
    W, H = 1280, 640
    img = Image.new("RGBA", (W, H), (30, 30, 46, 255))
    draw = ImageDraw.Draw(img)

    # Coffee cup (centered, larger)
    _draw_coffee_cup(draw, W // 2, 220, 140, (137, 180, 250))

    # Title
    title_font = _get_font(64, bold=True)
    bbox = draw.textbbox((0, 0), "Caffeinator", font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 350), "Caffeinator", fill=(205, 214, 244), font=title_font)

    # Tagline
    tag_font = _get_font(24)
    tag = "Process-aware Windows sleep prevention"
    bbox = draw.textbbox((0, 0), tag, font=tag_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 435), tag, fill=(166, 227, 161), font=tag_font)

    # Features
    feat_font = _get_font(18)
    features = "Per-app rules  •  System tray  •  Modern Win32 API  •  Standalone .exe"
    bbox = draw.textbbox((0, 0), features, font=feat_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 485), features, fill=(127, 132, 156), font=feat_font)

    # Bottom accent
    draw.rectangle([(0, H - 4), (W, H)], fill=(137, 180, 250))

    output = Path(__file__).parent.parent / "assets" / "social-preview.png"
    img.save(str(output), "PNG")
    print(f"Generated {output}")


def generate_screenshot_mockup() -> None:
    """Generate a GUI mockup showing the settings window concept."""
    W, H = 700, 500
    img = Image.new("RGBA", (W, H), (42, 42, 60, 255))
    draw = ImageDraw.Draw(img)

    # Window chrome
    draw.rectangle([(0, 0), (W, 36)], fill=(30, 30, 46))
    draw.rectangle([(0, 36), (W, 37)], fill=(69, 71, 90))

    # Window title
    title_font = _get_font(13)
    draw.text((14, 10), "procawake v0.1.0", fill=(205, 214, 244), font=title_font)

    # Window buttons
    for i, color in enumerate([(244, 67, 54), (255, 235, 59), (76, 175, 80)]):
        draw.ellipse([(W - 80 + i * 24, 10), (W - 64 + i * 24, 26)], fill=color)

    # Header
    header_font = _get_font(22, bold=True)
    draw.text((20, 52), "procawake", fill=(205, 214, 244), font=header_font)
    sub_font = _get_font(12)
    draw.text((20, 82), "Select applications that should prevent your screen from sleeping",
              fill=(127, 132, 156), font=sub_font)

    # Column headers
    col_font = _get_font(11)
    draw.text((50, 115), "Application", fill=(127, 132, 156), font=col_font)
    draw.text((250, 115), "Process", fill=(127, 132, 156), font=col_font)
    draw.text((430, 115), "Status", fill=(127, 132, 156), font=col_font)
    draw.text((560, 115), "Action", fill=(127, 132, 156), font=col_font)
    draw.line([(20, 135), (W - 20, 135)], fill=(69, 71, 90), width=1)

    # App rows
    app_font = _get_font(13)
    dim_font = _get_font(12)
    apps = [
        ("Claude Code", "claude.exe", "running", "both", True),
        ("VS Code", "code.exe", "running", "system", True),
        ("Microsoft Teams", "ms-teams.exe", "running", "display", True),
        ("Google Chrome", "chrome.exe", "running", "display", False),
        ("VLC Media Player", "vlc.exe", "", "display", False),
        ("OBS Studio", "obs64.exe", "", "display", False),
        ("Notepad++", "notepad++.exe", "", "system", False),
    ]

    y = 148
    for name, proc, status, action, checked in apps:
        row_bg = (54, 54, 73, 180) if checked else (42, 42, 60, 0)
        if checked:
            draw.rectangle([(14, y - 2), (W - 14, y + 26)], fill=(54, 54, 73))

        # Checkbox
        cb_color = (137, 180, 250) if checked else (69, 71, 90)
        draw.rounded_rectangle([(22, y + 3), (38, y + 19)], radius=3,
                                outline=cb_color, width=2)
        if checked:
            draw.line([(26, y + 11), (30, y + 16)], fill=(137, 180, 250), width=2)
            draw.line([(30, y + 16), (35, y + 6)], fill=(137, 180, 250), width=2)

        draw.text((50, y + 2), name, fill=(205, 214, 244), font=app_font)
        draw.text((250, y + 3), proc, fill=(127, 132, 156), font=dim_font)

        status_color = (166, 227, 161) if status else (127, 132, 156)
        draw.text((430, y + 3), status, fill=status_color, font=dim_font)

        # Action dropdown
        draw.rounded_rectangle([(555, y + 1), (660, y + 23)], radius=4,
                                fill=(54, 54, 73), outline=(69, 71, 90))
        draw.text((565, y + 3), action, fill=(205, 214, 244), font=dim_font)
        draw.text((640, y + 3), "v", fill=(127, 132, 156), font=dim_font)

        y += 34

    # Bottom bar
    draw.rectangle([(0, H - 60), (W, H)], fill=(30, 30, 46))
    draw.line([(0, H - 60), (W, H - 60)], fill=(69, 71, 90))

    # Buttons
    draw.rounded_rectangle([(20, H - 45), (100, H - 15)], radius=6,
                            fill=(54, 54, 73), outline=(69, 71, 90))
    draw.text((35, H - 40), "Rescan", fill=(205, 214, 244), font=dim_font)

    draw.rounded_rectangle([(460, H - 48), (680, H - 12)], radius=8,
                            fill=(137, 180, 250))
    btn_font = _get_font(13, bold=True)
    draw.text((475, H - 40), "Save & Start Monitoring", fill=(30, 30, 46), font=btn_font)

    output = Path(__file__).parent.parent / "assets" / "screenshot.png"
    img.save(str(output), "PNG")
    print(f"Generated {output}")


if __name__ == "__main__":
    generate_banner()
    generate_social_preview()
    generate_screenshot_mockup()
