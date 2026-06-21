"""The prediction pipeline: fetch flights + weather, join on (airport, time
window), score, persist, and return the scored flights.

Run it directly for a console demo:  python -m app.pipeline
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, init_db
from app.models import Prediction, ScoredFlight
from app.parsing.taf import build_weather_window
from app.scoring.risk import get_default_scorer
from app.sources.flights import get_default_provider
from app.sources.weather import NoaaWeatherClient


def run_pipeline(
    airport: str | None = None,
    limit: int | None = None,
    persist: bool = True,
    session: Session | None = None,
) -> list[ScoredFlight]:
    airport = (airport or settings.default_airport).upper()
    limit = limit or settings.flight_limit

    flights = get_default_provider().get_scheduled_departures(airport, limit)
    weather = NoaaWeatherClient()
    scorer = get_default_scorer()

    scored: list[ScoredFlight] = []
    for flight in flights:
        origin_taf = weather.get_taf(flight.origin)
        dest_taf = weather.get_taf(flight.destination)

        origin_wx = build_weather_window(origin_taf, flight.origin, flight.scheduled_out)
        dest_wx = build_weather_window(dest_taf, flight.destination, flight.scheduled_out)

        risk = scorer.score(flight, origin_wx, dest_wx)
        scored.append(
            ScoredFlight(
                flight=flight,
                origin_weather=origin_wx,
                destination_weather=dest_wx,
                risk=risk,
            )
        )

    if persist:
        _persist(scored, session)

    return scored


def _persist(scored: list[ScoredFlight], session: Session | None) -> None:
    owns_session = session is None
    session = session or SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for sf in scored:
            session.add(
                Prediction(
                    flight_ident=sf.flight.ident,
                    origin=sf.flight.origin,
                    destination=sf.flight.destination,
                    scheduled_out=sf.flight.scheduled_out,
                    predicted_score=sf.risk.score,
                    predicted_high_risk=sf.risk.high_risk,
                    reasons="; ".join(sf.risk.reasons),
                    predicted_at=now,
                )
            )
        session.commit()
    finally:
        if owns_session:
            session.close()


def _print_report(scored: list[ScoredFlight], airport: str) -> None:
    high_risk = [s for s in scored if s.risk.high_risk]
    print(f"\nScored {len(scored)} departures out of {airport}.")
    print(f"High risk of delay: {len(high_risk)}\n")
    print(f"{'FLIGHT':<10}{'DEST':<8}{'DEPARTS (UTC)':<22}{'SCORE':<7}{'FLAG'}")
    print("-" * 60)
    for sf in sorted(scored, key=lambda s: s.risk.score, reverse=True):
        flag = "HIGH RISK" if sf.risk.high_risk else ""
        depart = sf.flight.scheduled_out.strftime("%Y-%m-%d %H:%M")
        print(f"{sf.flight.ident:<10}{sf.flight.destination:<8}{depart:<22}{sf.risk.score:<7}{flag}")
    print()
    for sf in high_risk:
        print(f"  {sf.flight.ident} -> {sf.flight.destination}: {'; '.join(sf.risk.reasons)}")


if __name__ == "__main__":
    init_db()
    results = run_pipeline()
    _print_report(results, settings.default_airport)
