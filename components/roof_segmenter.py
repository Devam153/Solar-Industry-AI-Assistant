"""
MobileSAM-based roof segmenter.

Replaces Gemini's hallucinated roof coordinates with a pixel-accurate binary
mask from Meta's Segment Anything Model. 
Converts pixel count to ground-area square feet 
using Google Web Mercator's known meters-per-pixel formula 
at the request's zoom level (with cosine correction for latitude).

Public API:
    segment_roof(image_bytes, lat, zoom=21, prompt_point=None) -> dict

Returns dict with:
    mask          (H,W) bool numpy array
    area_sqft     float
    area_m2       float
    pixel_count   int
    m_per_pixel   float
    score         float (SAM confidence, 0..1)
"""

import io # reads image bytes as a stream
import math
import os
import sys
import urllib.request

import cv2
import numpy as np
from PIL import Image # decodes png bytes into an array


# ---- weights handling ------------------------------------------------------
WEIGHTS_URL = (
    "https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt"
)
WEIGHTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "models"
)
WEIGHTS_PATH = os.path.join(WEIGHTS_DIR, "mobile_sam.pt")


def _ensure_weights() -> str:
    """Download MobileSAM weights on first use."""
    if os.path.exists(WEIGHTS_PATH):
        return WEIGHTS_PATH

    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    print(f"[roof_segmenter] downloading MobileSAM weights to {WEIGHTS_PATH}")
    urllib.request.urlretrieve(WEIGHTS_URL, WEIGHTS_PATH)
    print("[roof_segmenter] download complete.")
    return WEIGHTS_PATH


# ---- model singleton -------------------------------------------------------
_PREDICTOR = None


def _get_predictor():
    """Lazy-load MobileSAM and cache the predictor at module level."""
    '''Loading SAM is slow, about 2 seconds on a cold start. We don't want to pay that cost on every segment_roof() call. So we load once and keep the loaded predictor in module-level memory.'''

    global _PREDICTOR
    if _PREDICTOR is not None: # stays loaded after one time 
        return _PREDICTOR

    import torch
    from mobile_sam import sam_model_registry, SamPredictor

    weights_path = _ensure_weights()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = sam_model_registry["vit_t"](checkpoint=weights_path)
    # Tiny ViT-thats MobileSAM's encoder
    model.to(device=device)
    model.eval()

    _PREDICTOR = SamPredictor(model)
    return _PREDICTOR


# ---- geometry --------------------------------------------------------------
EQUATOR_M_PER_PX_AT_ZOOM_0 = 156543.03392


def _meters_per_pixel(lat: float, zoom: int, scale: int = 1) -> float:
    """
    Web Mercator meters-per-pixel at the given latitude/zoom/scale.

    Google Static Maps with scale=2 doubles pixel density at the same
    zoom (1280x1280 for size=640), so m_per_px halves.

    Formula: 156543.03 * cos(lat) / (2^zoom * scale)
    """
    return EQUATOR_M_PER_PX_AT_ZOOM_0 * math.cos(math.radians(lat)) / (2 ** zoom * scale)


def _pixels_to_sqft(pixel_count: int, lat: float, zoom: int, scale: int = 1) -> tuple[float, float]:
    """Convert mask pixel count to (sq meters, sq feet) on the ground."""
    m_per_px = _meters_per_pixel(lat, zoom, scale)
    area_m2 = pixel_count * (m_per_px ** 2)
    area_sqft = area_m2 * 10.7639
    return area_m2, area_sqft


# ---- mask picker -----------------------------------------------------------
# Plausible roof-mask size relative to the frame. A residential rooftop at
# zoom 21 typically occupies 4-30% of the frame; commercial roofs up to 50%.
# Anything > 60% is almost certainly "the whole neighborhood + roads merged."
MIN_MASK_FRAC = 0.02
MAX_MASK_FRAC = 0.60


def _pick_best_mask(
    masks: np.ndarray,
    scores: np.ndarray,
    prompt_point: tuple[int, int],
    image_size: tuple[int, int],
) -> tuple[np.ndarray, float]:
    """
    Pick the most plausible roof mask from SAM's 3 candidates.

    Heuristics:
      - must contain the prompt point (foreground)
      - prefer masks within MIN..MAX fraction of frame
      - tiebreaker: highest SAM confidence in range
    """
    h, w = image_size
    px, py = prompt_point
    total_pixels = h * w

    candidates = []
    for i, (mask, score) in enumerate(zip(masks, scores)):
        if not mask[py, px]:
            continue
        frac = mask.sum() / total_pixels
        in_range = MIN_MASK_FRAC <= frac <= MAX_MASK_FRAC
        candidates.append((i, mask, float(score), float(frac), in_range))

    if not candidates:
        i = int(np.argmax(scores))
        return masks[i], float(scores[i])

    # Prefer in-range masks; among those, pick the highest-confidence one.
    # SAM's score correlates with mask quality — for multi-level Indian
    # rooftops the larger (and higher-scored) mask usually captures the
    # full building, while the smaller one captures just one flat-roof
    # section.
    in_range = [c for c in candidates if c[4]]
    if in_range:
        in_range.sort(key=lambda c: c[2], reverse=True)  # highest score first
        _, mask, score, _, _ = in_range[0]
        return mask, score

    # Fall back: of the out-of-range candidates, prefer the smallest
    # (avoids "everything merged into one giant blob" failure mode).
    candidates.sort(key=lambda c: c[3])
    _, mask, score, _, _ = candidates[0]
    return mask, score


# ---- shadow removal --------------------------------------------------------
def _remove_shadow(
    image_rgb: np.ndarray,
    mask: np.ndarray,
    prompt_point: tuple[int, int],
    brightness_ratio: float = 0.65,
    sample_radius: int = 25,
    open_kernel: int = 7,
) -> np.ndarray:
    """
    Strip building-shadow regions out of a SAM mask.

    Why we need this: SAM treats a building and its cast shadow as one
    connected "object" because the shadow is dark, attached to the building,
    and visually similar to neighboring shaded ground. We use the prompt
    point's local brightness as the reference for "what a roof looks like"
    and discard any masked pixel that is significantly darker.

    Steps:
      1. Sample HSV "value" channel in a small patch around the prompt point.
      2. Compute reference brightness (median of patch).
      3. Mark mask pixels below brightness_ratio * reference as shadow.
      4. Morphological opening to break narrow shadow tails.
      5. Keep only the connected component containing the prompt point.
    """
    px, py = prompt_point
    h, w = image_rgb.shape[:2]

    # 1. convert to HSV
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    v = hsv[..., 2]

    y0 = max(0, py - sample_radius)
    y1 = min(h, py + sample_radius)
    x0 = max(0, px - sample_radius)
    x1 = min(w, px + sample_radius)
    ref_v = float(np.median(v[y0:y1, x0:x1]))

    # 2. Threshold: drop pixels significantly darker than reference.
    bright_enough = v >= (ref_v * brightness_ratio)
    refined = mask & bright_enough

    # 3. Morphological opening — removes thin shadow "tails" hanging off
    #    the roof while preserving solid roof body.
    refined_u8 = refined.astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_kernel, open_kernel))
    refined_u8 = cv2.morphologyEx(refined_u8, cv2.MORPH_OPEN, kernel)

    # 4. Keep only the connected component that contains the prompt point.
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(refined_u8, connectivity=8)
    if n_labels > 1:
        prompt_label = int(labels[py, px])
        if prompt_label > 0:
            refined_u8 = (labels == prompt_label).astype(np.uint8)
        else:
            # Prompt point fell on a hole — keep the largest non-background blob
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            refined_u8 = (labels == largest).astype(np.uint8)

    return refined_u8.astype(bool)


# main
def segment_roof(
    image_bytes: bytes,
    lat: float,
    zoom: int = 21,
    scale: int = 1,
    prompt_point: tuple[int, int] | None = None,
    use_box_prompt: bool = True,
    box_fraction: float = 0.50,
    remove_shadows: bool = True,
    shadow_brightness_ratio: float = 0.65,
    debug: bool = False,
) -> dict:
    """
    Segment the roof in a satellite image and compute its ground area.

    Parameters
    ----------
    image_bytes : raw PNG/JPEG bytes (e.g. from Google Static Maps).
    lat : latitude of the image center (degrees, for Mercator scale).
    zoom : Google Maps zoom level the image was fetched at.
    prompt_point : (x, y) pixel for the SAM point prompt. Defaults to center.
    use_box_prompt : if True, also pass a bounding box around the prompt
        point. A box prompt biases SAM toward "the dominant object inside
        this rectangle" — much more reliable than a point alone in dense
        urban scenes.
    box_size : side length of the box prompt (pixels). 240 fits a typical
        residential roof in a 640x640 zoom-21 image.

    Returns
    -------
    dict with keys: mask, area_sqft, area_m2, pixel_count, m_per_pixel, score
    """
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = np.array(pil_img)
    h, w = image.shape[:2]

    # default prompt poin to the center 
    if prompt_point is None:
        prompt_point = (w // 2, h // 2)
    px, py = int(prompt_point[0]), int(prompt_point[1])
    prompt_point = (px, py)

    predictor = _get_predictor()
    predictor.set_image(image)

    point_coords = np.array([prompt_point], dtype=np.float32)
    point_labels = np.array([1], dtype=np.int32)

    box = None
    if use_box_prompt:
        # Box is sized as a fraction of the smaller image dimension so it
        # scales correctly for both 640x640 (scale=1) and 1280x1280 (scale=2)
        # images. 0.50 covers the full center half — generous enough for
        # large residential roofs without grabbing the whole frame.
        half = int(min(h, w) * box_fraction / 2)
        box = np.array(
            [[
                max(0, px - half),
                max(0, py - half),
                min(w, px + half),
                min(h, py + half),
            ]],
            dtype=np.float32,
        )

    masks, scores, _ = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        box=box,
        multimask_output=True,
    )

    if debug:
        total = h * w
        print("[roof_segmenter] SAM returned 3 candidate masks:")
        for i, (m, s) in enumerate(zip(masks, scores)):
            frac = m.sum() / total
            print(f"  mask {i}: {m.sum():,} px ({frac*100:.1f}% of frame), score={s:.3f}")

    mask, score = _pick_best_mask(masks, scores, prompt_point, (h, w))

    raw_pixel_count = int(mask.sum())

    if remove_shadows:
        mask = _remove_shadow(
            image,
            mask,
            prompt_point,
            brightness_ratio=shadow_brightness_ratio,
        )
        if debug:
            removed = raw_pixel_count - int(mask.sum())
            pct = removed / max(raw_pixel_count, 1) * 100
            print(f"[roof_segmenter] shadow removal: dropped {removed:,} px "
                  f"({pct:.1f}% of raw mask)")

    pixel_count = int(mask.sum())
    area_m2, area_sqft = _pixels_to_sqft(pixel_count, lat, zoom, scale)
    m_per_px = _meters_per_pixel(lat, zoom, scale)

    return {
        "mask": mask.astype(bool),
        "area_sqft": round(area_sqft, 1),
        "area_m2": round(area_m2, 2),
        "pixel_count": pixel_count,
        "raw_pixel_count": raw_pixel_count,
        "m_per_pixel": round(m_per_px, 4),
        "score": round(score, 3),
        "image_shape": (h, w),
        "prompt_point": prompt_point,
        "used_box_prompt": use_box_prompt,
        "shadow_removed": remove_shadows,
        "scale": scale,
    }


# ---- smoke test ------------------------------------------------------------
if __name__ == "__main__":
    # Allow running directly: python components/roof_segmenter.py
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    from utils.image_fetch import fetch_satellite_image_complete

    address = "FF21-HBR, HBR layout"
    zoom = 21
    scale = 2  # 2x pixel density at zoom 21 = double the detail for SAM

    print(f"\n{'=' * 60}")
    print(f"TEST: {address}  (zoom={zoom}, scale={scale})")
    print("=" * 60)
    res = fetch_satellite_image_complete(address=address, zoom=zoom, scale=scale)
    if "error" in res:
        print(f"image fetch failed: {res['error']}")
        sys.exit(1)

    print(f"  Geocoded: {res['formatted_address']}")
    print(f"  Coords:   {res['coordinates']}")
    print(f"  Bytes:    {res['image_size_bytes']:,}")

    result = segment_roof(
        res["image_data"],
        lat=res["coordinates"]["lat"],
        zoom=zoom,
        scale=scale,
        debug=True,
    )

    print(f"\nResults:")
    print(f"  Image dims:   {result['image_shape']}")
    print(f"  Roof area:    {result['area_sqft']:,.0f} sq ft ({result['area_m2']:,.1f} m^2)")
    print(f"  Pixels:       {result['pixel_count']:,}")
    print(f"  m/pixel:      {result['m_per_pixel']}")
    print(f"  Confidence:   {result['score']}")

    # Save the original image AND the overlay so the user can see both.
    cache_dir = os.path.join(WEIGHTS_DIR, "..")
    original_path = os.path.join(cache_dir, "sarita_vihar_original.png")
    overlay_path = os.path.join(cache_dir, "sarita_vihar_overlay.png")

    Image.open(io.BytesIO(res["image_data"])).convert("RGB").save(original_path)

    overlay_arr = np.array(Image.open(io.BytesIO(res["image_data"])).convert("RGB"))
    overlay_arr[result["mask"]] = (
        0.5 * overlay_arr[result["mask"]] + 0.5 * np.array([0, 255, 0])
    ).astype(np.uint8)
    Image.fromarray(overlay_arr).save(overlay_path)

    print(f"\nSaved:")
    print(f"  Original:     {original_path}")
    print(f"  Overlay:      {overlay_path}")
