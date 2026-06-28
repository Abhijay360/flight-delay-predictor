"""Flight data providers.

Two interchangeable sources implement the same interface:

* `MockFlightProvider` — bundled sample departures (no signup), times relative
  to now.
* `OpenSkyFlightProvider` — real flights (callsigns + routes) from the OpenSky
  Network REST API via OAuth2. OpenSky data is batch-updated nightly, so the
  provider walks back day-by-day to find the most recent available departures.

`get_default_provider()` picks OpenSky when credentials are configured and
falls back to the mock dataset otherwise, so the app always works.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import httpx

from app.airports import iata_to_icao, icao_to_iata
from app.config import settings
from app.models import Flight

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "mock_flights.json"


class FlightProvider(Protocol):
    def get_scheduled_departures(self, airport: str, limit: int) -> list[Flight]:
        ...

    def get_all_departures(self) -> list[Flight]:
        ...

    def get_hubs(self) -> list[str]:
        ...


class MockFlightProvider:
    """Serves cached sample departures (across multiple hubs) with departure
    times relative to now."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file

    def _load(self) -> dict:
        return json.loads(self.data_file.read_text())

    def _to_flight(self, record: dict, now: datetime, fallback_origin: str | None = None) -> Flight:
        return Flight(
            ident=record["ident"],
            origin=(record.get("origin") or fallback_origin).upper(),
            destination=record["destination"].upper(),
            scheduled_out=now + timedelta(minutes=record["depart_offset_minutes"]),
            inbound_delayed=record.get("inbound_delayed", False),
        )

    def get_hubs(self) -> list[str]:
        return [h.upper() for h in self._load().get("hubs", [])]

    def get_all_departures(self) -> list[Flight]:
        payload = self._load()
        now = datetime.now(timezone.utc)
        return [self._to_flight(r, now) for r in payload["flights"]]

    def get_scheduled_departures(self, airport: str, limit: int) -> list[Flight]:
        airport = airport.upper()
        payload = self._load()
        now = datetime.now(timezone.utc)
        flights = [
            self._to_flight(r, now, fallback_origin=airport)
            for r in payload["flights"]
            if (r.get("origin") or airport).upper() == airport
        ]
        return flights[:limit]


class OpenSkyFlightProvider:
    """Real departures from the OpenSky Network REST API (OAuth2 client creds).

    OpenSky is an ADS-B network: it reports flights that actually departed, with
    real callsigns and estimated origin/destination airports. Data is batch
    processed nightly, so we walk back day-by-day to find the most recent
    available departures for each hub.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expiry: float = 0.0

    # --- auth ---------------------------------------------------------------
    def _get_token(self) -> str | None:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        try:
            resp = httpx.post(
                settings.opensky_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
            self._token = payload["access_token"]
            self._token_expiry = time.time() + float(payload.get("expires_in", 1800))
            return self._token
        except (httpx.HTTPError, ValueError, KeyError):
            return None

    # --- fetching -----------------------------------------------------------
    def _fetch_window(self, airport: str, begin: int, end: int) -> list[dict]:
        token = self._get_token()
        if not token:
            return []
        try:
            resp = httpx.get(
                f"{settings.opensky_base_url}/flights/departure",
                params={"airport": airport, "begin": begin, "end": end},
                headers={"Authorization": f"Bearer {token}"},
                timeout=settings.http_timeout,
            )
            if resp.status_code == 404:  # OpenSky returns 404 when no flights found
                return []
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except (httpx.HTTPError, ValueError):
            return []

    def _recent_departures(self, airport: str) -> list[dict]:
        """Try today, then previous days, until a window returns data."""
        now = datetime.now(timezone.utc)
        for day_offset in range(settings.opensky_max_lookback_days + 1):
            day = (now - timedelta(days=day_offset)).date()
            end_dt = datetime(day.year, day.month, day.day, 18, 0, tzinfo=timezone.utc)
            if end_dt > now:
                end_dt = now
            begin_dt = end_dt - timedelta(hours=settings.opensky_lookback_hours)
            day_start = datetime(day.year, day.month, day.day, 0, 0, tzinfo=timezone.utc)
            if begin_dt < day_start:  # keep the window inside one UTC day
                begin_dt = day_start
            if end_dt <= begin_dt:
                continue
            records = self._fetch_window(airport, int(begin_dt.timestamp()), int(end_dt.timestamp()))
            if records:
                return records
        return []

    @staticmethod
    def _to_flight(record: dict) -> Flight | None:
        callsign = (record.get("callsign") or "").strip()
        origin = record.get("estDepartureAirport")
        destination = record.get("estArrivalAirport")
        first_seen = record.get("firstSeen")
        if not callsign or not origin or not destination or first_seen is None:
            return None
        return Flight(
            ident=callsign,
            origin=origin.upper(),
            destination=destination.upper(),
            scheduled_out=datetime.fromtimestamp(first_seen, tz=timezone.utc),
            inbound_delayed=False,  # OpenSky doesn't expose inbound-delay status
        )

    # --- interface ----------------------------------------------------------
    def get_hubs(self) -> list[str]:
        return [h.upper() for h in settings.hubs]

    def get_scheduled_departures(self, airport: str, limit: int) -> list[Flight]:
        seen: set[tuple[str, str]] = set()
        flights: list[Flight] = []
        for record in self._recent_departures(airport.upper()):
            flight = self._to_flight(record)
            if flight is None:
                continue
            key = (flight.ident, flight.destination)
            if key in seen:
                continue
            seen.add(key)
            flights.append(flight)
            if len(flights) >= limit:
                break
        return flights

    def get_all_departures(self) -> list[Flight]:
        flights: list[Flight] = []
        for hub in self.get_hubs():
            flights.extend(self.get_scheduled_departures(hub, settings.opensky_per_hub_limit))
        return flights


class AirLabsFlightProvider:
    """Real scheduled departures from the AirLabs API (free key, no card).

    AirLabs `/schedules` returns upcoming departures with scheduled times and a
    `delayed` field. It keys on IATA codes, so we translate to/from ICAO (which
    the weather + coordinate layers use).
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def get_hubs(self) -> list[str]:
        return [h.upper() for h in settings.hubs]

    def _fetch_schedules(self, dep_iata: str) -> list[dict]:
        try:
            resp = httpx.get(
                f"{settings.airlabs_base_url}/schedules",
                params={"dep_iata": dep_iata, "api_key": self.api_key},
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError):
            return []
        # AirLabs wraps results in {"response": [...]} (errors in {"error": ...}).
        if isinstance(payload, dict):
            return payload.get("response") or []
        return payload if isinstance(payload, list) else []

    @staticmethod
    def _parse_time(record: dict) -> datetime | None:
        raw = record.get("dep_time_utc") or record.get("dep_time")
        if not raw:
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _to_flight(self, record: dict, origin_icao: str) -> Flight | None:
        ident = (record.get("flight_iata") or record.get("flight_icao") or "").strip()
        # Prefer an explicit ICAO if present, else translate the IATA arrival code.
        dest_icao = (record.get("arr_icao") or "").upper() or iata_to_icao(record.get("arr_iata") or "")
        scheduled_out = self._parse_time(record)
        if not ident or not dest_icao or scheduled_out is None:
            return None
        return Flight(
            ident=ident,
            origin=origin_icao.upper(),
            destination=dest_icao,
            scheduled_out=scheduled_out,
            inbound_delayed=False,
        )

    def get_scheduled_departures(self, airport: str, limit: int) -> list[Flight]:
        iata = icao_to_iata(airport)
        if not iata:
            return []
        seen: set[tuple[str, str]] = set()
        flights: list[Flight] = []
        for record in self._fetch_schedules(iata):
            flight = self._to_flight(record, airport)
            if flight is None:
                continue
            key = (flight.ident, flight.destination)
            if key in seen:
                continue
            seen.add(key)
            flights.append(flight)
            if len(flights) >= limit:
                break
        return flights

    def get_all_departures(self) -> list[Flight]:
        flights: list[Flight] = []
        for hub in self.get_hubs():
            flights.extend(self.get_scheduled_departures(hub, settings.airlabs_per_hub_limit))
        return flights


_provider: FlightProvider | None = None


def _build_provider() -> FlightProvider:
    source = settings.flight_source
    has_airlabs = bool(settings.airlabs_api_key)
    has_opensky = bool(settings.opensky_client_id and settings.opensky_client_secret)

    if source == "mock":
        return MockFlightProvider()
    if source == "airlabs" or (source == "auto" and has_airlabs):
        if has_airlabs:
            return AirLabsFlightProvider(settings.airlabs_api_key)
    if source == "opensky" or (source == "auto" and has_opensky):
        if has_opensky:
            return OpenSkyFlightProvider(settings.opensky_client_id, settings.opensky_client_secret)
    return MockFlightProvider()


def get_default_provider() -> FlightProvider:
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def active_source_label() -> str:
    """Human-readable label for the active flight source (for the UI)."""
    provider = get_default_provider()
    if isinstance(provider, AirLabsFlightProvider):
        return "airlabs"
    if isinstance(provider, OpenSkyFlightProvider):
        return "opensky"
    return "mock"
