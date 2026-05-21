import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from praias_ai.sentiment import analyze_sentiment
from praias_ai.weather import WeatherSnapshot, weather_score, weather_warnings


def load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def bathing_index_penalty(summary: dict, fallback_status: str = "") -> float:
    if summary["points_total"]:
        bad_points = summary["points_improper"] + summary["points_interdicted"]
        if bad_points == summary["points_total"]:
            return 15.0
        return 0.0

    normalized = fallback_status.strip().lower()
    if normalized in {"interditado", "interditada", "impropria", "imprópria", "improprio", "impróprio"}:
        return 15.0
    return 0.0


def normalize_bathing_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"proprio", "propria", "próprio", "própria", "adequada", "boa"}:
        return "Próprio"
    if normalized in {"interditado", "interditada"}:
        return "Interditado"
    if normalized in {"atencao", "atenção", "regular"}:
        return "Atenção"
    if not normalized or normalized == "sem dado":
        return "Sem dado"
    return "Impróprio"


def summarize_bathing_points(rows: list[dict]) -> dict:
    counts = {"Próprio": 0, "Impróprio": 0, "Interditado": 0, "Atenção": 0, "Sem dado": 0}
    points = []

    for row in rows:
        status = normalize_bathing_status(row.get("status", ""))
        counts[status] = counts.get(status, 0) + 1
        points.append(
            {
                "point_id": row.get("point_id", ""),
                "status": status,
                "subdivision": row.get("subdivision", ""),
                "location": row.get("location", ""),
                "valid_until": row.get("valid_until", ""),
                "source": row.get("source", ""),
                "notes": row.get("notes", ""),
            }
        )

    total = len(points)
    if not total:
        return {
            "status": "Sem dado",
            "severity": "unknown",
            "proper_percent": None,
            "points_total": 0,
            "bad_percent": None,
            "points_proper": 0,
            "points_improper": 0,
            "points_interdicted": 0,
            "points_attention": 0,
            "points": [],
        }

    if counts["Interditado"]:
        status = "Parcialmente interditada" if counts["Próprio"] else "Interditada"
        severity = "danger"
    elif counts["Impróprio"]:
        status = "Mista" if counts["Próprio"] else "Imprópria"
        severity = "warning" if counts["Próprio"] else "danger"
    elif counts["Atenção"]:
        status = "Atenção"
        severity = "warning"
    else:
        status = "Própria"
        severity = "good"

    bad_points = counts["Impróprio"] + counts["Interditado"]
    return {
        "status": status,
        "severity": severity,
        "proper_percent": round((counts["Próprio"] / total) * 100.0, 1),
        "bad_percent": round((bad_points / total) * 100.0, 1),
        "points_total": total,
        "points_proper": counts["Próprio"],
        "points_improper": counts["Impróprio"],
        "points_interdicted": counts["Interditado"],
        "points_attention": counts["Atenção"],
        "points": points,
    }


def default_weather_snapshot(beach_id: str) -> WeatherSnapshot:
    return WeatherSnapshot(
        beach_id=beach_id,
        temperature_c=26.0,
        apparent_temperature_c=26.0,
        precipitation_mm=0.0,
        precipitation_probability_percent=0.0,
        wind_kmh=10.0,
        uv_index=6.0,
        wave_height_m=0.5,
        cloud_cover_percent=50.0,
    )


def build_index(
    beaches: list[dict],
    posts: list[dict],
    weather_by_beach: dict[str, WeatherSnapshot],
    bathing_rows: list[dict] | None = None,
) -> dict:
    posts_by_beach: dict[str, list[dict]] = defaultdict(list)
    for post in posts:
        posts_by_beach[post["beach_id"]].append(post)

    bathing_by_beach: dict[str, list[dict]] = defaultdict(list)
    for row in bathing_rows or []:
        bathing_by_beach[row["beach_id"]].append(row)

    beach_results = []

    for beach in beaches:
        beach_posts = posts_by_beach.get(beach["id"], [])
        sentiments = [analyze_sentiment(post["text"]) for post in beach_posts]
        sentiment_score = sum(item.score_0_100 for item in sentiments) / len(sentiments) if sentiments else 50.0
        rating_values = [float(post["rating"]) for post in beach_posts if post.get("rating")]
        rating_score = (sum(rating_values) / len(rating_values)) * 20.0
        perception_score = (sentiment_score * 0.65) + (rating_score * 0.35)

        bathing_summary = summarize_bathing_points(bathing_by_beach.get(beach["id"], []))
        bathing_status = bathing_summary["status"]
        fallback_bathing_status = ""
        if not bathing_summary["points_total"]:
            bathing_status = "Sem dado"
        bathing_penalty = bathing_index_penalty(bathing_summary, fallback_bathing_status)

        weather = weather_by_beach.get(beach["id"], default_weather_snapshot(beach["id"]))
        current_weather_score = weather_score(weather)
        current_weather_warnings = weather_warnings(weather)

        base_score = (perception_score * 0.40) + (current_weather_score * 0.60)
        final_score = clamp(base_score - bathing_penalty)

        beach_results.append(
            {
                "id": beach["id"],
                "name": beach["name"],
                "neighborhood": beach["neighborhood"],
                "city": beach.get("city", "Vitoria"),
                "coordinates": {"latitude": beach["latitude"], "longitude": beach["longitude"]},
                "index": round(final_score, 2),
                "classification": classify_index(final_score),
                "components": {
                    "public_perception": round(perception_score, 2),
                    "sentiment": round(sentiment_score, 2),
                    "ratings": round(rating_score, 2),
                    "weather": current_weather_score,
                },
                "signals": {
                    "posts_analyzed": len(beach_posts),
                    "positive_terms": sum(item.positive_hits for item in sentiments),
                    "negative_terms": sum(item.negative_hits for item in sentiments),
                    "bathing_status": bathing_status,
                    "bathing_severity": bathing_summary["severity"],
                    "bathing_proper_percent": bathing_summary["proper_percent"],
                    "bathing_bad_percent": bathing_summary["bad_percent"],
                    "bathing_points_total": bathing_summary["points_total"],
                    "bathing_points_proper": bathing_summary["points_proper"],
                    "bathing_points_improper": bathing_summary["points_improper"],
                    "bathing_points_interdicted": bathing_summary["points_interdicted"],
                    "bathing_points_attention": bathing_summary["points_attention"],
                    "bathing_index_penalty": round(bathing_penalty, 2),
                    "bathing_points": bathing_summary["points"],
                    "temperature_c": weather.temperature_c,
                    "precipitation_mm": weather.precipitation_mm,
                    "precipitation_probability_percent": weather.precipitation_probability_percent,
                    "wind_kmh": weather.wind_kmh,
                    "uv_index": weather.uv_index,
                    "wave_height_m": weather.wave_height_m,
                    "weather_warnings": current_weather_warnings,
                },
            }
        )

    beach_results.sort(key=lambda item: item["index"], reverse=True)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "method": {
            "public_perception_weight": 0.40,
            "weather_weight": 0.60,
            "bathing_penalty_if_all_points_bad": 15.0,
        },
        "beaches": beach_results,
    }


def classify_index(score: float) -> str:
    if score >= 85:
        return "Excelente"
    if score >= 70:
        return "Boa"
    if score >= 55:
        return "Regular"
    return "Atenção"
