"""The prediction pipeline: fetch flights + weather, join on (airport, time
window), score, persist, and return the scored flights.

Run it directly for a console demo:  python -m app.pipeline
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.airports import remember_airport
from app.config import settings
from app.db import SessionLocal, init_db
from app.models import Flight, Prediction, ScoredFlight
from app.parsing.taf import build_weather_window
from app.scoring.risk import get_default_scorer
from app.sources.flights import MockFlightProvider, active_source_label, get_default_provider
from app.sources.weather import NoaaWeatherClient


def run_pipeline(
    airport: str | None = None,
    limit: int | None = None,
    persist: bool = True,
    session: Session | None = None,
) -> list[ScoredFlight]:
    """Score upcoming departures.

    Pass an `airport` to score a single hub; pass `airport=None` to score every
    hub in the dataset. Weather for all involved airports is fetched in a single
    batched request.
    """
    provider = get_default_provider()
    if airport:
        flights: list[Flight] = provider.get_scheduled_departures(
            airport.upper(), limit or settings.flight_limit
        )
    else:
        flights = provider.get_all_departures()

    source = active_source_label()

    # Safety net: if a live source returns nothing (bad key, quota, outage),
    # fall back to the bundled sample flights so the dashboard is never blank —
    # and label the data honestly so the UI can say the live source was down.
    if not flights and not isinstance(provider, MockFlightProvider):
        source = f"{source}_fallback"
        mock = MockFlightProvider()
        flights = (
            mock.get_scheduled_departures(airport.upper(), limit or settings.flight_limit)
            if airport
            else mock.get_all_departures()
        )

    weather = NoaaWeatherClient()
    scorer = get_default_scorer()

    # One batched weather call for every airport involved (origins + destinations).
    codes = sorted({f.origin for f in flights} | {f.destination for f in flights})
    tafs = weather.get_tafs(codes)

    # Auto-learn coordinates from the weather response for any unknown airport.
    for code, taf in tafs.items():
        if taf:
            remember_airport(code, taf.get("name"), taf.get("lat"), taf.get("lon"))

    # TAFs forecast the future, so for already-departed (historical) flights we
    # assess current conditions instead of their past departure time.
    now = datetime.now(timezone.utc)

    scored: list[ScoredFlight] = []
    for flight in flights:
        wx_time = flight.scheduled_out if flight.scheduled_out > now else now
        origin_wx = build_weather_window(tafs.get(flight.origin), flight.origin, wx_time)
        dest_wx = build_weather_window(tafs.get(flight.destination), flight.destination, wx_time)

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
        _persist(scored, source, session)

    return scored


def _persist(scored: list[ScoredFlight], source: str, session: Session | None) -> None:
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
                    source=source,
                )
            )
        session.commit()
    finally:
        if owns_session:
            session.close()


def _print_report(scored: list[ScoredFlight]) -> None:
    high_risk = [s for s in scored if s.risk.high_risk]
    hubs = sorted({s.flight.origin for s in scored})
    print(f"\nScored {len(scored)} departures across {len(hubs)} hubs: {', '.join(hubs)}")
    print(f"High risk of delay: {len(high_risk)}\n")
    print(f"{'FLIGHT':<10}{'ROUTE':<14}{'DEPARTS (UTC)':<22}{'SCORE':<7}{'FLAG'}")
    print("-" * 64)
    for sf in sorted(scored, key=lambda s: s.risk.score, reverse=True):
        flag = "HIGH RISK" if sf.risk.high_risk else ""
        depart = sf.flight.scheduled_out.strftime("%Y-%m-%d %H:%M")
        route = f"{sf.flight.origin}->{sf.flight.destination}"
        print(f"{sf.flight.ident:<10}{route:<14}{depart:<22}{sf.risk.score:<7}{flag}")
    print()
    for sf in high_risk:
        print(f"  {sf.flight.ident} {sf.flight.origin}->{sf.flight.destination}: {'; '.join(sf.risk.reasons)}")


if __name__ == "__main__":
    init_db()
    results = run_pipeline()
    _print_report(results)
