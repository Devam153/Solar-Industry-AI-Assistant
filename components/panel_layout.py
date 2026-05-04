"""
Panel layout optimizer — pack standard solar panels onto the usable rooftop area.

Solves a constrained 2D bin-packing problem:
    - input:  usable_mask (from shading_analyzer) + obstacle_mask + m_per_pixel
    - output: list of panel rectangles, panel_count, system_size_kW

Constraints honored:
    1. Setback from roof edges (default 0.5 m, fire code)
    2. Obstacle avoidance (water tanks, AC units, stair-rooms)
    3. Heavily-shaded zones already excluded via usable_mask
    4. Aisle spacing between panels for maintenance access (default 0.1 m)

Default panel: 1.65 m x 1.0 m, 330 W (Indian residential standard).
Configurable via parameters.

Public API:
    optimize_panel_layout(usable_mask, obstacle_mask, m_per_pixel, ...) -> dict

Returns dict with:
    panels                list of (x, y, w, h) pixel rectangles
    panel_count           int
    system_size_kw        float
    placed_area_m2        float (panels' physical footprint)
    packing_efficiency    float (placed / usable)
    + config echo
"""

import cv2
import numpy as np


# ---- main API --------------------------------------------------------------
def optimize_panel_layout(
    usable_mask: np.ndarray,
    m_per_pixel: float,
    obstacle_mask: np.ndarray | None = None,
    panel_height_m: float = 1.65,
    panel_width_m: float = 1.00,
    panel_wattage: int = 330,
    setback_m: float = 0.5,
    aisle_m: float = 0.10,
    debug: bool = False,
) -> dict:
    """
    Pack standard PV panels onto the usable rooftop.

    Strategy
    --------
    - Erode usable_mask by `setback_m` to enforce edge clearance.
    - Tile a regular grid of panel slots, stride = panel_dim + aisle.
    - For each slot: accept if entirely inside the eroded usable area AND
      doesn't overlap any obstacle pixel; reject otherwise.
    - Each accepted slot = 1 panel.

    Notes
    -----
    Panel orientation: portrait (long axis = 1.65 m running north-south).
    Most Indian residential installations use this orientation for better
    airflow and wiring layout. Easy to flip if needed.

    Returns a dict (see module docstring for keys).
    """
    h, w = usable_mask.shape

    # Convert physical lengths to pixels (round, but never below 1).
    panel_h_px = max(1, int(round(panel_height_m / m_per_pixel)))
    panel_w_px = max(1, int(round(panel_width_m / m_per_pixel)))
    setback_px = int(round(setback_m / m_per_pixel))
    aisle_px = int(round(aisle_m / m_per_pixel))

    # 1. Apply edge setback by morphological erosion.
    if setback_px > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (setback_px * 2 + 1, setback_px * 2 + 1),
        )
        usable_eroded = cv2.erode(
            usable_mask.astype(np.uint8), kernel
        ).astype(bool)
    else:
        usable_eroded = usable_mask.astype(bool)

    def _pack(pw: int, ph: int) -> list[tuple[int, int, int, int]]:
        """Greedy grid pack with given panel pixel dimensions; try multiple
        grid offsets to find the best translation, return the best result."""
        stride_y = ph + aisle_px
        stride_x = pw + aisle_px

        # Try a handful of grid offsets — the right offset can boost panel
        # count by 15-30% on irregular usable regions.
        offsets_to_try = []
        n_off = 4  # 4x4 = 16 combinations
        for oy in range(0, stride_y, max(1, stride_y // n_off)):
            for ox in range(0, stride_x, max(1, stride_x // n_off)):
                offsets_to_try.append((oy, ox))

        best: list[tuple[int, int, int, int]] = []
        for oy, ox in offsets_to_try:
            placed: list[tuple[int, int, int, int]] = []
            for y0 in range(oy, h - ph + 1, stride_y):
                y1 = y0 + ph
                row = usable_eroded[y0:y1]
                for x0 in range(ox, w - pw + 1, stride_x):
                    x1 = x0 + pw
                    slot_usable = row[:, x0:x1]
                    if not slot_usable.all():
                        continue
                    if obstacle_mask is not None:
                        if obstacle_mask[y0:y1, x0:x1].any():
                            continue
                    placed.append((x0, y0, pw, ph))
            if len(placed) > len(best):
                best = placed
        return best

    # Try BOTH portrait (long axis vertical) and landscape (long axis
    # horizontal). Pick whichever orientation packs more panels onto this
    # specific roof shape.
    panels_portrait = _pack(panel_w_px, panel_h_px)
    panels_landscape = _pack(panel_h_px, panel_w_px)

    if len(panels_landscape) > len(panels_portrait):
        panels = panels_landscape
        chosen_orientation = "landscape"
    else:
        panels = panels_portrait
        chosen_orientation = "portrait"

    panel_count = len(panels)
    system_size_kw = panel_count * panel_wattage / 1000.0

    # Packing efficiency for diagnostics.
    panel_area_m2 = panel_height_m * panel_width_m
    placed_area_m2 = panel_count * panel_area_m2
    usable_area_m2 = float(usable_mask.sum()) * (m_per_pixel ** 2)
    packing_efficiency = placed_area_m2 / max(usable_area_m2, 1e-6)

    if debug:
        print(f"[panel_layout] panel size: {panel_w_px}x{panel_h_px} px "
              f"({panel_width_m}x{panel_height_m} m)")
        print(f"[panel_layout] setback {setback_px} px, aisle {aisle_px} px")
        print(f"[panel_layout] best orientation: {chosen_orientation} "
              f"(portrait={len(panels_portrait)}, landscape={len(panels_landscape)})")
        print(f"[panel_layout] placed {panel_count} panels = "
              f"{system_size_kw:.2f} kW")
        print(f"[panel_layout] packing efficiency: "
              f"{packing_efficiency*100:.1f}% (placed/usable)")

    return {
        "panels": panels,
        "panel_count": panel_count,
        "system_size_kw": round(system_size_kw, 2),
        "placed_area_m2": round(placed_area_m2, 1),
        "usable_area_m2": round(usable_area_m2, 1),
        "packing_efficiency": round(packing_efficiency, 3),
        "orientation": chosen_orientation,
        "panel_height_m": panel_height_m,
        "panel_width_m": panel_width_m,
        "panel_wattage": panel_wattage,
        "setback_m": setback_m,
        "aisle_m": aisle_m,
        "panel_size_px": (panel_w_px, panel_h_px),
    }


# ---- visualization helper --------------------------------------------------
def draw_panel_layout(
    image_rgb: np.ndarray,
    panels: list[tuple[int, int, int, int]],
    color: tuple[int, int, int] = (0, 100, 255),  # BGR-ish, but we draw on RGB
    fill_alpha: float = 0.55,
    border: int = 2,
) -> np.ndarray:
    """Paint each panel rectangle onto a copy of the image."""
    out = image_rgb.copy()
    color_arr = np.array(color, dtype=np.float32)
    for (x, y, pw, ph) in panels:
        # Fill (semi-transparent)
        roi = out[y:y + ph, x:x + pw]
        roi[:] = ((1 - fill_alpha) * roi + fill_alpha * color_arr).astype(np.uint8)
        # Border
        cv2.rectangle(out, (x, y), (x + pw - 1, y + ph - 1),
                      color, thickness=border)
    return out


# ---- smoke test ------------------------------------------------------------
if __name__ == "__main__":
    import io
    import os
    import sys

    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    try:
        import torch  # noqa: F401
    except Exception:
        pass

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.image_fetch import fetch_satellite_image_complete
    from components.roof_segmenter import segment_roof, auto_pick_prompt_point
    from components.shading_analyzer import analyze_shading

    address = "E-87, Sarita Vihar, Delhi"
    zoom = 21
    scale = 2

    cache_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
    os.makedirs(cache_root, exist_ok=True)
    cached_image = os.path.join(cache_root, "shading_smoketest_image.png")
    cached_meta = os.path.join(cache_root, "shading_smoketest_meta.txt")

    print(f"\n{'=' * 60}")
    print(f"PANEL LAYOUT SMOKE TEST: {address}")
    print(f"{'=' * 60}")

    # Step 1: image (use cache if present)
    if os.path.exists(cached_image) and os.path.exists(cached_meta):
        print("[step 1] loading cached satellite image...")
        with open(cached_image, "rb") as f:
            image_bytes = f.read()
        with open(cached_meta, "r") as f:
            meta_lat, meta_lng, _ = f.read().strip().split("|")
        lat = float(meta_lat); lng = float(meta_lng)
    else:
        print("[step 1] fetching satellite image...")
        res = fetch_satellite_image_complete(address=address, zoom=zoom, scale=scale)
        image_bytes = res["image_data"]
        lat = res["coordinates"]["lat"]; lng = res["coordinates"]["lng"]
        with open(cached_image, "wb") as f:
            f.write(image_bytes)
        with open(cached_meta, "w") as f:
            f.write(f"{lat}|{lng}|{res['formatted_address']}")

    # Step 2: pick prompt + segment
    prompt_point = auto_pick_prompt_point(image_bytes)
    print(f"[step 2] auto-picked prompt: {prompt_point}")
    seg = segment_roof(
        image_bytes, lat=lat, zoom=zoom, scale=scale,
        prompt_point=prompt_point, debug=False,
    )
    print(f"  roof: {seg['area_sqft']:,.0f} sq ft  ({seg['pixel_count']:,} px)  m/px {seg['m_per_pixel']}")

    # Step 3: shading
    print("[step 3] analyzing shading...")
    sh = analyze_shading(
        image_bytes=image_bytes,
        roof_mask=seg["mask"],
        lat=lat, lng=lng,
        m_per_pixel=seg["m_per_pixel"],
        debug=False,
    )
    print(f"  avg shade: {sh['avg_shade_pct']:.1f}%   usable: {sh['usable_area_sqft']:,.0f} sq ft")

    # Step 4: panel layout
    print("[step 4] optimizing panel layout...")
    layout = optimize_panel_layout(
        usable_mask=sh["usable_mask"],
        obstacle_mask=sh["obstacle_mask"],
        m_per_pixel=seg["m_per_pixel"],
        debug=True,
    )
    print()
    print("=" * 60)
    print(f"FINAL")
    print("=" * 60)
    print(f"  Panels placed:         {layout['panel_count']}")
    print(f"  System size:           {layout['system_size_kw']:.2f} kW")
    print(f"  Placed area:           {layout['placed_area_m2']:.0f} m^2")
    print(f"  Usable area:           {layout['usable_area_m2']:.0f} m^2")
    print(f"  Packing efficiency:    {layout['packing_efficiency']*100:.1f}%")

    # Step 5: visualization (4 cropped panels)
    print("[step 5] rendering visualization...")
    image = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    px, py = seg["prompt_point"]

    def _crosshair(arr, x, y, color=(255, 0, 0)):
        out = arr.copy()
        for d in range(-30, 31):
            xx = x + d; yy = y + d
            if 0 <= xx < out.shape[1]:
                for t in (-1, 0, 1):
                    if 0 <= y + t < out.shape[0]:
                        out[y + t, xx] = color
            if 0 <= yy < out.shape[0]:
                for t in (-1, 0, 1):
                    if 0 <= x + t < out.shape[1]:
                        out[yy, x + t] = color
        return out

    panel1 = _crosshair(image, px, py)
    # Panel 2: roof + obstacles
    panel2 = image.copy()
    panel2[seg["mask"]] = (0.5 * panel2[seg["mask"]] + 0.5 * np.array([0, 255, 0])).astype(np.uint8)
    panel2[sh["obstacle_mask"]] = (0.4 * panel2[sh["obstacle_mask"]] + 0.6 * np.array([255, 0, 0])).astype(np.uint8)
    # Panel 3: usable area
    panel3 = image.copy()
    panel3[sh["usable_mask"]] = (0.4 * panel3[sh["usable_mask"]] + 0.6 * np.array([0, 200, 255])).astype(np.uint8)
    # Panel 4: PANEL LAYOUT — the money shot
    panel4 = draw_panel_layout(image, layout["panels"])

    # Crop to roof bbox + 15% padding
    ys, xs = np.where(seg["mask"])
    if ys.size > 0:
        H, W = seg["mask"].shape
        roof_h = ys.max() - ys.min(); roof_w = xs.max() - xs.min()
        pad_h = int(roof_h * 0.15); pad_w = int(roof_w * 0.15)
        y0 = max(0, ys.min() - pad_h); y1 = min(H, ys.max() + pad_h)
        x0 = max(0, xs.min() - pad_w); x1 = min(W, xs.max() + pad_w)
        panel1 = panel1[y0:y1, x0:x1]
        panel2 = panel2[y0:y1, x0:x1]
        panel3 = panel3[y0:y1, x0:x1]
        panel4 = panel4[y0:y1, x0:x1]

    fig, axes = plt.subplots(2, 2, figsize=(20, 20))
    titles = [
        f"1. Satellite + auto-picked prompt ({px},{py})",
        f"2. Roof (green) + obstacles (red) — {seg['area_sqft']:,.0f} sq ft",
        f"3. Usable area — {sh['usable_area_sqft']:,.0f} sq ft  (avg shade {sh['avg_shade_pct']:.1f}%)",
        f"4. Panel layout — {layout['panel_count']} panels = {layout['system_size_kw']:.2f} kW",
    ]
    panels_to_show = [panel1, panel2, panel3, panel4]
    for ax, panel, title in zip(axes.ravel(), panels_to_show, titles):
        ax.imshow(panel)
        ax.set_title(title, fontsize=14)
        ax.set_xticks([]); ax.set_yticks([])

    out_path = os.path.join(cache_root, "panel_layout_test.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=140, bbox_inches="tight", pad_inches=0.2)
    plt.close()
    print(f"  saved: {out_path}")
