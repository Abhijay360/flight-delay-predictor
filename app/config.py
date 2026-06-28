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

    # --- Flight data source ---------------------------------------------------
    # "auto": prefer AirLabs, then OpenSky, then the bundled mock dataset,
    #         depending on which credentials are configured.
    # "mock" / "airlabs" / "opensky": force a specific source.
    flight_source: str = "auto"

    # AirLabs (free plan, no card): real scheduled departures + delay status.
    # Get a key at https://airlabs.co/signup ; set FDP_AIRLABS_API_KEY.
    airlabs_api_key: str = ""
    airlabs_base_url: str = "https://airlabs.co/api/v9"
    airlabs_per_hub_limit: int = 8

    # Hubs to pull departures for when scoring "all hubs".
    hubs: list[str] = [
        "KBOS", "KJFK", "KLAX", "KORD", "KATL", "KSFO", "KSEA", "KDFW", "KDEN", "KMIA",
    ]

    # OpenSky Network (free account; create an API client for these — no card).
    # Set via env: FDP_OPENSKY_CLIENT_ID / FDP_OPENSKY_CLIENT_SECRET.
    opensky_client_id: str = ""
    opensky_client_secret: str = ""
    opensky_base_url: str = "https://opensky-network.org/api"
    opensky_token_url: str = (
        "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    )
    # How far back to look for departures (OpenSky data is batch-updated nightly,
    # so recent windows are often empty; the provider walks back day-by-day).
    opensky_lookback_hours: int = 2
    opensky_max_lookback_days: int = 3
    # Cap departures kept per hub so the globe stays readable and runs stay fast.
    opensky_per_hub_limit: int = 8


settings = Settings()
