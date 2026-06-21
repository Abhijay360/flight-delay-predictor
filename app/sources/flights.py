"""Flight data provider.

`MockFlightProvider` reads cached departures from `data/mock_flights.json` and
shifts their times to be relative to "now" so there are always upcoming flights
to score. It implements the same `get_scheduled_departures` interface that an
`AeroApiFlightProvider` would, so swapping to live data later is a one-class
change with no pipeline rewrite.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

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


# Placeholder for the future live provider. Implement `get_scheduled_departures`
# by calling AeroAPI's /airports/{id}/flights/scheduled_departures endpoint and
# mapping each record into a `Flight`.
class AeroApiFlightProvider:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def get_scheduled_departures(self, airport: str, limit: int) -> list[Flight]:  # pragma: no cover
        raise NotImplementedError(
            "Wire up AeroAPI here once you have a key. Return the same Flight list shape."
        )


def get_default_provider() -> FlightProvider:
    return MockFlightProvider()
