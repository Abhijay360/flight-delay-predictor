"""FastAPI app exposing the flight delay predictor.

Endpoints:
    GET  /                     -> globe dashboard (HTML)
    GET  /info                 -> service info (JSON)
    POST /run                  -> run the pipeline (fetch, score, persist)
    GET  /predictions          -> latest scored flights for an airport
    GET  /predictions/high-risk-> only flights flagged high risk
    GET  /globe-data           -> latest predictions as globe arcs (for the dashboard)
    GET  /accuracy             -> precision/recall once actuals are backfilled

Run:  uvicorn app.main:app --reload
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.airports import get_airport
from app.config import settings
from app.db import get_session, init_db
from app.models import Prediction, ScoredFlight
from app.pipeline import run_pipeline

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Flight Delay Predictor", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/info")
def info() -> dict:
    return {
        "service": "Flight Delay Predictor",
        "default_airport": settings.default_airport,
        "high_risk_threshold": settings.high_risk_threshold,
        "endpoints": ["/run", "/predictions", "/predictions/high-risk", "/globe-data", "/accuracy"],
    }


@app.post("/run")
def run(
    airport: str = Query(default=None, description="ICAO code for one hub; omit to score all hubs"),
    limit: int = Query(default=None, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    scored: list[ScoredFlight] = run_pipeline(airport=airport, limit=limit, session=session)
    high_risk = [s for s in scored if s.risk.high_risk]
    return {
        "airport": airport.upper() if airport else "ALL_HUBS",
        "scored": len(scored),
        "high_risk": len(high_risk),
        "flights": [s.model_dump() for s in scored],
    }


def _latest_predictions(session: Session, airport: str | None, high_risk_only: bool) -> list[Prediction]:
    stmt = select(Prediction).order_by(Prediction.predicted_at.desc(), Prediction.scheduled_out)
    if airport:
        stmt = stmt.where(Prediction.origin == airport.upper())
    if high_risk_only:
        stmt = stmt.where(Prediction.predicted_high_risk.is_(True))
    return list(session.scalars(stmt).all())


@app.get("/predictions")
def predictions(
    airport: str = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    rows = _latest_predictions(session, airport, high_risk_only=False)
    return [_prediction_to_dict(r) for r in rows]


@app.get("/predictions/high-risk")
def high_risk_predictions(
    airport: str = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    rows = _latest_predictions(session, airport, high_risk_only=True)
    return [_prediction_to_dict(r) for r in rows]


def _risk_color(score: int, high_risk: bool) -> str:
    """Map a risk score to an arc color (green -> amber -> red)."""
    if high_risk:
        return "#ff3b30"  # red
    if score >= 40:
        return "#ff9500"  # amber
    if score > 0:
        return "#ffd60a"  # yellow
    return "#34c759"      # green


@app.get("/globe-data")
def globe_data(session: Session = Depends(get_session)) -> dict:
    """Return the most recent batch of predictions as globe arcs.

    Each arc connects the origin and destination airports (via the coordinate
    lookup) and carries the risk score/color for rendering and tooltips.
    """
    latest_ts = session.scalar(select(func.max(Prediction.predicted_at)))
    if latest_ts is None:
        return {"threshold": settings.high_risk_threshold, "generated_at": None, "arcs": []}

    rows = list(
        session.scalars(
            select(Prediction)
            .where(Prediction.predicted_at == latest_ts)
            .order_by(Prediction.predicted_score.desc())
        ).all()
    )

    arcs: list[dict] = []
    for r in rows:
        origin = get_airport(r.origin)
        dest = get_airport(r.destination)
        if origin is None or dest is None:
            continue
        arcs.append(
            {
                "flight_ident": r.flight_ident,
                "origin": r.origin,
                "origin_name": origin.name,
                "destination": r.destination,
                "destination_name": dest.name,
                "startLat": origin.lat,
                "startLng": origin.lon,
                "endLat": dest.lat,
                "endLng": dest.lon,
                "score": r.predicted_score,
                "high_risk": r.predicted_high_risk,
                "reasons": r.reasons,
                "color": _risk_color(r.predicted_score, r.predicted_high_risk),
                "scheduled_out": r.scheduled_out.isoformat(),
            }
        )

    return {
        "threshold": settings.high_risk_threshold,
        "generated_at": latest_ts.isoformat(),
        "arcs": arcs,
    }


@app.get("/accuracy")
def accuracy(session: Session = Depends(get_session)) -> dict:
    """Compare predictions to backfilled actual outcomes.

    Only rows whose `actual_was_delayed` has been filled in are counted.
    """
    scored = list(
        session.scalars(select(Prediction).where(Prediction.actual_was_delayed.isnot(None))).all()
    )
    if not scored:
        return {"evaluated": 0, "note": "No actual outcomes backfilled yet."}

    tp = sum(1 for r in scored if r.predicted_high_risk and r.actual_was_delayed)
    fp = sum(1 for r in scored if r.predicted_high_risk and not r.actual_was_delayed)
    fn = sum(1 for r in scored if not r.predicted_high_risk and r.actual_was_delayed)
    tn = sum(1 for r in scored if not r.predicted_high_risk and not r.actual_was_delayed)

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    accuracy_val = (tp + tn) / len(scored)

    return {
        "evaluated": len(scored),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": precision,
        "recall": recall,
        "accuracy": accuracy_val,
    }


def _prediction_to_dict(p: Prediction) -> dict:
    return {
        "flight_ident": p.flight_ident,
        "origin": p.origin,
        "destination": p.destination,
        "scheduled_out": p.scheduled_out.isoformat(),
        "predicted_score": p.predicted_score,
        "predicted_high_risk": p.predicted_high_risk,
        "reasons": p.reasons,
        "predicted_at": p.predicted_at.isoformat(),
        "actual_was_delayed": p.actual_was_delayed,
        "actual_delay_minutes": p.actual_delay_minutes,
    }
