# quote

Visual assets repository for PPT / presentation materials.

## Image Assets

| File | Description |
|---|---|
| `Redis_Logo.png` | Redis logo (RGBA, transparent background) |

---

## Batch Background Removal

The script `scripts/transparentize_images.py` scans the repository for image
files and removes solid-colour backgrounds, producing transparent PNG versions
suitable for use in PowerPoint / Keynote slides.

### What it does

- **Scans** the repository for `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, and
  `.svg` files recursively.
- **Skips** files that already have a transparent background.
- **Processes** files with a detectable solid/near-solid colour background
  (black, white, grey, or any other uniform corner colour) by flood-filling
  the background area and replacing it with transparency.
- **Skips** complex/photographic/gradient backgrounds (logs the reason).
- **Outputs** `<original_name>.transparent.png` beside each processed image —
  the original file is never modified.
- **Generates** a machine-readable report at
  `scripts/transparentize_report.json` and a human-readable summary at
  `scripts/transparentize_report.md`.

### Dependencies

```bash
pip install Pillow numpy
```

### Usage

```bash
# Process the entire repository (run from the repo root):
python scripts/transparentize_images.py

# Process a specific directory:
python scripts/transparentize_images.py path/to/directory
```

### Output example

```
Scanning: /path/to/repo
Found 3 image file(s).
  Processing assets/icon.png ...   PROCESSED → assets/icon.transparent.png
  Processing assets/photo.jpg ...  SKIPPED  (complex background)
  Processing assets/logo.png ...   SKIPPED  (already transparent)

Report written to:
  scripts/transparentize_report.json
  scripts/transparentize_report.md

Summary: 1 processed, 2 skipped, 0 error(s).
```

> **Note:** The generated `.transparent.png` files are ideal for
> inserting into PowerPoint slides — place them on any coloured slide
> background without a visible rectangle around the image.
