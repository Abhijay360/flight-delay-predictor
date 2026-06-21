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


class MockFlightProvider:
    """Serves cached sample departures with departure times relative to now."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file

    def get_scheduled_departures(self, airport: str, limit: int) -> list[Flight]:
        payload = json.loads(self.data_file.read_text())
        origin = payload.get("origin", airport)
        now = datetime.now(timezone.utc)

        flights: list[Flight] = []
        for record in payload["flights"][:limit]:
            scheduled_out = now + timedelta(minutes=record["depart_offset_minutes"])
            flights.append(
                Flight(
                    ident=record["ident"],
                    origin=origin,
                    destination=record["destination"],
                    scheduled_out=scheduled_out,
                    inbound_delayed=record.get("inbound_delayed", False),
                )
            )
        return flights


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
