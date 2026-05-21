import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import requests


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
DEFAULT_WAVE_HEIGHT_M = 0.5
FORECAST_LOOKAHEAD_HOURS = 5

@dataclass(frozen=True)
class WeatherSnapshot:
    beach_id: str
    temperature_c: float
    apparent_temperature_c: float
    precipitation_mm: float
    precipitation_probability_percent: float
    wind_kmh: float
    uv_index: float
    wave_height_m: float
    cloud_cover_percent: float


def load_local_weather(path: Path) -> dict[str, WeatherSnapshot]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = csv.DictReader(file)
        return {
            row["beach_id"]: WeatherSnapshot(
                beach_id=row["beach_id"],
                temperature_c=float(row["temperature_c"]),
                apparent_temperature_c=float(row["apparent_temperature_c"]),
                precipitation_mm=float(row["precipitation_mm"]),
                precipitation_probability_percent=float(row["precipitation_probability_percent"]),
                wind_kmh=float(row["wind_kmh"]),
                uv_index=float(row["uv_index"]),
                wave_height_m=float(row["wave_height_m"]),
                cloud_cover_percent=float(row["cloud_cover_percent"]),
            )
            for row in rows
        }


def write_weather_snapshot_csv(weather_by_beach: dict[str, WeatherSnapshot], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "beach_id",
        "temperature_c",
        "apparent_temperature_c",
        "precipitation_mm",
        "precipitation_probability_percent",
        "wind_kmh",
        "uv_index",
        "wave_height_m",
        "cloud_cover_percent",
    ]

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for beach_id in sorted(weather_by_beach):
            snapshot = weather_by_beach[beach_id]
            writer.writerow(
                {
                    "beach_id": snapshot.beach_id,
                    "temperature_c": snapshot.temperature_c,
                    "apparent_temperature_c": snapshot.apparent_temperature_c,
                    "precipitation_mm": snapshot.precipitation_mm,
                    "precipitation_probability_percent": snapshot.precipitation_probability_percent,
                    "wind_kmh": snapshot.wind_kmh,
                    "uv_index": snapshot.uv_index,
                    "wave_height_m": snapshot.wave_height_m,
                    "cloud_cover_percent": snapshot.cloud_cover_percent,
                }
            )


def fetch_open_meteo_weather(beaches: Iterable[dict], timeout: int = 8) -> dict[str, WeatherSnapshot]:
    snapshot: dict[str, WeatherSnapshot] = {}

    def request_json(url: str, params: dict) -> dict:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            reason = payload.get("reason", "erro desconhecido")
            raise RuntimeError(f"Open-Meteo retornou erro: {reason}")
        return payload

    def max_float(values: Optional[Iterable]) -> float:
        valid_values = [float(value) for value in values or [] if value is not None]
        return max(valid_values, default=0.0)

    def current_float(values: dict, key: str, default: float = 0.0) -> float:
        value = values.get(key)
        return float(value) if value is not None else default

    def upcoming_float(
        values: dict,
        key: str,
        current_time: str | None,
        hours: int = FORECAST_LOOKAHEAD_HOURS,
    ) -> float:
        series = values.get(key) or []
        times = values.get("time") or []
        if not series:
            return 0.0
        start_index = 0
        if current_time and times:
            try:
                current_dt = datetime.fromisoformat(current_time)
                start_index = next(
                    (index for index, item in enumerate(times) if datetime.fromisoformat(item) >= current_dt),
                    0,
                )
            except ValueError:
                start_index = 0
        window = series[start_index : start_index + hours] or series
        return max_float(window)
    
    for beach in beaches:
        forecast_params = {
            "latitude": beach["latitude"],
            "longitude": beach["longitude"],
            "current": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,cloud_cover",
            "hourly": "uv_index,precipitation_probability",
            "forecast_days": 1,
            "timezone": "America/Sao_Paulo",
        }
        marine_params = {
            "latitude": beach["latitude"],
            "longitude": beach["longitude"],
            "current": "wave_height",
            "timezone": "America/Sao_Paulo",
        }

        forecast = request_json(FORECAST_URL, forecast_params)
        current = forecast.get("current", {})
        hourly = forecast.get("hourly", {})
        current_time = current.get("time")

        try:
            marine = request_json(MARINE_URL, marine_params)
            wave_height_m = current_float(marine.get("current", {}), "wave_height", DEFAULT_WAVE_HEIGHT_M)
        except Exception:
            wave_height_m = DEFAULT_WAVE_HEIGHT_M

        snapshot[beach["id"]] = WeatherSnapshot(
            beach_id               = beach["id"],
            temperature_c          = current_float(current, "temperature_2m"),
            apparent_temperature_c = current_float(current, "apparent_temperature"),
            precipitation_mm       = current_float(current, "precipitation"),
            precipitation_probability_percent = upcoming_float(hourly, "precipitation_probability", current_time),
            wind_kmh               = current_float(current, "wind_speed_10m"),
            cloud_cover_percent    = current_float(current, "cloud_cover"),
            wave_height_m          = wave_height_m,
            uv_index               = upcoming_float(hourly, "uv_index", current_time),
        )

    return snapshot


def weather_score(snapshot: WeatherSnapshot) -> float:
    current_rain_score = max(0.0, 100.0 - snapshot.precipitation_mm * 65.0)
    rain_probability = snapshot.precipitation_probability_percent
    if rain_probability >= 80.0:
        precipitation_risk_score = 5.0
    elif rain_probability >= 60.0:
        precipitation_risk_score = 25.0
    elif rain_probability >= 40.0:
        precipitation_risk_score = 50.0
    elif rain_probability >= 25.0:
        precipitation_risk_score = 70.0
    else:
        precipitation_risk_score = max(85.0, 100.0 - rain_probability * 0.5)
    rain_score = (current_rain_score * 0.25) + (precipitation_risk_score * 0.75)

    wind_score = max(0.0, 100.0 - max(0.0, snapshot.wind_kmh - 16.0) * 5.0)
    wave_score = max(0.0, 100.0 - max(0.0, snapshot.wave_height_m - 0.8) * 65.0)
    apparent_temperature = snapshot.apparent_temperature_c or snapshot.temperature_c
    if 25.0 <= apparent_temperature <= 31.0:
        temperature_score = 100.0
    else:
        target = 25.0 if apparent_temperature < 25.0 else 31.0
        penalty_per_degree = 18.0 if apparent_temperature < 25.0 else 8.0
        temperature_score = max(0.0, 100.0 - abs(apparent_temperature - target) * penalty_per_degree)
    uv_score = max(55.0, 100.0 - max(0.0, snapshot.uv_index - 8.0) * 8.0)
    cloud_score = max(35.0, 100.0 - max(0.0, snapshot.cloud_cover_percent - 45.0) * 0.9)

    score = (
        (rain_score * 0.45)
        + (temperature_score * 0.30)
        + (wind_score * 0.10)
        + (wave_score * 0.08)
        + (cloud_score * 0.04)
        + (uv_score * 0.03)
    )
    return round(max(0.0, min(100.0, score)), 2)


def weather_warnings(snapshot: WeatherSnapshot) -> list[str]:
    warnings = []
    probability = round(snapshot.precipitation_probability_percent)

    if probability >= 60:
        warnings.append(f"Alta chance de chuva: {probability}%")
    elif probability >= 35:
        warnings.append(f"Chance moderada de chuva: {probability}%")

    if snapshot.precipitation_mm > 0:
        warnings.append(f"Chuva atual: {snapshot.precipitation_mm:.1f} mm")

    if snapshot.wind_kmh >= 30:
        warnings.append(f"Vento forte: {snapshot.wind_kmh:.0f} km/h")

    if snapshot.wave_height_m >= 1.2:
        warnings.append(f"Mar agitado: {snapshot.wave_height_m:.1f} m")

    if snapshot.uv_index >= 9:
        warnings.append(f"UV muito alto: {snapshot.uv_index:.1f}")

    return warnings
