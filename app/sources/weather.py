"""NOAA Aviation Weather Center client (free, no API key).

Fetches TAF (Terminal Aerodrome Forecast) data. NOAA conveniently returns the
TAF already decoded into time-bounded forecast segments (`fcsts`), so we don't
have to tokenize raw TAF strings ourselves. We cache responses per-airport for
the lifetime of a pipeline run to avoid hammering the API.
"""
from __future__ import annotations

import httpx

from app.config import settings


class NoaaWeatherClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = base_url or settings.awc_base_url
        self.timeout = timeout or settings.http_timeout
        self._taf_cache: dict[str, dict] = {}

    def get_taf(self, airport: str) -> dict | None:
        """Return the most recent decoded TAF object for an airport, or None.

        The returned dict includes a `fcsts` list of forecast segments.
        """
        airport = airport.upper()
        if airport in self._taf_cache:
            return self._taf_cache[airport]

        url = f"{self.base_url}/taf"
        params = {"ids": airport, "format": "json"}
        try:
            resp = httpx.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            self._taf_cache[airport] = None
            return None

        taf = data[0] if isinstance(data, list) and data else None
        self._taf_cache[airport] = taf
        return taf
