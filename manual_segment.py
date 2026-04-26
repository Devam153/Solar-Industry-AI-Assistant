"""
Manual roof segmentation — pick the prompt pixel yourself.

Two-stage workflow:

    Stage 1: see the image and find the right pixel
    -----------------------------------------------
    python manual_segment.py "E-87, Sarita Vihar, Delhi"

    This fetches the satellite image and saves a copy with a coordinate
    grid (so you can read pixel (x, y) by eye). Look at the saved image,
    pick a pixel inside the rooftop you want segmented.

    Stage 2: segment at your chosen pixel
    -------------------------------------
    python manual_segment.py "E-87, Sarita Vihar, Delhi" 640 380

    Same address, plus the (x, y) pixel you picked. The script runs SAM
    with that point as the prompt and saves both the original image and
    the segmentation overlay.

Output files (under .cache/manual/):
    {slug}_grid.png        original image with coordinate grid (Stage 1)
    {slug}_original.png    original image, no overlay (Stage 2)
    {slug}_overlay.png     mask overlay (Stage 2)
"""

import io
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ---- bootstrap path so we can import project modules ----------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load env BEFORE importing modules that need API keys
from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from utils.image_fetch import fetch_satellite_image_complete  # noqa: E402
from components.roof_segmenter import segment_roof  # noqa: E402


CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "manual")
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_ZOOM = 21
DEFAULT_SCALE = 2  # 1280x1280 image — more detail for SAM


def _slugify(text: str) -> str:
    """Filesystem-safe filename slug."""
    keep = "abcdefghijklmnopqrstuvwxyz0123456789_"
    s = text.lower().replace(",", "").replace(" ", "_")
    return "".join(c for c in s if c in keep)[:40]


def _save_with_grid(image: Image.Image, out_path: str, step: int = 100) -> None:
    """
    Save the image with a coordinate grid overlay so the user can read off
    pixel (x, y) by eye. Grid lines every `step` pixels, labeled at the
    top and left edges.
    """
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    # Grid lines — semi-transparent yellow drawn directly on the RGB image
    grid_color = (255, 235, 59)
    for x in range(step, w, step):
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
        draw.text((x + 2, 2), str(x), fill=grid_color, font=font)
    for y in range(step, h, step):
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)
        draw.text((2, y + 2), str(y), fill=grid_color, font=font)

    # Center crosshair (the SAM default if no point is given)
    cx, cy = w // 2, h // 2
    draw.line([(cx - 12, cy), (cx + 12, cy)], fill=(255, 0, 0), width=2)
    draw.line([(cx, cy - 12), (cx, cy + 12)], fill=(255, 0, 0), width=2)
    draw.text((cx + 14, cy + 4), f"center ({cx},{cy})", fill=(255, 0, 0), font=font)

    canvas.save(out_path)


def _save_overlay(image: Image.Image, mask: np.ndarray, point: tuple[int, int], out_path: str) -> None:
    """Save the satellite image with mask painted green and the prompt point marked."""
    arr = np.array(image.convert("RGB"))
    arr[mask] = (0.5 * arr[mask] + 0.5 * np.array([0, 255, 0])).astype(np.uint8)
    overlay = Image.fromarray(arr)

    draw = ImageDraw.Draw(overlay)
    px, py = point
    draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline=(255, 0, 0), width=2)
    draw.line([(px - 10, py), (px + 10, py)], fill=(255, 0, 0), width=2)
    draw.line([(px, py - 10), (px, py + 10)], fill=(255, 0, 0), width=2)

    overlay.save(out_path)


def stage1_show_grid(address: str) -> None:
    """Stage 1: fetch + save image with coordinate grid for inspection."""
    print(f"[stage 1] fetching satellite image for: {address}")
    res = fetch_satellite_image_complete(
        address=address,
        zoom=DEFAULT_ZOOM,
        scale=DEFAULT_SCALE,
    )
    if "error" in res:
        print(f"  fetch failed: {res['error']}")
        sys.exit(1)

    print(f"  geocoded: {res['formatted_address']}")
    print(f"  coords:   {res['coordinates']}")
    img = Image.open(io.BytesIO(res["image_data"]))
    print(f"  dims:     {img.size}")

    slug = _slugify(address)
    grid_path = os.path.join(CACHE_DIR, f"{slug}_grid.png")
    _save_with_grid(img, grid_path)

    print()
    print(f"saved with coord grid: {grid_path}")
    print()
    print("Open that image, pick a pixel INSIDE the rooftop you want")
    print("segmented (read off the (x, y) from the yellow grid labels), then run:")
    print()
    print(f'    python manual_segment.py "{address}" <x> <y>')
    print()


def stage2_segment(address: str, x: int, y: int) -> None:
    """Stage 2: segment using the user-provided prompt pixel."""
    print(f"[stage 2] fetching satellite image for: {address}")
    res = fetch_satellite_image_complete(
        address=address,
        zoom=DEFAULT_ZOOM,
        scale=DEFAULT_SCALE,
    )
    if "error" in res:
        print(f"  fetch failed: {res['error']}")
        sys.exit(1)

    img = Image.open(io.BytesIO(res["image_data"]))
    w, h = img.size
    if not (0 <= x < w and 0 <= y < h):
        print(f"  ERROR: pixel ({x}, {y}) is outside image bounds {w}x{h}")
        sys.exit(1)

    print(f"  geocoded:     {res['formatted_address']}")
    print(f"  coords:       {res['coordinates']}")
    print(f"  image dims:   {w} x {h}")
    print(f"  prompt point: ({x}, {y})")
    print()
    print("[stage 2] running MobileSAM segmentation at your prompt point...")

    result = segment_roof(
        res["image_data"],
        lat=res["coordinates"]["lat"],
        zoom=DEFAULT_ZOOM,
        scale=DEFAULT_SCALE,
        prompt_point=(x, y),
        debug=True,
    )

    print()
    print("=" * 60)
    print(f"RESULT for {address}  @  ({x}, {y})")
    print("=" * 60)
    print(f"  Roof area:    {result['area_sqft']:,.0f} sq ft "
          f"({result['area_m2']:,.1f} m^2)")
    print(f"  Pixels:       {result['pixel_count']:,}")
    print(f"  m/pixel:      {result['m_per_pixel']}")
    print(f"  Confidence:   {result['score']}")

    slug = _slugify(address)
    original_path = os.path.join(CACHE_DIR, f"{slug}_original.png")
    overlay_path = os.path.join(CACHE_DIR, f"{slug}_overlay.png")

    img.convert("RGB").save(original_path)
    _save_overlay(img, result["mask"], (x, y), overlay_path)

    print()
    print(f"saved:")
    print(f"  original: {original_path}")
    print(f"  overlay:  {overlay_path}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    address = sys.argv[1]

    if len(sys.argv) == 2:
        stage1_show_grid(address)
    elif len(sys.argv) == 4:
        try:
            x = int(sys.argv[2])
            y = int(sys.argv[3])
        except ValueError:
            print("ERROR: x and y must be integers.")
            sys.exit(1)
        stage2_segment(address, x, y)
    else:
        print('Usage:')
        print('  python manual_segment.py "<address>"           # Stage 1: see grid')
        print('  python manual_segment.py "<address>" <x> <y>   # Stage 2: segment at point')
        sys.exit(1)


if __name__ == "__main__":
    main()
