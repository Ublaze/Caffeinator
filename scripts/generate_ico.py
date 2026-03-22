"""Generate procawake.ico from Pillow icons for use in installer and exe."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from procawake.icons import create_active_icon

def main() -> None:
    output = Path(__file__).parent.parent / "assets" / "procawake.ico"
    output.parent.mkdir(parents=True, exist_ok=True)

    # Generate multiple sizes for the ICO file
    sizes = [16, 32, 48, 64, 128, 256]
    images = [create_active_icon(size=s) for s in sizes]

    # Save as ICO with all sizes
    images[0].save(
        str(output),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Generated {output} ({output.stat().st_size} bytes, {len(sizes)} sizes)")


if __name__ == "__main__":
    main()
