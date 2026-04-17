#!/usr/bin/env python3
"""
make_all_icons_transparent.py
==============================
Batch-process all icon images in the repository:
  - Scan for .png / .jpg / .jpeg / .webp / .gif files
  - Skip images that already have a transparent background
  - Detect images with a plain solid-color background (white, black, gray, etc.)
  - Remove the background and save a new  <original_stem>.transparent.png  file
    next to the source image (original is NEVER overwritten)
  - Skip complex/photo images where auto-removal would be risky

Usage
-----
  # From repo root:
  python scripts/make_all_icons_transparent.py

  # Specify a custom directory:
  python scripts/make_all_icons_transparent.py --dir assets/icons

Dependencies
------------
  pip install Pillow numpy

How it works
------------
  1. Sample the four corner blocks of the image to estimate background colour.
  2. If the corners are very uniform (low std-dev) it is treated as a
     solid-colour background.
  3. A tolerance-based alpha-matting pass removes background pixels and
     cleans up anti-aliased fringe pixels along the boundary.
  4. If the corners are not uniform (photo / gradient) the file is skipped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# ── tuneable constants ────────────────────────────────────────────────────────
# Size (pixels) of the corner squares sampled to estimate background colour.
CORNER_SIZE = 10

# Maximum per-channel standard-deviation of corner pixels still considered
# a "solid background".  Lower = more conservative.
CORNER_STD_THRESHOLD = 18

# How much per-channel variation we allow when deciding a pixel "matches"
# the background colour during removal.
BG_TOLERANCE = 35

# Percentage of image pixels that must match the background to justify removal.
# Prevents accidental removal on images with almost no background.
MIN_BG_FRACTION = 0.10


# ── helpers ───────────────────────────────────────────────────────────────────

def _corner_sample(arr: np.ndarray, size: int = CORNER_SIZE) -> np.ndarray:
    """Return pixels from the four corner blocks of size x size."""
    h, w = arr.shape[:2]
    s = max(1, min(size, h // 4, w // 4))
    tl = arr[:s,  :s,  :3]
    tr = arr[:s,  -s:, :3]
    bl = arr[-s:, :s,  :3]
    br = arr[-s:, -s:, :3]
    return np.concatenate(
        [tl.reshape(-1, 3), tr.reshape(-1, 3),
         bl.reshape(-1, 3), br.reshape(-1, 3)],
        axis=0,
    )


def _is_solid_background(arr: np.ndarray) -> tuple[bool, np.ndarray | None]:
    """
    Returns (True, bg_colour) if the image has a solid-colour background,
    (False, None) otherwise.

    Strategy: sample the four corner blocks (most reliably background).
    If all four corners agree on nearly the same colour, that colour is
    the background.
    """
    corners = _corner_sample(arr)
    std = corners.std(axis=0)    # per-channel std across corner pixels
    mean = corners.mean(axis=0)
    if np.all(std <= CORNER_STD_THRESHOLD):
        return True, mean.astype(np.float32)
    return False, None


def _remove_background(img: Image.Image, bg_colour: np.ndarray) -> Image.Image:
    """
    Replace pixels within BG_TOLERANCE of bg_colour with transparency,
    using a soft alpha ramp at the edges for clean anti-aliasing.
    """
    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.float32)   # H x W x 4

    rgb = arr[:, :, :3]
    diff = np.abs(rgb - bg_colour)           # per-channel absolute diff
    dist = diff.max(axis=2)                  # Chebyshev distance to bg colour

    # Hard mask: certainly background
    hard_mask = dist <= BG_TOLERANCE
    # Soft transition zone for anti-aliasing
    soft_lo = BG_TOLERANCE
    soft_hi = BG_TOLERANCE + 20
    alpha_factor = np.clip((dist - soft_lo) / (soft_hi - soft_lo), 0.0, 1.0)

    new_alpha = arr[:, :, 3] * alpha_factor
    new_alpha[hard_mask] = 0.0

    result = arr.copy()
    result[:, :, 3] = new_alpha
    return Image.fromarray(result.astype(np.uint8), "RGBA")


def _already_transparent(arr: np.ndarray) -> bool:
    """True when the image already carries meaningful transparency."""
    if arr.shape[2] < 4:
        return False
    alpha = arr[:, :, 3]
    transparent = (alpha == 0).sum()
    return (transparent / alpha.size) >= 0.05


def process_image(
    src: Path,
    *,
    dry_run: bool = False,
) -> tuple[str, str]:
    """
    Process one image file.

    Returns
    -------
    (status, reason) where status is one of: 'processed', 'skipped', 'error'
    """
    # ── load ──────────────────────────────────────────────────────────────────
    try:
        img = Image.open(src)
        img.load()
    except Exception as exc:
        return "error", f"Cannot open: {exc}"

    rgba_arr = np.array(img.convert("RGBA"))

    # ── already transparent? ──────────────────────────────────────────────────
    if _already_transparent(rgba_arr):
        return "skipped", "Already has transparent background"

    # ── solid background? ─────────────────────────────────────────────────────
    is_solid, bg_colour = _is_solid_background(rgba_arr)
    if not is_solid:
        return "skipped", (
            "Background is not a uniform solid colour "
            "(complex photo / gradient) — auto-removal skipped to avoid damage"
        )

    # ── sanity: is there enough background to justify removal? ────────────────
    rgb = rgba_arr[:, :, :3].astype(np.float32)
    dist = np.abs(rgb - bg_colour).max(axis=2)
    bg_px = (dist <= BG_TOLERANCE).sum()
    if bg_px / dist.size < MIN_BG_FRACTION:
        return "skipped", "Very little background detected — skipping to avoid damage"

    # ── determine output path ─────────────────────────────────────────────────
    out_name = src.stem + ".transparent.png"
    out_path = src.parent / out_name

    if out_path.exists():
        return "skipped", f"Output already exists: {out_path.name}"

    # ── remove background ─────────────────────────────────────────────────────
    if not dry_run:
        result = _remove_background(img, bg_colour)
        result.save(out_path, "PNG")

    return "processed", f"bg~{bg_colour.astype(int).tolist()} -> {out_path.name}"


# ── main ──────────────────────────────────────────────────────────────────────

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def scan_images(root: Path) -> list[Path]:
    """Recursively find all image files under root, skipping .transparent.png."""
    found = []
    for ext in SUPPORTED_EXTS:
        for p in root.rglob(f"*{ext}"):
            # Skip already-generated transparent versions
            if p.stem.endswith(".transparent"):
                continue
            # Skip hidden dirs / .git
            if any(part.startswith(".") for part in p.parts):
                continue
            found.append(p)
    found.sort()
    return found


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-remove solid backgrounds from icon images."
    )
    parser.add_argument(
        "--dir",
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing any files",
    )
    args = parser.parse_args()

    root = Path(args.dir).resolve()
    if not root.is_dir():
        sys.exit(f"Error: {root} is not a directory")

    images = scan_images(root)
    if not images:
        print("No image files found.")
        return

    processed = []
    skipped = []
    errors = []

    print(f"Scanning {len(images)} image(s) in {root}\n")

    for src in images:
        rel = src.relative_to(root)
        status, reason = process_image(src, dry_run=args.dry_run)
        label = {
            "processed": "[PROCESSED]",
            "skipped":   "[SKIPPED]  ",
            "error":     "[ERROR]    ",
        }[status]
        print(f"  {label}  {rel}")
        print(f"             {reason}")
        if status == "processed":
            processed.append((src, reason))
        elif status == "skipped":
            skipped.append((src, reason))
        else:
            errors.append((src, reason))

    # ── summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"Summary  (dry_run={args.dry_run})")
    print("=" * 60)
    print(f"  Processed : {len(processed)}")
    print(f"  Skipped   : {len(skipped)}")
    print(f"  Errors    : {len(errors)}")

    if processed:
        print("\nProcessed:")
        for src, reason in processed:
            out = src.parent / (src.stem + ".transparent.png")
            print(f"  {src.name}  ->  {out.name}")
            print(f"    {reason}")

    if skipped:
        print("\nSkipped:")
        for src, reason in skipped:
            print(f"  {src.name}")
            print(f"    {reason}")

    if errors:
        print("\nErrors:")
        for src, reason in errors:
            print(f"  {src.name}")
            print(f"    {reason}")


if __name__ == "__main__":
    main()
