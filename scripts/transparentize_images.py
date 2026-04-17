#!/usr/bin/env python3
"""
transparentize_images.py — Batch background removal for PPT asset preparation.

For each image file found in the repository, this script:
  1. Detects whether the image already has a transparent background (skips if so).
  2. Detects whether the image has a simple solid/near-solid colour background
     (black, white, grey, or any other dominant corner colour).
  3. Removes that background via flood-fill + anti-aliasing and writes
     <original_name>.transparent.png beside the original (never overwrites it).
  4. Skips complex / photographic backgrounds and logs the reason.

Supported formats: .png .jpg .jpeg .webp .gif (raster only — .svg is skipped).

Usage
-----
    python scripts/transparentize_images.py [ROOT_DIR]

    ROOT_DIR  Directory to scan recursively (default: repo root, i.e. the
              parent of the ``scripts/`` folder).

Dependencies
------------
    pip install Pillow numpy

Output
------
    <image_dir>/<name>.transparent.png   — processed image (transparent bg)
    scripts/transparentize_report.json   — machine-readable processing log
    scripts/transparentize_report.md     — human-readable summary
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Constants / tunables
# ---------------------------------------------------------------------------
SUPPORTED_RASTER = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SUPPORTED_VECTOR = {".svg"}  # logged as skipped (cannot reliably process)

# Colour-similarity threshold (0-255) for considering two pixels the same hue.
CORNER_SIMILARITY_THRESHOLD = 30

# If corner pixels' std-dev across R/G/B channels is below this value we treat
# the background as "uniform / single-colour".
CORNER_UNIFORMITY_THRESHOLD = 20

# Flood-fill tolerance: pixels within this Euclidean distance in RGB space from
# the seed colour are considered background.
FLOODFILL_TOLERANCE = 40

# Anti-aliasing: grow the alpha mask by this many pixels, then feather.
FEATHER_RADIUS = 1

# If ≥ this fraction of total pixels are transparent in an RGBA image, assume
# it already has a proper transparent background.
ALREADY_TRANSPARENT_THRESHOLD = 0.10  # 10 % transparency → likely intentional


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _is_already_transparent(img: Image.Image) -> bool:
    """Return True if the image already carries a meaningful transparent bg."""
    if img.mode != "RGBA":
        return False
    arr = np.array(img)
    alpha = arr[:, :, 3]
    transparent_ratio = np.sum(alpha == 0) / alpha.size
    if transparent_ratio < ALREADY_TRANSPARENT_THRESHOLD:
        return False
    # Also verify that the image corners / borders are transparent so we know
    # the *background* (not just isolated cut-outs) is transparent.
    h, w = alpha.shape
    border = np.concatenate([
        alpha[0, :], alpha[-1, :], alpha[:, 0], alpha[:, -1]
    ])
    border_transparent = np.sum(border == 0) / border.size
    return border_transparent >= 0.5


def _sample_corner_colours(arr_rgb: np.ndarray) -> np.ndarray:
    """Return an (N, 3) array of sampled corner/edge pixel colours."""
    h, w = arr_rgb.shape[:2]
    samples = []
    margin = max(1, min(5, h // 20, w // 20))
    for r in range(margin):
        for c in range(margin):
            samples.append(arr_rgb[r, c])
            samples.append(arr_rgb[r, w - 1 - c])
            samples.append(arr_rgb[h - 1 - r, c])
            samples.append(arr_rgb[h - 1 - r, w - 1 - c])
    return np.array(samples, dtype=np.float32)


def _is_uniform_background(corner_colours: np.ndarray) -> bool:
    """True if sampled corners share a sufficiently uniform colour."""
    if len(corner_colours) == 0:
        return False
    std = corner_colours.std(axis=0)  # per-channel std
    return float(std.max()) < CORNER_UNIFORMITY_THRESHOLD


def _mean_background_colour(corner_colours: np.ndarray) -> np.ndarray:
    """Return the mean (R, G, B) of sampled corners as uint8."""
    return corner_colours.mean(axis=0).astype(np.uint8)


def _colour_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Euclidean RGB distance between arrays a and b (element-wise rows)."""
    return np.sqrt(np.sum((a.astype(np.float32) - b.astype(np.float32)) ** 2,
                          axis=-1))


def _floodfill_background_mask(arr_rgb: np.ndarray,
                                bg_colour: np.ndarray,
                                tolerance: int) -> np.ndarray:
    """
    Flood-fill from all four image corners.  Returns a boolean mask (h×w)
    that is True wherever a pixel belongs to the background.
    """
    h, w = arr_rgb.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    is_bg = np.zeros((h, w), dtype=bool)

    # Distance of every pixel to the background colour.
    dist = _colour_distance(arr_rgb.reshape(-1, 3),
                             bg_colour).reshape(h, w)
    candidate = dist <= tolerance

    # BFS from the four corners.
    from collections import deque
    seeds = [
        (0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1),
    ]
    queue: deque[tuple[int, int]] = deque()
    for r, c in seeds:
        if not visited[r, c] and candidate[r, c]:
            queue.append((r, c))
            visited[r, c] = True
            is_bg[r, c] = True

    while queue:
        r, c = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and not visited[nr, nc]:
                visited[nr, nc] = True
                if candidate[nr, nc]:
                    is_bg[nr, nc] = True
                    queue.append((nr, nc))
    return is_bg


def _feather_alpha(alpha: np.ndarray, radius: int) -> np.ndarray:
    """Simple box-blur feathering to soften hard alpha edges."""
    from PIL import ImageFilter
    pil_alpha = Image.fromarray(alpha)
    for _ in range(radius):
        pil_alpha = pil_alpha.filter(ImageFilter.SMOOTH_MORE)
    return np.array(pil_alpha)


def remove_background(img: Image.Image) -> Image.Image:
    """
    Remove the solid-colour background from *img* and return a new RGBA image
    with that background replaced by transparency.
    """
    # Work on a copy so we never mutate the caller's object.
    img_rgba = img.convert("RGBA")
    arr = np.array(img_rgba)
    arr_rgb = arr[:, :, :3]

    corner_colours = _sample_corner_colours(arr_rgb)
    bg_colour = _mean_background_colour(corner_colours)

    # Build the background mask via flood-fill.
    bg_mask = _floodfill_background_mask(arr_rgb, bg_colour, FLOODFILL_TOLERANCE)

    # Create new alpha channel: 0 where background, 255 elsewhere.
    new_alpha = np.where(bg_mask, np.uint8(0), np.uint8(255))

    # Feather edges to reduce hard / jagged borders.
    if FEATHER_RADIUS > 0:
        new_alpha = _feather_alpha(new_alpha, FEATHER_RADIUS)

    # Merge back.
    result = arr.copy()
    result[:, :, 3] = new_alpha
    return Image.fromarray(result, "RGBA")


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------

def analyse_and_process(image_path: Path) -> dict:
    """
    Analyse *image_path* and (if appropriate) write a transparent version.

    Returns a dict suitable for the JSON report:
        status  : "processed" | "skipped" | "error"
        reason  : human-readable explanation
        output  : output file path (str) or None
    """
    suffix = image_path.suffix.lower()

    # --- SVG: skip -----------------------------------------------------------
    if suffix in SUPPORTED_VECTOR:
        return {
            "file": str(image_path),
            "status": "skipped",
            "reason": "SVG is a vector format — raster background removal is not applicable.",
            "output": None,
        }

    # --- Unsupported format --------------------------------------------------
    if suffix not in SUPPORTED_RASTER:
        return {
            "file": str(image_path),
            "status": "skipped",
            "reason": f"Unsupported format '{suffix}'.",
            "output": None,
        }

    # --- Skip previously generated transparent files to avoid recursion ------
    if image_path.stem.endswith(".transparent"):
        return {
            "file": str(image_path),
            "status": "skipped",
            "reason": "File is itself a generated transparent output — not reprocessed.",
            "output": None,
        }

    # --- Load image ----------------------------------------------------------
    try:
        img = Image.open(image_path)
        img.load()  # force decode
    except Exception as exc:
        return {
            "file": str(image_path),
            "status": "error",
            "reason": f"Cannot open image: {exc}",
            "output": None,
        }

    # Animated GIFs: only process the first frame but log the caveat.
    animated_note = ""
    if getattr(img, "is_animated", False):
        animated_note = " (animated GIF — only first frame processed)"
        img = img.copy()  # first frame

    # --- Already transparent? ------------------------------------------------
    if _is_already_transparent(img):
        return {
            "file": str(image_path),
            "status": "skipped",
            "reason": "Image already has a transparent background." + animated_note,
            "output": None,
        }

    # --- Check for uniform solid-colour background ---------------------------
    img_rgb = img.convert("RGB")
    arr_rgb = np.array(img_rgb)
    corner_colours = _sample_corner_colours(arr_rgb)

    if not _is_uniform_background(corner_colours):
        return {
            "file": str(image_path),
            "status": "skipped",
            "reason": (
                "Background appears complex / multi-colour (photographic or gradient). "
                "Automatic removal would risk destroying image content." + animated_note
            ),
            "output": None,
        }

    # --- Process: remove background ------------------------------------------
    try:
        result_img = remove_background(img)
    except Exception as exc:
        return {
            "file": str(image_path),
            "status": "error",
            "reason": f"Processing failed: {exc}",
            "output": None,
        }

    # --- Write output file ---------------------------------------------------
    out_name = image_path.stem + ".transparent.png"
    out_path = image_path.parent / out_name
    try:
        result_img.save(out_path, "PNG")
    except Exception as exc:
        return {
            "file": str(image_path),
            "status": "error",
            "reason": f"Could not save output: {exc}",
            "output": None,
        }

    bg_colour = _mean_background_colour(corner_colours)
    return {
        "file": str(image_path),
        "status": "processed",
        "reason": (
            f"Solid background detected (mean corner colour RGB={bg_colour.tolist()}). "
            "Background removed via flood-fill." + animated_note
        ),
        "output": str(out_path),
    }


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def find_images(root: Path) -> list[Path]:
    """Recursively find all image files under *root*, excluding .git."""
    all_ext = SUPPORTED_RASTER | SUPPORTED_VECTOR
    images = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden/git directories.
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d != "node_modules"]
        for fname in sorted(filenames):
            p = Path(dirpath) / fname
            if p.suffix.lower() in all_ext:
                images.append(p)
    return images


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _relative_or_abs(path_str: str, root: Path) -> str:
    """Return a path relative to *root* when possible, otherwise absolute."""
    try:
        return str(Path(path_str).relative_to(root))
    except ValueError:
        return path_str


def write_json_report(results: list[dict], out_path: Path, root: Path) -> None:
    rel_results = [
        {
            **r,
            "file": _relative_or_abs(r["file"], root),
            "output": _relative_or_abs(r["output"], root) if r["output"] else None,
        }
        for r in results
    ]
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"results": rel_results}, fh, ensure_ascii=False, indent=2)


def write_md_report(results: list[dict], out_path: Path, root: Path) -> None:
    results = [
        {
            **r,
            "file": _relative_or_abs(r["file"], root),
            "output": _relative_or_abs(r["output"], root) if r["output"] else None,
        }
        for r in results
    ]
    processed = [r for r in results if r["status"] == "processed"]
    skipped   = [r for r in results if r["status"] == "skipped"]
    errors    = [r for r in results if r["status"] == "error"]

    lines = [
        "# Transparentize Images — Processing Report",
        "",
        f"**Total scanned:** {len(results)}  ",
        f"**Processed:** {len(processed)}  ",
        f"**Skipped:** {len(skipped)}  ",
        f"**Errors:** {len(errors)}  ",
        "",
    ]

    if processed:
        lines += ["## ✅ Processed", ""]
        lines += ["| Original | Output |", "|---|---|"]
        for r in processed:
            lines.append(f"| `{r['file']}` | `{r['output']}` |")
        lines.append("")

    if skipped:
        lines += ["## ⏭ Skipped", ""]
        lines += ["| File | Reason |", "|---|---|"]
        for r in skipped:
            reason = r["reason"].replace("|", "\\|")
            lines.append(f"| `{r['file']}` | {reason} |")
        lines.append("")

    if errors:
        lines += ["## ❌ Errors", ""]
        lines += ["| File | Error |", "|---|---|"]
        for r in errors:
            reason = r["reason"].replace("|", "\\|")
            lines.append(f"| `{r['file']}` | {reason} |")
        lines.append("")

    lines += [
        "---",
        "_Generated by `scripts/transparentize_images.py`_",
        "",
    ]

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-remove image backgrounds; output transparent PNGs."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="Root directory to scan (default: parent of the scripts/ folder).",
    )
    args = parser.parse_args()

    # Resolve root directory.
    script_dir = Path(__file__).resolve().parent
    root = Path(args.root).resolve() if args.root else script_dir.parent

    print(f"Scanning: {root}")
    images = find_images(root)
    print(f"Found {len(images)} image file(s).")

    results = []
    for img_path in images:
        rel = img_path.relative_to(root)
        print(f"  Processing {rel} ...", end=" ", flush=True)
        result = analyse_and_process(img_path)
        results.append(result)
        print(result["status"].upper()
              + (f" → {result['output']}" if result["output"] else "")
              + f"  ({result['reason'][:80]}{'…' if len(result['reason']) > 80 else ''})")

    # Write reports.
    report_json = script_dir / "transparentize_report.json"
    report_md   = script_dir / "transparentize_report.md"
    write_json_report(results, report_json, root)
    write_md_report(results, report_md, root)
    print(f"\nReport written to:\n  {report_json}\n  {report_md}")

    processed_count = sum(1 for r in results if r["status"] == "processed")
    skipped_count   = sum(1 for r in results if r["status"] == "skipped")
    error_count     = sum(1 for r in results if r["status"] == "error")
    print(f"\nSummary: {processed_count} processed, "
          f"{skipped_count} skipped, {error_count} error(s).")


if __name__ == "__main__":
    main()
