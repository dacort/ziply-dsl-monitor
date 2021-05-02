from dataclasses import dataclass
import os
from time import sleep
import argparse

import requests
from prometheus_client import Gauge, Enum, start_http_server

PIRATE_WEATHER_API_KEY = os.getenv("PIRATE_WEATHER_API_KEY")
PIRATE_WEATHER_ENDPOINT = "https://api.pirateweather.net/forecast/"
LAT_LONG = os.getenv("LAT_LONG")


@dataclass
class Weather:
    """Keep track of current weather conditions."""

    timestamp: int
    icon: str
    temperature: float
    windSpeed: float
    windGust: float
    cloudCover: float
    precipIntensity: float
    precipType: str
    uvIndex: float


def fetch_weather():
    url = f"https://api.pirateweather.net/forecast/{PIRATE_WEATHER_API_KEY}/{LAT_LONG}"
    r = requests.get(url)
    weather_data = r.json().get("currently")
    return Weather(
        timestamp=weather_data.get("time"),
        icon=weather_data.get("icon"),
        temperature=weather_data.get("temperature"),
        windSpeed=weather_data.get("windSpeed"),
        windGust=weather_data.get("windGust"),
        cloudCover=weather_data.get("cloudCover"),
        precipIntensity=weather_data.get("precipIntensity"),
        precipType=weather_data.get("precipType"),
        uvIndex=weather_data.get("uvIndex"),
    )


def poll_stats(step_seconds: int = 60 * 10):
    """
    Continuously poll the Pirate Weather API.

    You can poll less often, but the default API limits you to about once every 10 minutes.
    """
    icon = Enum(
        "outdoor_icon",
        "Outdoor icon of weather summary",
        states=[
            "clear-day",
            "clear-night",
            "rain",
            "snow",
            "sleet",
            "wind",
            "fog",
            "cloudy",
            "partly-cloudy-day",
            "partly-cloudy-night",
        ],
    )
    temp = Gauge("outdoor_temperature_f", "Outdoor Temperature F°")
    wind_speed = Gauge("outdoor_wind_speed_mph", "Outdoor Wind Speed (mph)")
    wind_gust = Gauge("outdoor_wind_gust_mph", "Outdoor Wind Gust (mph)")
    cloud_cov = Gauge("outdoor_cloud_cover_pct", "Outdoor Cloud Coverage (%)")
    precip_intensity = Gauge(
        "outdoor_precipitation_intensity", "Outdoor Precipiation Intensity"
    )
    precip_type = Enum(
        "outdoor_precipitation_type",
        "Type of precipitation",
        states=["none", "rain", "snow", "sleet"],
    )
    uvIndex = Gauge("outdoor_uv_index", "Outdoor UV Index")

    while True:
        stats = fetch_weather()
        print(stats)

        icon.state(stats.icon)
        temp.set(stats.temperature)
        wind_speed.set(stats.windSpeed)
        wind_gust.set(stats.windGust)
        cloud_cov.set(stats.cloudCover)
        precip_intensity.set(stats.precipIntensity)
        precip_type.state(stats.precipType)
        uvIndex.set(stats.uvIndex)

        sleep(step_seconds)


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor my shitty DSL.")
    parser.add_argument(
        "--serve", help="Run a Prometheus endpoint", action="store_true"
    )
    parser.add_argument(
        "--oneshot", help="Only one one data retrieval loop", action="store_true"
    )
    parser.add_argument(
        "--interval",
        help="Interval in seconds at which to poll the endpoint",
        type=int,
        default=60 * 10,
    )
    parser.add_argument(
        "--port",
        help="Port on which to run the Prometheus endpoint",
        type=int,
        default=8000,
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.oneshot:
        print(fetch_weather())
        exit()

    if args.serve:
        # Start up the server to expose the metrics.
        print(f"Starting prometheus server on port {args.port}")
        start_http_server(args.port)

    # Continuously poll the DSL server
    poll_stats(args.interval)