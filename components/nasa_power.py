"""
NASA POWER hourly irradiance client.

Pulls an 8760-hour Typical Meteorological Year for a given (lat, lng) using
NASA's free POWER API (no API key required). Returns a pandas DataFrame in
the shape pvlib's PVWatts model expects.

API docs: https://power.larc.nasa.gov/docs/services/api/temporal/hourly/
Parameters:
    ALLSKY_SFC_SW_DWN   Global Horizontal Irradiance (GHI), W/m^2
    ALLSKY_SFC_SW_DNI   Direct Normal Irradiance (DNI), W/m^2
    ALLSKY_SFC_SW_DIFF  Diffuse Horizontal Irradiance (DHI), W/m^2
    T2M                 Ambient temperature at 2m, deg C
    WS10M               Wind speed at 10m, m/s
"""

import os
import json
import hashlib
import requests
import pandas as pd
from datetime import datetime

POWER_ENDPOINT = "https://power.larc.nasa.gov/api/temporal/hourly/point"

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache", "nasa_power")
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_TMY_YEAR = 2022

PARAMETERS = [
    "ALLSKY_SFC_SW_DWN",
    "ALLSKY_SFC_SW_DNI",
    "ALLSKY_SFC_SW_DIFF",
    "T2M",
    "WS10M",
]


def _cache_key(lat: float, lng: float, year: int) -> str:
    raw = f"{round(lat, 4)}_{round(lng, 4)}_{year}"
    h = hashlib.md5(raw.encode()).hexdigest()[:10]
    return os.path.join(CACHE_DIR, f"{raw}_{h}.json")


def fetch_hourly_weather(lat: float, lng: float, year: int = DEFAULT_TMY_YEAR) -> pd.DataFrame:
    """
    Fetch an 8760-row hourly weather DataFrame for (lat, lng, year).

    Caches raw JSON response on disk; subsequent calls for the same coords+year
    are instant.

    Returns DataFrame indexed by tz-aware UTC timestamps with columns:
        ghi (W/m^2), dni (W/m^2), dhi (W/m^2),
        temp_air (deg C), wind_speed (m/s)
    """
    cache_path = _cache_key(lat, lng, year)

    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            payload = json.load(f)
    else:
        params = {
            "parameters": ",".join(PARAMETERS),
            "community": "re",
            "longitude": lng,
            "latitude": lat,
            "start": f"{year}0101",
            "end": f"{year}1231",
            "format": "JSON",
            "time-standard": "UTC",
        }
        resp = requests.get(POWER_ENDPOINT, params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        with open(cache_path, "w") as f:
            json.dump(payload, f)

    data = payload["properties"]["parameter"]

    index = pd.to_datetime(list(data["ALLSKY_SFC_SW_DWN"].keys()), format="%Y%m%d%H", utc=True)

    df = pd.DataFrame(
        {
            "ghi": list(data["ALLSKY_SFC_SW_DWN"].values()),
            "dni": list(data["ALLSKY_SFC_SW_DNI"].values()),
            "dhi": list(data["ALLSKY_SFC_SW_DIFF"].values()),
            "temp_air": list(data["T2M"].values()),
            "wind_speed": list(data["WS10M"].values()),
        },
        index=index,
    )

    # NASA POWER encodes missing as -999; clip to non-negative for irradiance
    df = df.replace(-999, pd.NA).dropna()
    for col in ("ghi", "dni", "dhi"):
        df[col] = df[col].clip(lower=0)

    return df


def annual_ghi_kwh_per_m2(df: pd.DataFrame) -> float:
    """Total annual global horizontal irradiance, kWh/m^2."""
    return float(df["ghi"].sum()) / 1000.0


def peak_sun_hours(df: pd.DataFrame) -> float:
    """Average daily peak-sun-hours (kWh/m^2/day equivalent)."""
    return annual_ghi_kwh_per_m2(df) / 365.0

if __name__ == "__main__":
    # Smoke test: Mumbai
    df = fetch_hourly_weather(19.0760, 72.8777)
    print(f"Rows: {len(df)}")
    print(f"Annual GHI: {annual_ghi_kwh_per_m2(df):.0f} kWh/m^2")
    print(f"Avg peak sun hours: {peak_sun_hours(df):.2f} h/day")
    print(df.head(3))
