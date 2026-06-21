"""TAF parsing: pick the forecast segment(s) covering a flight's departure hour
and distill them into a `WeatherWindow`.

NOAA returns a TAF as a list of `fcsts` segments, each with `timeFrom`/`timeTo`
(Unix epoch seconds) plus decoded fields. A given moment can be covered by more
than one segment: a baseline `FM` segment plus a `TEMPO`/`PROB` overlay
describing possible adverse conditions. For delay-risk purposes we merge all
covering segments by worst case (lowest visibility, highest gust, any severe
weather), because those overlays are exactly the conditions that cause delays.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import WeatherWindow

# Tokens in a TAF `wxString` that indicate delay-driving severe weather.
SEVERE_WX_TOKENS = (
    "TS",     # thunderstorm
    "FZRA",   # freezing rain
    "FZDZ",   # freezing drizzle
    "GR",     # hail
    "GS",     # small hail / snow pellets
    "+SN",    # heavy snow
    "SN",     # snow
    "+RA",    # heavy rain
    "FC",     # funnel cloud / tornado
    "SQ",     # squall
    "PL",     # ice pellets
    "BLSN",   # blowing snow
)


def parse_visibility(raw: object) -> float | None:
    """NOAA `visib` may be a number, a '6+' string (meaning >6 SM), or a
    fraction like '1/2'. Returns statute miles as a float, or None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if text.endswith("+"):
        text = text[:-1]
    try:
        if "/" in text:
            num, den = text.split("/")
            return float(num) / float(den)
        return float(text)
    except (ValueError, ZeroDivisionError):
        return None


def has_severe_weather(wx_string: object) -> bool:
    if not wx_string:
        return False
    text = str(wx_string).upper()
    return any(token in text for token in SEVERE_WX_TOKENS)


def _segment_covers(segment: dict, epoch: int) -> bool:
    start = segment.get("timeFrom")
    end = segment.get("timeTo")
    if start is None or end is None:
        return False
    return start <= epoch < end


def build_weather_window(taf: dict | None, airport: str, at: datetime) -> WeatherWindow | None:
    """Select the TAF segments covering `at` and merge them by worst case."""
    if not taf or "fcsts" not in taf:
        return None

    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    epoch = int(at.timestamp())

    covering = [seg for seg in taf["fcsts"] if _segment_covers(seg, epoch)]
    if not covering:
        return None

    visibility: float | None = None
    gust: float | None = None
    severe = False
    raw_segments: list[str] = []

    for seg in covering:
        seg_vis = parse_visibility(seg.get("visib"))
        if seg_vis is not None:
            visibility = seg_vis if visibility is None else min(visibility, seg_vis)

        seg_gust = seg.get("wgst")
        # When there's no named gust, sustained wind can still be the limiting factor.
        seg_wind = seg.get("wspd")
        effective = max(v for v in (seg_gust, seg_wind) if v is not None) if (
            seg_gust is not None or seg_wind is not None
        ) else None
        if effective is not None:
            gust = float(effective) if gust is None else max(gust, float(effective))

        severe = severe or has_severe_weather(seg.get("wxString"))

        change = seg.get("fcstChange") or "BASE"
        raw_segments.append(f"{change}({seg.get('timeFrom')}-{seg.get('timeTo')})")

    return WeatherWindow(
        airport=airport.upper(),
        visibility_mi=visibility,
        wind_gust_kt=gust,
        has_severe_weather=severe,
        raw_segment=", ".join(raw_segments),
    )
