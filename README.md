# Go Logo Assets

## Source image

`488581-20230904123211637-1775692153.png` – Go language logo / Gopher image (original, black background).

## Transparent version

`488581-20230904123211637-1775692153.transparent.png` – Same image with black background and outer page background removed; RGBA, transparent PNG suitable for PPT.

## Reproducing the transparent image

Install dependencies and run the processing script:

```bash
pip install Pillow numpy scipy
python scripts/make_go_logo_transparent.py
```

Custom paths:

```bash
python scripts/make_go_logo_transparent.py \
    --input  488581-20230904123211637-1775692153.png \
    --output 488581-20230904123211637-1775692153.transparent.png
```

### Processing strategy

1. **Outer white background removal** – flood-fill from image borders over connected near-white pixels (all channels ≥ 220) to detect the page background, then set those pixels to fully transparent.  
2. **Inner black background removal** – colour threshold (all channels ≤ 55) removes the dark logo background.  
3. **Anti-aliasing** – a 3-pixel-wide Euclidean-distance-based alpha transition zone smooths the content edges so there are no hard jagged borders or black fringes.  
4. **Output** – 32-bit RGBA PNG at the same pixel dimensions as the source (1702 × 926 px).
