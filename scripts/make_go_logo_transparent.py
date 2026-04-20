"""
make_go_logo_transparent.py
----------------------------
Remove the black (and outer-white page) background from the Go language
logo/gopher PNG, producing a transparent-background PNG suitable for PPT.

Strategy
--------
1. Detect the outer white page background via flood-fill from image
   borders (connected-components on near-white pixels).
2. Detect remaining near-black logo-background pixels by colour threshold.
3. Combine both masks to build a "background" mask.
4. Compute the Euclidean distance from each pixel to the nearest background
   pixel and use that distance to build a smooth alpha channel
   (edge_px-wide anti-alias zone so there are no hard jagged edges).
5. Save the result as a 32-bit RGBA PNG without changing image dimensions.

Usage
-----
    # Default: process the Go logo in the repo root
    python scripts/make_go_logo_transparent.py

    # Custom paths
    python scripts/make_go_logo_transparent.py \
        --input  488581-20230904123211637-1775692153.png \
        --output 488581-20230904123211637-1775692153.transparent.png

Dependencies
------------
    pip install Pillow numpy scipy
    # or, if a requirements.txt is present:
    pip install -r requirements.txt
"""

import argparse
import pathlib

import numpy as np
from PIL import Image
from scipy import ndimage


# ---------------------------------------------------------------------------
# Tuneable parameters
# ---------------------------------------------------------------------------
# Minimum channel value (0-255) for a pixel to be considered "white/light".
# Pixels with ALL channels >= this threshold AND belonging to the flood-filled
# outer background region are treated as background.
WHITE_THRESHOLD = 220

# Maximum channel value (0-255) for a pixel to be considered "near-black".
# Pixels with ALL channels <= this threshold are treated as black background.
BLACK_THRESHOLD = 55

# Half-width (pixels) of the anti-aliasing transition zone at mask edges.
EDGE_PX = 3


def remove_background(input_path: str, output_path: str) -> None:
    """Process *input_path* and write a transparent PNG to *output_path*."""

    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)       # shape (H, W, 4)

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # ------------------------------------------------------------------
    # Step 1 – outer white / light-grey page background (flood fill)
    # ------------------------------------------------------------------
    # A pixel is "light" if every channel is at least WHITE_THRESHOLD.
    is_light = (r >= WHITE_THRESHOLD) & (g >= WHITE_THRESHOLD) & (b >= WHITE_THRESHOLD)

    # Label connected regions of light pixels.
    structure = np.ones((3, 3), dtype=int)          # 8-connectivity
    labeled, _ = ndimage.label(is_light, structure=structure)

    # Any label that touches an image border belongs to the outer background.
    h, w = arr.shape[:2]
    border_labels: set[int] = set()
    border_labels.update(labeled[0, :].tolist())
    border_labels.update(labeled[-1, :].tolist())
    border_labels.update(labeled[:, 0].tolist())
    border_labels.update(labeled[:, -1].tolist())
    border_labels.discard(0)                        # 0 = non-light regions

    outer_bg_mask = np.isin(labeled, list(border_labels))

    # ------------------------------------------------------------------
    # Step 2 – near-black logo background (colour threshold)
    # ------------------------------------------------------------------
    black_mask = (r <= BLACK_THRESHOLD) & (g <= BLACK_THRESHOLD) & (b <= BLACK_THRESHOLD)

    # ------------------------------------------------------------------
    # Step 3 – combined background mask
    # ------------------------------------------------------------------
    bg_mask = outer_bg_mask | black_mask            # True = background

    # ------------------------------------------------------------------
    # Step 4 – smooth alpha via distance transform (anti-aliasing)
    # ------------------------------------------------------------------
    # distance_transform_edt(~bg_mask) gives, for every pixel, the
    # Euclidean distance to the nearest background pixel.
    #   - background pixels              → distance = 0  → alpha = 0
    #   - content pixels at the border   → distance ≈ 1  → alpha small
    #   - content pixels deep inside     → distance ≥ EDGE_PX → alpha = 255
    dist = ndimage.distance_transform_edt(~bg_mask)
    alpha = np.clip(dist / EDGE_PX * 255.0, 0.0, 255.0)

    # ------------------------------------------------------------------
    # Step 5 – write output
    # ------------------------------------------------------------------
    result = arr.copy()
    result[:, :, 3] = alpha
    Image.fromarray(result.astype(np.uint8), "RGBA").save(output_path)
    print(f"Saved transparent image → {output_path}")


def main() -> None:
    repo_root = pathlib.Path(__file__).parent.parent
    default_input = repo_root / "488581-20230904123211637-1775692153.png"
    default_output = repo_root / "488581-20230904123211637-1775692153.transparent.png"

    parser = argparse.ArgumentParser(
        description="Remove black/white background from the Go logo PNG."
    )
    parser.add_argument(
        "--input", default=str(default_input),
        help="Source PNG path (default: %(default)s)"
    )
    parser.add_argument(
        "--output", default=str(default_output),
        help="Output transparent PNG path (default: %(default)s)"
    )
    args = parser.parse_args()

    remove_background(args.input, args.output)


if __name__ == "__main__":
    main()
