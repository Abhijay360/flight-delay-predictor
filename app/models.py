"""Data models.

`Pydantic` models describe the in-memory shapes that flow through the pipeline.
The `SQLAlchemy` `Prediction` model is what we persist so we can later compare
predictions against actual outcomes and report accuracy.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Flight(BaseModel):
    """A scheduled departure. Shaped to mirror AeroAPI's
    `/airports/{id}/flights/scheduled_departures` records so the real API can be
    swapped in later without touching the pipeline."""

    ident: str = Field(description="Flight identifier, e.g. 'UAL123'")
    origin: str = Field(description="Origin ICAO code, e.g. 'KBOS'")
    destination: str = Field(description="Destination ICAO code, e.g. 'KLAX'")
    scheduled_out: datetime = Field(description="Scheduled departure time (UTC)")
    inbound_delayed: bool = Field(
        default=False,
        description="Whether the inbound aircraft for this flight is already delayed (ripple effect).",
    )


class WeatherWindow(BaseModel):
    """The weather features relevant to a single flight's departure hour,
    distilled from a parsed TAF segment."""

    airport: str
    visibility_mi: Optional[float] = None
    wind_gust_kt: Optional[float] = None
    has_severe_weather: bool = False
    raw_segment: Optional[str] = Field(default=None, description="The raw TAF segment text used.")


class RiskResult(BaseModel):
    """Output of the scoring module for one flight."""

    score: int
    high_risk: bool
    reasons: list[str] = Field(default_factory=list)


class ScoredFlight(BaseModel):
    """A flight joined with its weather window and risk result."""

    flight: Flight
    origin_weather: Optional[WeatherWindow] = None
    destination_weather: Optional[WeatherWindow] = None
    risk: RiskResult


class Prediction(Base):
    """Persisted prediction. The `actual_*` columns start NULL and are filled
    in later by the backfill step, enabling an accuracy report."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_ident: Mapped[str] = mapped_column(String, index=True)
    origin: Mapped[str] = mapped_column(String, index=True)
    destination: Mapped[str] = mapped_column(String)
    scheduled_out: Mapped[datetime] = mapped_column(DateTime)

    predicted_score: Mapped[int] = mapped_column(Integer)
    predicted_high_risk: Mapped[bool] = mapped_column(Boolean)
    reasons: Mapped[str] = mapped_column(String, default="")
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Filled in later by the backfill step.
    actual_delay_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_was_delayed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
