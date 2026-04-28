# quote

A collection of icon images for PPT / presentation use, with transparent-background versions for each icon.

## Images

| Original file | Transparent version |
|---|---|
| `488581-20230904123211637-1775692153.png` | `488581-20230904123211637-1775692153.transparent.png` |
| `OIP-C (1).webp` | `OIP-C (1).transparent.png` |
| `OIP-C (2).webp` | `OIP-C (2).transparent.png` |
| `OIP-C.webp` | `OIP-C.transparent.png` |
| `ee9b6b2024f01047.webp` | `ee9b6b2024f01047.transparent.png` |

All `*.transparent.png` files are RGBA PNGs with the solid background removed — ready to drop into any PPT slide.

---

## Batch background-removal script

`scripts/make_all_icons_transparent.py` scans the repository for icon images and generates a `.transparent.png` version for each one that has a detectable solid-colour background.

### Dependencies

```bash
pip install Pillow numpy
```

### Usage

```bash
# From the repo root — processes all images under the current directory:
python scripts/make_all_icons_transparent.py

# Scan a specific subdirectory only:
python scripts/make_all_icons_transparent.py --dir assets/icons

# Preview what would happen without writing any files:
python scripts/make_all_icons_transparent.py --dry-run
```

### How it works

1. **Scans** for `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` files (skips already-generated `.transparent.png` files).
2. **Checks for existing transparency** — images that already have ≥ 5 % transparent pixels are skipped.
3. **Corner sampling** — measures the colour variance in the four corner blocks of the image.  
   If all corners agree on a near-uniform colour, that colour is treated as the background.
4. **Background removal** — pixels within a colour-distance tolerance of the background colour are made transparent; a soft alpha ramp on the transition zone removes anti-aliased fringe pixels cleanly.
5. **Saves** `<original_stem>.transparent.png` alongside the source file.  
   The original is **never overwritten**.

Images with non-uniform corners (complex photos, gradients) are skipped automatically and listed in the output with a reason.
