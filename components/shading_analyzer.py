"""
Shading analyzer — per-pixel annual shade map for a rooftop.

For every roof pixel, computes how many hours per year it is in the shadow
of an obstacle (water tank, AC unit, stair-room, parapet) given the sun's
position throughout the year.

Pipeline:
    1. Detect obstacles inside the roof mask via brightness thresholding.
    2. Get hourly sun positions for the year via pvlib.
    3. Bin sun positions by azimuth (36 bins x 10 deg each) — collapses
       ~4000 ray casts into ~100 representative ones.
    4. For each populated bin, cast a shadow from every obstacle pixel in
       the direction opposite the sun and accumulate weighted hours.
    5. Aggregate to per-pixel shade hours, shade fraction, and a "usable"
       mask (low-shade roof pixels suitable for panels).

Public API:
    analyze_shading(image_bytes, roof_mask, lat, lng, m_per_pixel, ...) -> dict

Returns dict with:
    shade_hours_map       (H,W) float — annual shaded hours per pixel
    shade_fraction_map    (H,W) float — 0..1 per pixel
    obstacle_mask         (H,W) bool  — detected obstacles on the roof
    usable_mask           (H,W) bool  — roof_mask AND shade_fraction < threshold
    avg_shade_pct         float       — mean shade across all roof pixels
    usable_area_sqft      float       — total panel-ready area
    n_daylight_hours      int         — hours used in the simulation
"""

import io
import math
import os

# Workaround for a known Windows DLL conflict: pvlib/scipy and torch both
# carry their own OpenMP runtime; loading both in the same process trips
# Windows' duplicate-library check. Enabling this flag is the documented
# escape hatch from Intel's MKL team.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Pre-load torch BEFORE any scientific stack so its DLLs win the race.
# Harmless when torch is unused; required when we chain segmenter -> shading.
try:
    import torch  # noqa: F401
except Exception:
    pass

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from pvlib import solarposition


# ---- obstacle detection ----------------------------------------------------
def _detect_obstacles(
    image_rgb: np.ndarray,
    roof_mask: np.ndarray,
    dark_percentile: float = 10.0,
    morph_kernel: int = 7,
) -> np.ndarray:
    """
    Find on-roof obstacles by spotting the darkest 15-20% of roof pixels.

    Why percentile, not a fixed brightness ratio: rooftops vary widely in
    base color (white-painted, beige concrete, dark tile, weathered grey).
    A fixed ratio under-detects on dark roofs and over-detects on bright
    ones. Percentile auto-adapts.

    Captures water tanks, AC units, stair-rooms, vents, and on-roof
    shadows from parapets — anything that's noticeably darker than the
    surrounding roof surface.

    Returns a bool mask of obstacle pixels (subset of roof_mask).
    """
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    v = hsv[..., 2]

    roof_v = v[roof_mask]
    if roof_v.size == 0:
        return np.zeros_like(roof_mask, dtype=bool)

    threshold_v = float(np.percentile(roof_v, dark_percentile))
    dark = (v < threshold_v) & roof_mask

    # Morph open then close: drops salt-noise, fills small holes.
    dark_u8 = dark.astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_kernel, morph_kernel))
    dark_u8 = cv2.morphologyEx(dark_u8, cv2.MORPH_OPEN, kernel)
    dark_u8 = cv2.morphologyEx(dark_u8, cv2.MORPH_CLOSE, kernel)

    return dark_u8.astype(bool)


# ---- sun-path utilities ----------------------------------------------------
def _get_daylight_sun_positions(
    lat: float,
    lng: float,
    year: int,
    elevation_min_deg: float = 5.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (azimuth_array, elevation_array) for every daylight hour of the
    given year at this location. Elevations below 5 deg are dropped — sun
    that low is contributing negligible energy.
    """
    times = pd.date_range(
        start=f"{year}-01-01",
        end=f"{year}-12-31 23:00",
        freq="1h",
        tz="UTC",
    )
    solpos = solarposition.get_solarposition(times, lat, lng)

    daylight = solpos["apparent_elevation"] > elevation_min_deg
    az = solpos.loc[daylight, "azimuth"].to_numpy()
    el = solpos.loc[daylight, "apparent_elevation"].to_numpy()
    return az, el


def _bin_by_azimuth(
    sun_az: np.ndarray,
    sun_el: np.ndarray,
    az_bin_deg: int,
) -> list[tuple[float, float, int]]:
    """
    Group sun positions by azimuth bin. For each populated bin, return
    (mean_azimuth, mean_elevation, n_hours).
    """
    bin_idx = (sun_az / az_bin_deg).astype(int)
    bins: list[tuple[float, float, int]] = []
    for b in np.unique(bin_idx):
        in_bin = bin_idx == b
        bins.append((
            float(sun_az[in_bin].mean()),
            float(sun_el[in_bin].mean()),
            int(in_bin.sum()),
        ))
    return bins


# ---- shadow casting --------------------------------------------------------
def _cast_shadow_from_obstacles(
    obstacles: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    obstacle_height_m: float,
    m_per_pixel: float,
) -> np.ndarray:
    """
    Project shadows from every obstacle pixel for the given sun position.

    Geometry:
        shadow_length_m  = obstacle_height / tan(elevation)
        shadow_length_px = shadow_length_m / m_per_pixel
        shadow_direction = (sun_azimuth + 180) % 360   # opposite the sun

    Image coordinates:
        +x = east, +y = south (image y points DOWN)
        dx_step =  sin(shadow_az_rad)
        dy_step = -cos(shadow_az_rad)   # north points to negative y

    Returns a bool mask of shadow pixels for this sun position.
    """
    el_rad = math.radians(max(sun_elevation_deg, 1e-3))  # guard div by 0
    shadow_len_m = obstacle_height_m / math.tan(el_rad)
    shadow_len_px = int(round(shadow_len_m / m_per_pixel))
    if shadow_len_px < 1:
        return np.zeros_like(obstacles, dtype=bool)

    shadow_az = (sun_azimuth_deg + 180.0) % 360.0
    shadow_az_rad = math.radians(shadow_az)
    dx_step = math.sin(shadow_az_rad)
    dy_step = -math.cos(shadow_az_rad)

    shadow = np.zeros_like(obstacles, dtype=bool)
    for step in range(1, shadow_len_px + 1):
        ox = int(round(step * dx_step))
        oy = int(round(step * dy_step))
        shifted = np.roll(obstacles, shift=(oy, ox), axis=(0, 1))
        shadow |= shifted

    return shadow


# ---- main API --------------------------------------------------------------
def analyze_shading(
    image_bytes: bytes,
    roof_mask: np.ndarray,
    lat: float,
    lng: float,
    m_per_pixel: float,
    year: int = 2025,
    obstacle_height_m: float = 1.5,
    az_bin_deg: int = 10,
    obstacle_dark_percentile: float = 10.0,
    usable_shade_threshold: float = 0.10,
    debug: bool = False,
) -> dict:
    """
    Compute a per-pixel annual shade map for the rooftop.

    Parameters
    ----------
    image_bytes : raw PNG/JPEG bytes (same image used for segmentation).
    roof_mask : (H, W) bool — output of components.roof_segmenter.
    lat, lng : site coordinates (degrees).
    m_per_pixel : ground meters per image pixel (from segmenter result).
    year : reference year for the sun-path simulation.
    obstacle_height_m : assumed uniform obstacle height (m). 2.5 m is a
        reasonable median for Indian residential water tanks + AC units.
    az_bin_deg : azimuth bin size for sun-path grouping. 10 deg = 36 bins.
    obstacle_dark_threshold : how dark vs the roof median counts as obstacle.
    usable_shade_threshold : pixels with shade fraction below this are
        considered usable for panels (industry norm: 10%).

    Returns
    -------
    dict with keys: shade_hours_map, shade_fraction_map, obstacle_mask,
    usable_mask, avg_shade_pct, usable_area_sqft, n_daylight_hours.
    """
    image = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    h, w = image.shape[:2]

    # 1. Detect obstacles inside the roof mask.
    obstacles = _detect_obstacles(
        image, roof_mask, dark_percentile=obstacle_dark_percentile
    )
    if debug:
        n_obstacle_px = int(obstacles.sum())
        n_roof_px = int(roof_mask.sum())
        pct = n_obstacle_px / max(n_roof_px, 1) * 100
        print(f"[shading_analyzer] detected {n_obstacle_px:,} obstacle px "
              f"({pct:.1f}% of roof)")

    # 2. Get sun positions for daylight hours of the year.
    sun_az, sun_el = _get_daylight_sun_positions(lat, lng, year)
    n_daylight = int(len(sun_az))

    # 3. Bin sun positions by azimuth.
    bins = _bin_by_azimuth(sun_az, sun_el, az_bin_deg)
    if debug:
        print(f"[shading_analyzer] {n_daylight} daylight hours -> "
              f"{len(bins)} populated azimuth bins")

    # 4. For each bin, cast shadows from obstacles and accumulate hours.
    shade_hours = np.zeros((h, w), dtype=np.float32)
    for avg_az, avg_el, n_hours in bins:
        shadow = _cast_shadow_from_obstacles(
            obstacles, avg_az, avg_el, obstacle_height_m, m_per_pixel
        )
        shade_hours += (shadow & roof_mask).astype(np.float32) * n_hours

    # 5. Aggregate.
    shade_fraction = shade_hours / max(n_daylight, 1)
    shade_fraction = shade_fraction * roof_mask.astype(np.float32)

    usable_mask = roof_mask & (shade_fraction < usable_shade_threshold)

    roof_pixels_only = shade_fraction[roof_mask]
    avg_shade_pct = float(roof_pixels_only.mean()) * 100 if roof_pixels_only.size else 0.0

    usable_area_m2 = int(usable_mask.sum()) * (m_per_pixel ** 2)
    usable_area_sqft = usable_area_m2 * 10.7639

    if debug:
        print(f"[shading_analyzer] avg shade across roof: {avg_shade_pct:.1f}%")
        print(f"[shading_analyzer] usable area (< {usable_shade_threshold*100:.0f}% shade): "
              f"{usable_area_sqft:,.0f} sq ft")

    return {
        "shade_hours_map": shade_hours,
        "shade_fraction_map": shade_fraction,
        "obstacle_mask": obstacles,
        "usable_mask": usable_mask,
        "avg_shade_pct": round(avg_shade_pct, 2),
        "usable_area_sqft": round(usable_area_sqft, 1),
        "usable_area_m2": round(usable_area_m2, 2),
        "n_daylight_hours": n_daylight,
        "obstacle_height_m": obstacle_height_m,
        "n_az_bins": len(bins),
    }


# ---- smoke test ------------------------------------------------------------
if __name__ == "__main__":
    import os
    import sys
    from PIL import ImageDraw, ImageFont
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.image_fetch import fetch_satellite_image_complete
    from components.roof_segmenter import segment_roof, auto_pick_prompt_point

    address = "E-87, Sarita Vihar, Delhi"
    zoom = 21
    scale = 2
    # CV-based auto-pick: find the brightest large region near image center
    # and use its centroid as the prompt. Replaces the hard-coded (570, 250).
    prompt_point = None  # filled in after image is fetched, see below

    print(f"\n{'=' * 60}")
    print(f"SHADING SMOKE TEST: {address}")
    print(f"{'=' * 60}")

    # Cache the fetched image bytes on disk so re-runs are reproducible
    # (Google's CDN sometimes serves slightly different imagery between
    # calls, which makes SAM produce different masks). This keeps the
    # smoke test stable across runs.
    cache_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
    os.makedirs(cache_root, exist_ok=True)
    cached_image = os.path.join(cache_root, "shading_smoketest_image.png")
    cached_meta = os.path.join(cache_root, "shading_smoketest_meta.txt")

    if os.path.exists(cached_image) and os.path.exists(cached_meta):
        print("[step 1] loading cached satellite image...")
        with open(cached_image, "rb") as f:
            image_bytes = f.read()
        with open(cached_meta, "r") as f:
            meta_lat, meta_lng, meta_addr = f.read().strip().split("|")
        res = {
            "image_data": image_bytes,
            "coordinates": {"lat": float(meta_lat), "lng": float(meta_lng)},
            "formatted_address": meta_addr,
            "image_size_bytes": len(image_bytes),
        }
        print(f"  loaded:    {cached_image}")
    else:
        print("[step 1] fetching satellite image...")
        res = fetch_satellite_image_complete(address=address, zoom=zoom, scale=scale)
        if "error" in res:
            print(f"  fetch failed: {res['error']}")
            sys.exit(1)
        with open(cached_image, "wb") as f:
            f.write(res["image_data"])
        with open(cached_meta, "w") as f:
            f.write(f"{res['coordinates']['lat']}|{res['coordinates']['lng']}|{res['formatted_address']}")
        print(f"  cached:    {cached_image}")

    # Pick the prompt point automatically using CV: brightest large region
    # nearest the image center. Avoids relying on geocoder pin landing on
    # the actual rooftop.
    prompt_point = auto_pick_prompt_point(res["image_data"])
    print(f"[step 2] auto-picked prompt point: {prompt_point}")

    print("[step 2] segmenting roof...")
    seg = segment_roof(
        res["image_data"],
        lat=res["coordinates"]["lat"],
        zoom=zoom,
        scale=scale,
        prompt_point=prompt_point,
        debug=True,
    )
    print(f"  roof:        {seg['area_sqft']:,.0f} sq ft  ({seg['pixel_count']:,} px after shadow filter)")
    print(f"  raw mask:    {seg['raw_pixel_count']:,} px before shadow filter")
    print(f"  m/pixel:     {seg['m_per_pixel']}")
    print(f"  prompt_pt:   {seg['prompt_point']}")

    # Step B: shading
    print("[step 3] analyzing shading...")
    sh = analyze_shading(
        image_bytes=res["image_data"],
        roof_mask=seg["mask"],
        lat=res["coordinates"]["lat"],
        lng=res["coordinates"]["lng"],
        m_per_pixel=seg["m_per_pixel"],
        debug=True,
    )

    print()
    print(f"RESULT")
    print(f"  Avg shade across roof:    {sh['avg_shade_pct']:.1f}%")
    print(f"  Usable (<10% shade) area: {sh['usable_area_sqft']:,.0f} sq ft")
    print(f"  Daylight hours simulated: {sh['n_daylight_hours']:,}")
    print(f"  Azimuth bins used:        {sh['n_az_bins']}")

    # Step C: visualize 4 panels (original / roof+obstacles / shade heatmap / usable)
    print("[step 4] saving visualization...")
    image = np.array(Image.open(io.BytesIO(res["image_data"])).convert("RGB"))
    px, py = seg["prompt_point"]

    def _draw_prompt_marker(panel: np.ndarray) -> np.ndarray:
        """Paint a red crosshair at the prompt point so the user can see where SAM was prompted."""
        out = panel.copy()
        # Red crosshair: 2 px thick arms, 30 px long
        for dx in range(-30, 31):
            xx = px + dx
            if 0 <= xx < out.shape[1]:
                for t in (-1, 0, 1):
                    if 0 <= py + t < out.shape[0]:
                        out[py + t, xx] = [255, 0, 0]
        for dy in range(-30, 31):
            yy = py + dy
            if 0 <= yy < out.shape[0]:
                for t in (-1, 0, 1):
                    if 0 <= px + t < out.shape[1]:
                        out[yy, px + t] = [255, 0, 0]
        return out

    # Panel 1: original satellite with prompt marker
    panel1 = _draw_prompt_marker(image)

    # Panel 2: roof mask (green) + obstacles (red) overlay
    panel2 = image.copy()
    panel2[seg["mask"]] = (0.5 * panel2[seg["mask"]] + 0.5 * np.array([0, 255, 0])).astype(np.uint8)
    panel2[sh["obstacle_mask"]] = (0.4 * panel2[sh["obstacle_mask"]] + 0.6 * np.array([255, 0, 0])).astype(np.uint8)
    panel2 = _draw_prompt_marker(panel2)

    # Panel 3: shade fraction heatmap on roof, blended with original
    shade_map = sh["shade_fraction_map"]
    norm_shade = np.clip(shade_map / max(shade_map.max(), 1e-6), 0, 1)
    cmap = plt.get_cmap("RdYlGn_r")  # green=low shade, red=high shade
    heatmap_rgba = (cmap(norm_shade) * 255).astype(np.uint8)
    heatmap_rgb = heatmap_rgba[..., :3]
    panel3 = image.copy()
    inside = seg["mask"]
    panel3[inside] = (0.45 * panel3[inside] + 0.55 * heatmap_rgb[inside]).astype(np.uint8)

    # Panel 4: usable mask (cyan) on top of original
    panel4 = image.copy()
    usable = sh["usable_mask"]
    panel4[usable] = (0.4 * panel4[usable] + 0.6 * np.array([0, 200, 255])).astype(np.uint8)

    # Crop every panel to the roof's bounding box + 15% padding so the
    # rooftop fills the frame instead of being a tiny patch in the middle.
    ys, xs = np.where(seg["mask"])
    if ys.size > 0:
        roof_h = ys.max() - ys.min()
        roof_w = xs.max() - xs.min()
        pad_h = int(roof_h * 0.15)
        pad_w = int(roof_w * 0.15)
        H, W = seg["mask"].shape
        y0 = max(0, ys.min() - pad_h)
        y1 = min(H, ys.max() + pad_h)
        x0 = max(0, xs.min() - pad_w)
        x1 = min(W, xs.max() + pad_w)

        def _crop(panel: np.ndarray) -> np.ndarray:
            return panel[y0:y1, x0:x1]

        panel1 = _crop(panel1)
        panel2 = _crop(panel2)
        panel3 = _crop(panel3)
        panel4 = _crop(panel4)

    fig, axes = plt.subplots(2, 2, figsize=(20, 20))
    titles = [
        f"1. Original satellite + prompt point ({px},{py})",
        f"2. Roof (green) + obstacles (red) — {seg['area_sqft']:,.0f} sq ft",
        f"3. Annual shade heatmap — avg {sh['avg_shade_pct']:.1f}%",
        f"4. Usable area (cyan) — {sh['usable_area_sqft']:,.0f} sq ft",
    ]
    panels = [panel1, panel2, panel3, panel4]
    for ax, panel, title in zip(axes.ravel(), panels, titles):
        ax.imshow(panel)
        ax.set_title(title, fontsize=14)
        ax.set_xticks([]); ax.set_yticks([])

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "shading_test.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=140, bbox_inches="tight", pad_inches=0.2)
    plt.close()

    print(f"  saved: {out_path}")
