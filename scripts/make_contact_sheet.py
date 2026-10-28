#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a labeled contact sheet from colorized pages."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--columns", type=int, default=6)
    ap.add_argument("--thumb-width", type=int, default=300)
    ap.add_argument("--label-height", type=int, default=26)
    args = ap.parse_args()

    files = sorted(Path(args.input_dir).glob("*.png"))
    files = [p for p in files if not p.name.startswith(".")]
    if not files:
        raise SystemExit("no PNG files")

    thumbs = []
    for path in files:
        image = Image.open(path).convert("RGB")
        height = int(image.height * args.thumb_width / image.width)
        thumbs.append((path, image.resize((args.thumb_width, height),
                                          Image.LANCZOS)))

    cell_w = args.thumb_width
    cell_h = max(image.height for _, image in thumbs) + args.label_height
    cols = args.columns
    rows = (len(thumbs) + cols - 1) // cols
    margin = 12
    sheet = Image.new(
        "RGB",
        (cols * cell_w + (cols + 1) * margin,
         rows * cell_h + (rows + 1) * margin),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    for index, (path, thumb) in enumerate(thumbs):
        row, col = divmod(index, cols)
        x = margin + col * (cell_w + margin)
        y = margin + row * (cell_h + margin)
        sheet.paste(thumb, (x, y))
        draw.text((x + 4, y + thumb.height + 3), path.stem, fill="black", font=font)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92, subsampling=1)
    print(f"{len(thumbs)} pages -> {output}")


if __name__ == "__main__":
    main()
