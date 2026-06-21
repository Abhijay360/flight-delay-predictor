"""Application configuration.

Tweak the defaults here (default hub, scoring thresholds, weather endpoints)
or override any of them with environment variables.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_", env_file=".env", extra="ignore")

    # Default hub airport (ICAO code). Boston Logan.
    default_airport: str = "KBOS"

    # How many upcoming departures to score per run.
    flight_limit: int = 50

    # NOAA Aviation Weather Center data API (free, no key required).
    awc_base_url: str = "https://aviationweather.gov/api/data"

    # Risk scoring weights (the "algebraic weight matrix").
    weight_low_visibility: int = 30
    weight_high_wind_gust: int = 25
    weight_severe_weather: int = 40
    weight_inbound_delayed: int = 20

    # Thresholds that trigger each weight.
    visibility_threshold_mi: float = 2.0
    wind_gust_threshold_kt: float = 25.0

    # Total score at/above which a flight is flagged "High Risk of Delay".
    high_risk_threshold: int = 70

    # SQLite database location.
    database_url: str = "sqlite:///./predictions.db"

    # Outbound HTTP timeout (seconds).
    http_timeout: float = 15.0


settings = Settings()
