#!/usr/bin/env python3
"""
remove_png_bg.py – Batch remove solid/near-solid backgrounds from all PNG files
in the repository, keeping only the icon + text content.

Strategy
--------
1. Scan the whole repo tree for *.png files.
2. For every file:
   a. If the image already has a fully-transparent border all around (background
      was removed in a previous run) → skip (idempotency).
   b. Detect the dominant background colour by sampling the four corners.
      If the corners disagree too much, the image is deemed "complex" and left
      untouched (path is printed to stdout for manual review).
   c. Use a flood-fill from every corner to mark background pixels whose colour
      is within `THRESHOLD` of the detected background colour.
   d. Apply a gentle 1-pixel erosion on the foreground mask so that
      anti-aliased border pixels (which blend into the background) are kept
      sharp rather than left as ugly fringe.
   e. Write the result back to the original file (in-place replacement).

Usage
-----
    python scripts/remove_png_bg.py [--threshold 30] [--root .]

Arguments
---------
--threshold INT   Colour distance tolerance (0-255, default 30).  Lower = more
                  selective; higher = more aggressive background removal.
--root      DIR   Repository root to scan (default: parent of this script).
--dry-run         Print what would happen without writing any files.
"""

import argparse
import os
import sys
from collections import deque
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
    from PIL.ImageFilter import MinFilter
except ImportError:
    sys.exit(
        "Missing dependencies.  Run:  pip install Pillow numpy"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _colour_distance(c1: np.ndarray, c2: np.ndarray) -> float:
    """Euclidean distance between two RGB(A) pixel colours (ignoring alpha)."""
    return float(np.sqrt(np.sum((c1[:3].astype(int) - c2[:3].astype(int)) ** 2)))


def _sample_corner_colours(arr: np.ndarray, radius: int = 5) -> list:
    """Return a list of mean RGB values sampled near each of the four corners."""
    h, w = arr.shape[:2]
    r = min(radius, h // 4, w // 4)
    regions = [
        arr[:r, :r],          # top-left
        arr[:r, w - r:],      # top-right
        arr[h - r:, :r],      # bottom-left
        arr[h - r:, w - r:],  # bottom-right
    ]
    colours = []
    for region in regions:
        # Only consider opaque (or near-opaque) pixels when the image has alpha.
        if arr.shape[2] == 4:
            mask = region[:, :, 3] > 128
            if not np.any(mask):
                # Region is fully transparent → already processed
                colours.append(None)
                continue
            colours.append(region[mask, :3].mean(axis=0))
        else:
            colours.append(region[:, :, :3].reshape(-1, 3).mean(axis=0))
    return colours


def _flood_fill_background(arr: np.ndarray, bg_colour: np.ndarray,
                             threshold: int) -> np.ndarray:
    """
    BFS flood-fill from all four corners.

    Returns a boolean mask (H x W) where True = background pixel.
    Only pixels whose RGB distance to `bg_colour` is <= `threshold` AND that
    are reachable from a corner without crossing a non-background pixel are
    flagged.
    """
    h, w = arr.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    bg_mask = np.zeros((h, w), dtype=bool)

    # Pre-compute per-pixel distance to bg_colour
    rgb = arr[:, :, :3].astype(int)
    bg = bg_colour[:3].astype(int)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    is_bg_candidate = dist <= threshold

    queue = deque()
    for y, x in [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]:
        if not visited[y, x] and is_bg_candidate[y, x]:
            queue.append((y, x))
            visited[y, x] = True

    while queue:
        y, x = queue.popleft()
        bg_mask[y, x] = True
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and is_bg_candidate[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    return bg_mask


def _erode_background_mask(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """
    Shrink the background mask slightly so that anti-aliased edge pixels
    (which partially blend with the background) are kept in the foreground.
    """
    pil = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
    # Erosion via minimum filter – shrinks the background mask by one pixel so
    # anti-aliased border pixels (blended with background) remain foreground.
    for _ in range(iterations):
        pil = pil.filter(MinFilter(3))
    return np.array(pil) > 128


# ---------------------------------------------------------------------------
# Core processing function
# ---------------------------------------------------------------------------

def remove_background(path: Path, threshold: int = 30,
                       dry_run: bool = False) -> str:
    """
    Process a single PNG.

    Returns one of:
        "skipped"   – already transparent / no detectable solid background
        "processed" – background removed and file saved
        "complex"   – could not reliably detect background; file left untouched
        "error"     – unexpected exception
    """
    try:
        img = Image.open(path).convert("RGBA")
        arr = np.array(img)
        h, w = arr.shape[:2]

        # ── Idempotency check ──────────────────────────────────────────────
        # If all four corners are already fully transparent, skip.
        corners_alpha = [
            arr[0, 0, 3], arr[0, w - 1, 3],
            arr[h - 1, 0, 3], arr[h - 1, w - 1, 3],
        ]
        if all(a == 0 for a in corners_alpha):
            return "skipped"

        # ── Detect background colour from corners ──────────────────────────
        corner_colours = _sample_corner_colours(arr)
        valid_colours = [c for c in corner_colours if c is not None]
        if not valid_colours:
            return "skipped"  # all corners already transparent

        # Check that all sampled corners agree (i.e. they share the same bg)
        for i in range(len(valid_colours)):
            for j in range(i + 1, len(valid_colours)):
                if _colour_distance(valid_colours[i], valid_colours[j]) > threshold * 2:
                    print(f"  [COMPLEX] corners disagree — leaving unchanged: {path}")
                    return "complex"

        bg_colour = np.mean(valid_colours, axis=0)

        # ── Flood-fill background ──────────────────────────────────────────
        bg_mask = _flood_fill_background(arr, bg_colour, threshold)

        # If virtually nothing was identified as background, skip.
        if bg_mask.sum() < 10:
            return "skipped"

        # ── Erode mask to preserve anti-aliased edges ──────────────────────
        bg_mask = _erode_background_mask(bg_mask, iterations=1)

        # ── Apply transparency ─────────────────────────────────────────────
        result = arr.copy()
        result[bg_mask, 3] = 0

        if dry_run:
            return "processed"

        # Save with optimize=False to preserve exact per-pixel RGBA data without
        # any lossy re-compression that optimization passes might introduce.
        Image.fromarray(result, mode="RGBA").save(path, format="PNG", optimize=False)
        return "processed"

    except Exception as exc:  # noqa: BLE001
        print(f"  [ERROR] {path}: {exc}", file=sys.stderr)
        return "error"


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove solid backgrounds from all PNG files in a repo."
    )
    parser.add_argument(
        "--threshold", type=int, default=30,
        help="Colour-distance tolerance for background detection (default: 30)."
    )
    parser.add_argument(
        "--root", type=str, default=None,
        help="Root directory to scan (default: repo root derived from script location)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without writing any files."
    )
    args = parser.parse_args()

    if args.root:
        root = Path(args.root).resolve()
    else:
        # Default: one level above the scripts/ directory
        root = Path(__file__).resolve().parent.parent

    print(f"Scanning for PNG files under: {root}")
    if args.dry_run:
        print("DRY-RUN mode — no files will be modified.")

    png_files = sorted(root.rglob("*.png"))
    if not png_files:
        print("No PNG files found.")
        return

    counts = {"processed": 0, "skipped": 0, "complex": 0, "error": 0}

    for png_path in png_files:
        # Skip files inside hidden directories (e.g. .git)
        if any(part.startswith(".") for part in png_path.relative_to(root).parts):
            continue

        rel = png_path.relative_to(root)
        status = remove_background(png_path, threshold=args.threshold,
                                    dry_run=args.dry_run)
        counts[status] += 1

        if status == "processed":
            action = "would process" if args.dry_run else "processed"
            print(f"  [{action.upper()}] {rel}")
        elif status == "skipped":
            print(f"  [SKIPPED ] {rel}  (already transparent or no solid background)")
        # "complex" and "error" already printed inside remove_background()

    print()
    print("Summary:")
    print(f"  Processed : {counts['processed']}")
    print(f"  Skipped   : {counts['skipped']}")
    print(f"  Complex   : {counts['complex']}  ← review these manually")
    print(f"  Errors    : {counts['error']}")


if __name__ == "__main__":
    main()
