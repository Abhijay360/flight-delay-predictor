from datetime import datetime, timezone

from app.parsing.taf import (
    build_weather_window,
    has_severe_weather,
    parse_visibility,
)


def test_parse_visibility_plus_string():
    assert parse_visibility("6+") == 6.0


def test_parse_visibility_fraction():
    assert parse_visibility("1/2") == 0.5


def test_parse_visibility_number():
    assert parse_visibility(4) == 4.0


def test_parse_visibility_none():
    assert parse_visibility(None) is None


def test_has_severe_weather_detects_thunderstorm():
    assert has_severe_weather("-TSRA") is True


def test_has_severe_weather_detects_freezing_rain():
    assert has_severe_weather("FZRA") is True


def test_has_severe_weather_clear():
    assert has_severe_weather(None) is False
    assert has_severe_weather("") is False


def _taf_fixture() -> dict:
    # Two baseline FM segments and one PROB overlay with a thunderstorm.
    return {
        "icaoId": "KBOS",
        "fcsts": [
            {
                "timeFrom": 1000,
                "timeTo": 2000,
                "fcstChange": None,
                "wspd": 8,
                "wgst": None,
                "visib": "6+",
                "wxString": None,
            },
            {
                "timeFrom": 1500,
                "timeTo": 1800,
                "fcstChange": "PROB",
                "probability": 30,
                "wspd": None,
                "wgst": 30,
                "visib": 1,
                "wxString": "-TSRA",
            },
            {
                "timeFrom": 2000,
                "timeTo": 3000,
                "fcstChange": "FM",
                "wspd": 5,
                "wgst": None,
                "visib": "6+",
                "wxString": None,
            },
        ],
    }


def test_window_picks_clear_baseline_segment():
    at = datetime.fromtimestamp(1200, tz=timezone.utc)
    wx = build_weather_window(_taf_fixture(), "KBOS", at)
    assert wx is not None
    assert wx.visibility_mi == 6.0
    assert wx.has_severe_weather is False


def test_window_merges_overlapping_prob_overlay_by_worst_case():
    # At t=1600 both the baseline and the PROB thunderstorm overlay apply.
    at = datetime.fromtimestamp(1600, tz=timezone.utc)
    wx = build_weather_window(_taf_fixture(), "KBOS", at)
    assert wx is not None
    assert wx.visibility_mi == 1.0          # worst (lowest) visibility wins
    assert wx.wind_gust_kt == 30.0          # worst (highest) gust wins
    assert wx.has_severe_weather is True


def test_window_returns_none_when_no_segment_covers():
    at = datetime.fromtimestamp(9999, tz=timezone.utc)
    assert build_weather_window(_taf_fixture(), "KBOS", at) is None
