"""Build the desktop sprite atlas from the untouched four-pose illustration.

Run once after changing desk-sheet.png or the supplied Camposol logo:
    python scripts/prepare_companion.py

Background removal and pose alignment belong to asset preparation, not startup.
The resulting two-by-two RGBA atlas preserves the original display resolution.
"""
from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_BOUNDS = (222, 178)
BADGE_BOX = (401, 412, 437, 456)


def cutout(frame: Image.Image) -> Image.Image:
    """Remove only neutral exterior pixels connected to the image boundary."""
    width, height = frame.size
    pixels = frame.load()
    visited = bytearray(width * height)
    boundary: deque[tuple[int, int]] = deque()

    def add(x: int, y: int) -> None:
        index = y * width + x
        if visited[index]:
            return
        visited[index] = 1
        red, green, blue, _ = pixels[x, y]
        if min(red, green, blue) >= 226 and max(red, green, blue) - min(red, green, blue) <= 14:
            boundary.append((x, y))
            pixels[x, y] = (red, green, blue, 0)

    for x in range(width):
        add(x, 0)
        add(x, height - 1)
    for y in range(height):
        add(0, y)
        add(width - 1, y)
    while boundary:
        x, y = boundary.popleft()
        if x:
            add(x - 1, y)
        if x + 1 < width:
            add(x + 1, y)
        if y:
            add(x, y - 1)
        if y + 1 < height:
            add(x, y + 1)
    return frame


def prepare_sprites(source_path: Path, logo_path: Path) -> tuple[Image.Image, dict]:
    """Prepare all four poses; never overwrite or alter the source artwork."""
    with Image.open(source_path) as source:
        if source.width % 2 or source.height % 2:
            raise ValueError("The pose sheet must have an even two-by-two grid.")
        width, height = source.width // 2, source.height // 2
        frames = [
            cutout(source.crop((
                (index % 2) * width,
                (index // 2) * height,
                (index % 2 + 1) * width,
                (index // 2 + 1) * height,
            )).convert("RGBA"))
            for index in range(4)
        ]

    bounds = [frame.getchannel("A").getbbox() for frame in frames]
    if any(box is None for box in bounds):
        raise ValueError("The pose sheet contains an empty sprite.")
    base = bounds[0]
    aligned = []
    for frame, box in zip(frames, bounds):
        canvas = Image.new("RGBA", (width, height))
        canvas.alpha_composite(frame, (base[0] - box[0], base[3] - box[3]))
        aligned.append(canvas)
    boxes = [frame.getchannel("A").getbbox() for frame in aligned]
    common = (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )

    # Fit the original square logo inside the decorative badge without stretching
    # the artwork to the perspective-shaped badge. Its readable copy is in the UI.
    left, top, right, bottom = BADGE_BOX
    with Image.open(logo_path) as logo_source:
        logo = ImageOps.contain(
            logo_source.convert("RGBA"),
            (right - left, bottom - top),
            Image.Resampling.LANCZOS,
        )
    mask = Image.new("L", logo.size)
    ImageDraw.Draw(mask).ellipse((0, 0, logo.width - 1, logo.height - 1), fill=255)
    logo.putalpha(mask)
    logo_position = (
        left + (right - left - logo.width) // 2,
        top + (bottom - top - logo.height) // 2,
    )
    poses = []
    for frame in aligned:
        frame.alpha_composite(logo, logo_position)
        frame = frame.crop(common)
        frame.thumbnail(DISPLAY_BOUNDS, Image.Resampling.LANCZOS)
        poses.append(frame)

    pose_width, pose_height = poses[0].size
    atlas = Image.new("RGBA", (pose_width * 2, pose_height * 2))
    for index, frame in enumerate(poses):
        # Paste retains RGB in partially transparent pixels exactly; composing
        # onto another transparent image would needlessly process alpha again.
        atlas.paste(frame, ((index % 2) * pose_width, (index // 2) * pose_height))
    return atlas, {
        "poses": len(poses),
        "pose_size": [pose_width, pose_height],
        "atlas_size": list(atlas.size),
        "source_crop": list(common),
        "logo_size": list(logo.size),
        "logo_position": list(logo_position),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "assets/mascot/desk-sheet.png")
    parser.add_argument("--logo", type=Path, default=ROOT / "assets/branding/camposol-original.jpg")
    parser.add_argument("--output", type=Path, default=ROOT / "assets/mascot/desk-sprites.png")
    args = parser.parse_args()
    if args.output.resolve() in (args.source.resolve(), args.logo.resolve()):
        parser.error("The output must be different from the original artwork and logo.")
    atlas, metadata = prepare_sprites(args.source, args.logo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(args.output, format="PNG", optimize=True)
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size, **metadata}))


if __name__ == "__main__":
    main()
