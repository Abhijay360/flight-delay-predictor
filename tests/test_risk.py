from datetime import datetime, timezone

from app.models import Flight, WeatherWindow
from app.scoring.risk import RuleBasedScorer


def _flight(inbound_delayed: bool = False) -> Flight:
    return Flight(
        ident="TST1",
        origin="KBOS",
        destination="KLAX",
        scheduled_out=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        inbound_delayed=inbound_delayed,
    )


def test_clear_weather_is_low_risk():
    scorer = RuleBasedScorer()
    wx = WeatherWindow(airport="KBOS", visibility_mi=6.0, wind_gust_kt=10.0, has_severe_weather=False)
    result = scorer.score(_flight(), wx, None)
    assert result.score == 0
    assert result.high_risk is False


def test_low_visibility_adds_30():
    scorer = RuleBasedScorer()
    wx = WeatherWindow(airport="KBOS", visibility_mi=1.0)
    result = scorer.score(_flight(), wx, None)
    assert result.score == 30


def test_high_wind_gust_adds_25():
    scorer = RuleBasedScorer()
    wx = WeatherWindow(airport="KBOS", wind_gust_kt=30.0)
    result = scorer.score(_flight(), wx, None)
    assert result.score == 25


def test_severe_weather_adds_40():
    scorer = RuleBasedScorer()
    wx = WeatherWindow(airport="KBOS", has_severe_weather=True)
    result = scorer.score(_flight(), wx, None)
    assert result.score == 40


def test_inbound_delay_adds_20():
    scorer = RuleBasedScorer()
    result = scorer.score(_flight(inbound_delayed=True), None, None)
    assert result.score == 20


def test_crosses_threshold_flags_high_risk():
    scorer = RuleBasedScorer()
    # Severe weather (40) + low visibility (30) = 70 -> high risk.
    wx = WeatherWindow(airport="KBOS", visibility_mi=0.5, has_severe_weather=True)
    result = scorer.score(_flight(), wx, None)
    assert result.score == 70
    assert result.high_risk is True


def test_origin_and_destination_both_count():
    scorer = RuleBasedScorer()
    origin = WeatherWindow(airport="KBOS", wind_gust_kt=30.0)  # +25
    dest = WeatherWindow(airport="KLAX", visibility_mi=1.0)    # +30
    result = scorer.score(_flight(), origin, dest)
    assert result.score == 55
    assert result.high_risk is False
