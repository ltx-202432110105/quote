# quote

A collection of PNG assets with transparent backgrounds.

## PNG Background Removal

The script `scripts/remove_png_bg.py` automatically discovers every `*.png`
file in the repository (including sub-directories) and removes its solid or
near-solid background, keeping only the icon + text content.

### How to run

**1. Install dependencies**

```bash
pip install Pillow numpy
```

**2. Run the script**

```bash
python scripts/remove_png_bg.py
```

The script overwrites each PNG in-place with the background made transparent.
Running it multiple times is safe (idempotent): files whose corners are already
transparent are automatically skipped.

**3. Optional flags**

| Flag | Default | Description |
|------|---------|-------------|
| `--threshold INT` | `30` | Colour-distance tolerance for background detection (0–255). Increase for noisy or gradient backgrounds. |
| `--root DIR` | repo root | Directory to scan instead of the full repo. |
| `--dry-run` | off | Preview what would happen without writing any files. |

**Examples**

```bash
# Preview changes only
python scripts/remove_png_bg.py --dry-run

# More aggressive background removal
python scripts/remove_png_bg.py --threshold 50

# Process a specific sub-directory
python scripts/remove_png_bg.py --root assets/icons
```

### How it works

1. **Corner sampling** – The dominant background colour is estimated from
   small patches in all four corners of the image.
2. **Flood-fill** – A BFS flood-fill starting from each corner marks all
   connected pixels within `--threshold` colour distance as background.
3. **Edge preservation** – A 1-pixel erosion is applied to the background
   mask so that anti-aliased border pixels are kept in the foreground,
   avoiding ugly fringe artefacts.
4. **Transparency** – Background pixels have their alpha channel set to 0
   and the file is saved back as RGBA PNG.

Images whose corners disagree in colour (complex backgrounds, gradients,
photos) are left untouched and their paths are printed for manual review.
