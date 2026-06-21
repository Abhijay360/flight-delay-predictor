"""Risk scoring.

`score_flight` is a pure function: given the flight plus its origin/destination
weather windows, it returns a `RiskResult`. Keeping it pure means the same call
site can later route features into a scikit-learn model instead (see
`RiskScorer` protocol) without changing the pipeline.

The default `RuleBasedScorer` implements the algebraic weight matrix:
    visibility < 2 mi        -> +30
    wind gust > 25 kt        -> +25
    thunderstorm/freezing    -> +40
    inbound aircraft delayed -> +20
A total at/above the configured threshold (default 70) flags High Risk.
"""
from __future__ import annotations

from typing import Optional, Protocol

from app.config import settings
from app.models import Flight, RiskResult, WeatherWindow


class RiskScorer(Protocol):
    def score(
        self,
        flight: Flight,
        origin_weather: Optional[WeatherWindow],
        destination_weather: Optional[WeatherWindow],
    ) -> RiskResult:
        ...


class RuleBasedScorer:
    def __init__(self, threshold: int | None = None) -> None:
        self.threshold = threshold if threshold is not None else settings.high_risk_threshold

    def _score_weather(self, wx: Optional[WeatherWindow], label: str, reasons: list[str]) -> int:
        if wx is None:
            return 0
        points = 0
        if wx.visibility_mi is not None and wx.visibility_mi < settings.visibility_threshold_mi:
            points += settings.weight_low_visibility
            reasons.append(
                f"{label}: low visibility {wx.visibility_mi:g} mi (+{settings.weight_low_visibility})"
            )
        if wx.wind_gust_kt is not None and wx.wind_gust_kt > settings.wind_gust_threshold_kt:
            points += settings.weight_high_wind_gust
            reasons.append(
                f"{label}: wind gusts {wx.wind_gust_kt:g} kt (+{settings.weight_high_wind_gust})"
            )
        if wx.has_severe_weather:
            points += settings.weight_severe_weather
            reasons.append(f"{label}: severe weather in forecast (+{settings.weight_severe_weather})")
        return points

    def score(
        self,
        flight: Flight,
        origin_weather: Optional[WeatherWindow],
        destination_weather: Optional[WeatherWindow],
    ) -> RiskResult:
        reasons: list[str] = []
        total = 0
        total += self._score_weather(origin_weather, "origin", reasons)
        total += self._score_weather(destination_weather, "destination", reasons)

        if flight.inbound_delayed:
            total += settings.weight_inbound_delayed
            reasons.append(f"inbound aircraft delayed (+{settings.weight_inbound_delayed})")

        return RiskResult(score=total, high_risk=total >= self.threshold, reasons=reasons)


def get_default_scorer() -> RiskScorer:
    return RuleBasedScorer()
