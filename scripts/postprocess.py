#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Preserve original line art and replace only the model-generated chroma.

The diffusion model works at a lower resolution (default 0.5 MP).  This module
keeps the original full-resolution L channel (line art, text, screentone) and
combines it with the predicted LAB a/b channels, upscaled with a guided filter.
"""
import argparse
from pathlib import Path

import cv2
import numpy as np


def imread_unicode(path, flags=cv2.IMREAD_COLOR):
    """cv2.imread replacement that handles Windows Unicode paths."""
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def imwrite_unicode(path, image, params=None):
    """cv2.imwrite replacement that handles Windows Unicode paths."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix or ".png"
    ok, buf = cv2.imencode(ext, image, params or [])
    if not ok:
        raise OSError(f"could not encode {path}")
    buf.tofile(str(path))


def guided_filter(guide, src, radius=2, eps=1e-4):
    """Fast guided filter (He et al.) for a single-channel float image."""
    guide = guide.astype(np.float32)
    src = src.astype(np.float32)
    ksize = (2 * radius + 1, 2 * radius + 1)
    mean_i = cv2.boxFilter(guide, cv2.CV_32F, ksize)
    mean_p = cv2.boxFilter(src, cv2.CV_32F, ksize)
    corr_i = cv2.boxFilter(guide * guide, cv2.CV_32F, ksize)
    corr_ip = cv2.boxFilter(guide * src, cv2.CV_32F, ksize)
    var_i = corr_i - mean_i * mean_i
    cov_ip = corr_ip - mean_i * mean_p
    a = cov_ip / (var_i + eps)
    b = mean_p - a * mean_i
    mean_a = cv2.boxFilter(a, cv2.CV_32F, ksize)
    mean_b = cv2.boxFilter(b, cv2.CV_32F, ksize)
    return mean_a * guide + mean_b


def composite(original_path, color_path, output_path, radius=2, sat=1.0,
              white_threshold=256.0, neutral_mask=False, save_compare=None):
    original_bgr = imread_unicode(original_path, cv2.IMREAD_COLOR)
    if original_bgr is None:
        raise FileNotFoundError(original_path)
    color_bgr = imread_unicode(color_path, cv2.IMREAD_COLOR)
    if color_bgr is None:
        raise FileNotFoundError(color_path)

    h, w = original_bgr.shape[:2]
    color_bgr = cv2.resize(color_bgr, (w, h), interpolation=cv2.INTER_CUBIC)

    original_lab = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    color_lab = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    # OpenCV 8-bit LAB: L 0..255, a/b 0..255 with 128 offset.
    l_orig = original_lab[:, :, 0]
    a = color_lab[:, :, 1] - 128.0
    b = color_lab[:, :, 2] - 128.0

    guide = l_orig / 255.0
    a = guided_filter(guide, a, radius=radius, eps=1e-4)
    b = guided_filter(guide, b, radius=radius, eps=1e-4)
    a *= sat
    b *= sat

    # Optional paper/speech-bubble cleanup.  The default threshold of 256
    # disables this step because it can erase bright skin highlights.
    if white_threshold < 255.0:
        white = l_orig >= white_threshold
        if neutral_mask:
            chroma = np.sqrt(a * a + b * b)
            remove = white & (chroma < 6.0)
        else:
            remove = white & (b < -2.0)
        a[remove] = 0.0
        b[remove] = 0.0

    out_lab = np.dstack([l_orig, a + 128.0, b + 128.0]).clip(0, 255).astype(np.uint8)
    out_bgr = cv2.cvtColor(out_lab, cv2.COLOR_LAB2BGR)
    output_path = Path(output_path)
    imwrite_unicode(output_path, out_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 3])

    if save_compare:
        target_h = 1200

        def thumb(img):
            scale = target_h / img.shape[0]
            return cv2.resize(img, (int(img.shape[1] * scale), target_h),
                              interpolation=cv2.INTER_AREA)

        panels = [thumb(original_bgr), thumb(color_bgr), thumb(out_bgr)]
        sep = np.full((target_h, 12, 3), 255, np.uint8)
        row = np.hstack([panels[0], sep, panels[1], sep, panels[2]])
        imwrite_unicode(save_compare, row, [cv2.IMWRITE_JPEG_QUALITY, 92])

    return output_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original", required=True, help="full-resolution original page")
    ap.add_argument("--color", required=True, help="low-resolution model color layer")
    ap.add_argument("--output", required=True, help="full-resolution composite PNG")
    ap.add_argument("--radius", type=int, default=2)
    ap.add_argument("--sat", type=float, default=1.0)
    ap.add_argument("--white-threshold", type=float, default=256.0,
                    help="0-255; 256 disables paper/bubble cleanup")
    ap.add_argument("--neutral-mask", action="store_true")
    ap.add_argument("--compare", default=None, help="optional 3-panel QA JPEG")
    args = ap.parse_args()
    composite(args.original, args.color, args.output,
              radius=args.radius, sat=args.sat,
              white_threshold=args.white_threshold,
              neutral_mask=args.neutral_mask,
              save_compare=args.compare)
    print(args.output)


if __name__ == "__main__":
    main()
