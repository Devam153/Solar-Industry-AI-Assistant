"""
PVWatts engine — turns weather + system specs into hourly AC power.

Follows NREL's PVWatts v5 methodology via pvlib. For each of 8760 hours:
    1. Compute sun position (zenith, azimuth) for this lat/lng/time.
    2. Transpose GHI/DNI/DHI onto the tilted panel plane (POA).
    3. Compute cell temperature from POA + ambient + wind.
    4. Compute DC power with temperature derating.
    5. Apply the PVWatts loss stack (soiling, wiring, mismatch, etc.).
    6. Convert DC to AC via inverter model.

Inputs: the weather DataFrame from components.nasa_power (columns
ghi/dni/dhi/temp_air/wind_speed, UTC-indexed).
"""

import pandas as pd
from pvlib import solarposition, irradiance, temperature, pvsystem, inverter


# PVWatts v5 default loss stack, in percent.
# Each factor is independent; pvsystem.pvwatts_losses multiplies them into
# a single combined derate.
DEFAULT_LOSSES_PCT = {
    "soiling": 2.0,          # dust on panels (higher for Indian conditions)
    "shading": 3.0,          # near-field shading (handled more precisely later)
    "snow": 0.0,             # basically 0 in India
    "mismatch": 2.0,         # panel-to-panel variation
    "wiring": 2.0,           # DC cable resistive losses
    "connections": 0.5,      # connector losses
    "lid": 1.5,              # light-induced degradation
    "nameplate_rating": 1.0, # vs. manufacturer spec
    "age": 0.0,              # 0 for year 1; grows ~0.5%/year
    "availability": 3.0,     # grid outages + maintenance downtime
}

# Temperature coefficient of power for a typical silicon module.
# -0.4% per degree C above 25 C. This is why hot Indian rooftops lose output.
DEFAULT_GAMMA_PDC = -0.004

# SAPM cell-temperature model coefficients for "open rack, glass-glass" mount.
# a and b come from Sandia; they describe how irradiance and wind drive panel temp.
SAPM_COEFFS = {"a": -3.56, "b": -0.075, "deltaT": 3}


def _default_tilt_for_latitude(lat: float) -> float:
    """
    Rule of thumb: optimal fixed tilt ~= latitude (for annual energy).
    Clipped to [10, 35] for practical rooftop mounting.
    """
    return float(max(10, min(35, abs(lat))))


def simulate_annual_generation(
    weather: pd.DataFrame,
    latitude: float,
    longitude: float,
    system_size_kw: float,
    tilt: float | None = None,
    azimuth: float = 180.0,
    losses_pct: dict | None = None,
    gamma_pdc: float = DEFAULT_GAMMA_PDC,
    inverter_efficiency: float = 0.96,
) -> dict:
    """
    Run an 8760-hour PVWatts simulation and return annual/monthly totals.

    Parameters
    ----------
    weather : DataFrame with columns [ghi, dni, dhi, temp_air, wind_speed],
              indexed by tz-aware UTC timestamps.
    latitude, longitude : site coordinates (degrees).
    system_size_kw : DC nameplate capacity of the array.
    tilt : panel tilt from horizontal in degrees. If None, uses latitude rule.
    azimuth : panel azimuth in degrees (180 = south, northern hemisphere
              convention; pvlib uses 180=south for the northern hemisphere).
    losses_pct : dict of named losses; defaults to PVWatts v5 stack.
    gamma_pdc : temperature coefficient of power (per deg C).
    inverter_efficiency : nominal inverter efficiency (0-1).

    Returns
    -------
    dict with keys:
        annual_kwh           float
        monthly_kwh          pd.Series of length 12 (Jan..Dec in IST)
        hourly_ac_kw         pd.Series of length ~8760 (W -> /1000 for kW)
        peak_ac_kw           float (max instantaneous AC output)
        capacity_factor_pct  float (annual_kwh / (size_kw * 8760) * 100)
        specific_yield       float (annual_kwh / size_kw  == kWh/kWp/year)
        loss_breakdown       dict of percent losses + total combined percent
        system_specs         dict (size_kw, tilt, azimuth)
    """
    if tilt is None:
        tilt = _default_tilt_for_latitude(latitude)

    if losses_pct is None:
        losses_pct = DEFAULT_LOSSES_PCT.copy()

    # 1. Sun position at every hour.
    #    pvlib expects tz-aware times. weather.index is tz-aware UTC (from NASA POWER).
    solpos = solarposition.get_solarposition(
        time=weather.index,
        latitude=latitude,
        longitude=longitude,
        temperature=weather["temp_air"],
    )

    # 2. Transpose GHI/DNI/DHI to plane-of-array (tilted panel).
    poa = irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        solar_zenith=solpos["apparent_zenith"],
        solar_azimuth=solpos["azimuth"],
        dni=weather["dni"],
        ghi=weather["ghi"],
        dhi=weather["dhi"],
    )
    poa_global = poa["poa_global"].clip(lower=0).fillna(0)
#at sunset, transposition can briefly produce slightly negative numbers (due to model edge cases). Clip to zero.

    # 3. Cell temperature using Sandia Array Performance Model.
    #    Realistic for open-rack rooftop mounts with air gap beneath.
    cell_temp = temperature.sapm_cell(
        poa_global=poa_global,
        temp_air=weather["temp_air"],
        wind_speed=weather["wind_speed"],
        **SAPM_COEFFS,
    )

    # 4. DC power with temperature derating.
    #    pdc0 = nameplate DC watts at STC (1000 W/m^2, 25 C)
    pdc0_w = system_size_kw * 1000.0
    dc_power_w = pvsystem.pvwatts_dc(
        effective_irradiance=poa_global,
        temp_cell=cell_temp,
        pdc0=pdc0_w,
        gamma_pdc=gamma_pdc,
    )

    # 5. Apply the combined PVWatts loss stack.
    #    pvwatts_losses returns the TOTAL percent loss (not additive — it's
    #    the combined multiplicative derate, so 1 - total/100 is the retention).
    total_loss_pct = pvsystem.pvwatts_losses(**losses_pct)
    dc_after_losses_w = dc_power_w * (1 - total_loss_pct / 100.0)
#pvwatts_losses() takes the named loss percentages and combines
#  them multiplicatively (not additively!). So 2% + 2% + 3% + ... isn't a 17% total 


    # 6. DC -> AC via PVWatts inverter model.
    #    For rooftop systems AC nameplate is typically ~= DC nameplate.
    ac_power_w = inverter.pvwatts(
        pdc=dc_after_losses_w,
        pdc0=pdc0_w,
        eta_inv_nom=inverter_efficiency,
    ).clip(lower=0)

    # Aggregate results.
    hourly_ac_kw = ac_power_w / 1000.0
    annual_kwh = float(hourly_ac_kw.sum())

    # Group by IST month so "May" means the Indian month of May, not UTC May.
    ist_index = hourly_ac_kw.index.tz_convert("Asia/Kolkata")
    monthly_kwh = hourly_ac_kw.groupby(ist_index.month).sum()
    monthly_kwh.index = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ][: len(monthly_kwh)]

    peak_ac_kw = float(hourly_ac_kw.max())
    capacity_factor_pct = annual_kwh / (system_size_kw * 8760) * 100
    specific_yield = annual_kwh / system_size_kw

    loss_breakdown = dict(losses_pct)
    loss_breakdown["total_combined_pct"] = round(total_loss_pct, 2)

    return {
        "annual_kwh": round(annual_kwh, 1),
        "monthly_kwh": monthly_kwh.round(1),
        "hourly_ac_kw": hourly_ac_kw,
        "peak_ac_kw": round(peak_ac_kw, 2),
        "capacity_factor_pct": round(capacity_factor_pct, 2),
        "specific_yield": round(specific_yield, 1),
        "loss_breakdown": loss_breakdown,
        "system_specs": {
            "size_kw": system_size_kw,
            "tilt": round(tilt, 1),
            "azimuth": azimuth,
            "gamma_pdc": gamma_pdc,
            "inverter_efficiency": inverter_efficiency,
        },
    }


if __name__ == "__main__":
    # Smoke test: 5 kW rooftop system in Mumbai
    # Allow running directly (`python components/pvwatts_engine.py`) by
    # putting the project root on sys.path.
    import sys
    import os
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    from components.nasa_power import fetch_hourly_weather

    lat, lng = 19.0760, 72.8777
    weather = fetch_hourly_weather(lat, lng)
    result = simulate_annual_generation(
        weather=weather,
        latitude=lat,
        longitude=lng,
        system_size_kw=5.0,
    )

    print("=" * 60)
    print("PVWatts simulation — 5 kW rooftop system, Mumbai")
    print("=" * 60)
    print(f"Annual AC energy:     {result['annual_kwh']:,.0f} kWh/year")
    print(f"Specific yield:       {result['specific_yield']:,.0f} kWh/kWp/year")
    print(f"Capacity factor:      {result['capacity_factor_pct']:.1f}%")
    print(f"Peak AC power:        {result['peak_ac_kw']:.2f} kW")
    print()
    print("Monthly generation (kWh):")
    print(result["monthly_kwh"].to_string())
    print()
    print("Loss stack (% of each factor):")
    for k, v in result["loss_breakdown"].items():
        print(f"  {k:25s}  {v}")
    print()
    print(f"System specs: {result['system_specs']}")
