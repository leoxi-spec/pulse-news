"""Live Toronto weather for the weather theme.

Open-Meteo is used because it is a public forecast API with no key. The result
is cached for ten minutes and served from the backend, so the browser never
talks to a third-party weather service.
"""
from __future__ import annotations

import json
import threading
import time
from urllib.parse import urlencode

from .httpclient import HttpClient, FetchError
from .timeutil import iso

LATITUDE = 43.6532
LONGITUDE = -79.3832
TIMEZONE = "America/Toronto"
CACHE_SECONDS = 600
_client = HttpClient()
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "data": None}

CONDITIONS = {
    "clear-day": "Clear",
    "clear-night": "Clear night",
    "partly-cloudy": "Partly cloudy",
    "cloudy": "Cloudy",
    "fog": "Fog",
    "drizzle": "Drizzle",
    "rain": "Rain",
    "heavy-rain": "Heavy rain",
    "snow": "Snow",
    "thunderstorm": "Thunderstorm",
}

ANIMATIONS = {
    "clear-day": "sun-rays",
    "clear-night": "night-sky",
    "partly-cloudy": "clouds",
    "cloudy": "clouds",
    "fog": "fog",
    "drizzle": "drizzle",
    "rain": "rain",
    "heavy-rain": "heavy-rain",
    "snow": "snow",
    "thunderstorm": "thunder",
}


def _condition(code: int, is_day: bool) -> str:
    if code in (95, 96, 99):
        return "thunderstorm"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (65, 67, 80, 81, 82):
        return "heavy-rain"
    if code in (61, 63, 66):
        return "rain"
    if code in (45, 48):
        return "fog"
    if code == 3:
        return "cloudy"
    if code in (1, 2):
        return "partly-cloudy"
    return "clear-day" if is_day else "clear-night"


def _fetch() -> dict:
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,cloud_cover,wind_speed_10m,is_day",
        "timezone": TIMEZONE,
        "forecast_days": 1,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)
    result = _client.fetch(url, accept="application/json", timeout=8, retries=1)
    if not result.ok:
        raise FetchError(f"weather HTTP {result.status}")
    payload = json.loads(result.text)
    current = payload.get("current") or {}
    if "temperature_2m" not in current or "weather_code" not in current:
        raise FetchError("weather response was incomplete")
    code = int(current["weather_code"])
    is_day = bool(int(current.get("is_day", 1)))
    condition = _condition(code, is_day)
    return {
        "available": True,
        "location": "Toronto",
        "timezone": TIMEZONE,
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "condition": condition,
        "condition_label": CONDITIONS[condition],
        "animation": ANIMATIONS[condition],
        "temperature": round(float(current["temperature_2m"]), 1),
        "feels_like": round(float(current.get("apparent_temperature", current["temperature_2m"])), 1),
        "humidity": int(current.get("relative_humidity_2m") or 0),
        "precipitation": round(float(current.get("precipitation") or 0), 1),
        "cloud_cover": int(current.get("cloud_cover") or 0),
        "wind_kmh": round(float(current.get("wind_speed_10m") or 0), 1),
        "is_day": is_day,
        "weather_code": code,
        "observed_at": current.get("time"),
        "fetched_at": iso(),
        "source": "Open-Meteo",
        "source_url": "https://open-meteo.com/",
        "stale": False,
    }


def current() -> dict:
    now = time.time()
    with _lock:
        if _cache["data"] and now - _cache["at"] < CACHE_SECONDS:
            return {**_cache["data"], "stale": False}
        try:
            data = _fetch()
            _cache["data"] = data
            _cache["at"] = now
            return data
        except Exception as exc:
            if _cache["data"]:
                return {**_cache["data"], "stale": True, "error": str(exc)}
            return {
                "available": False,
                "location": "Toronto",
                "timezone": TIMEZONE,
                "error": str(exc),
                "source": "Open-Meteo",
                "fetched_at": iso(),
            }
