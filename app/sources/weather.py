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
        if airport not in self._taf_cache:
            self.get_tafs([airport])
        return self._taf_cache.get(airport)

    def get_tafs(self, airports: list[str]) -> dict[str, dict | None]:
        """Fetch TAFs for many airports in a single request.

        NOAA accepts a comma-separated `ids` list, so this turns what used to be
        dozens of sequential calls into one. Results are cached per airport;
        only uncached airports trigger a network call.
        """
        wanted = [a.upper() for a in airports]
        missing = [a for a in wanted if a not in self._taf_cache]

        if missing:
            url = f"{self.base_url}/taf"
            params = {"ids": ",".join(missing), "format": "json"}
            try:
                resp = httpx.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                data = []

            by_id: dict[str, dict] = {}
            if isinstance(data, list):
                for taf in data:
                    icao = (taf.get("icaoId") or "").upper()
                    # Keep the most recent TAF if an airport appears more than once.
                    if icao and (icao not in by_id or taf.get("mostRecent")):
                        by_id[icao] = taf

            for code in missing:
                self._taf_cache[code] = by_id.get(code)

        return {a: self._taf_cache.get(a) for a in wanted}
