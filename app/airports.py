"""Airport coordinate lookup (ICAO -> lat/lon/name).

Used to draw flight arcs on the globe. The NOAA TAF response also includes
lat/lon, so this table can be extended automatically later; for now it covers
the airports used by the mock flight dataset.
"""
from __future__ import annotations

from typing import NamedTuple


class Airport(NamedTuple):
    icao: str
    name: str
    lat: float
    lon: float


AIRPORTS: dict[str, Airport] = {
    "KBOS": Airport("KBOS", "Boston Logan", 42.3656, -71.0096),
    "KJFK": Airport("KJFK", "New York JFK", 40.6413, -73.7781),
    "KLGA": Airport("KLGA", "New York LaGuardia", 40.7769, -73.8740),
    "KEWR": Airport("KEWR", "Newark Liberty", 40.6895, -74.1745),
    "KORD": Airport("KORD", "Chicago O'Hare", 41.9742, -87.9073),
    "KATL": Airport("KATL", "Atlanta Hartsfield", 33.6407, -84.4277),
    "KSFO": Airport("KSFO", "San Francisco", 37.6213, -122.3790),
    "KLAX": Airport("KLAX", "Los Angeles", 33.9416, -118.4085),
    "KDFW": Airport("KDFW", "Dallas/Fort Worth", 32.8998, -97.0403),
    "KDTW": Airport("KDTW", "Detroit Metro", 42.2162, -83.3554),
    "KFLL": Airport("KFLL", "Fort Lauderdale", 26.0742, -80.1506),
    "KIAD": Airport("KIAD", "Washington Dulles", 38.9531, -77.4565),
    "KPHL": Airport("KPHL", "Philadelphia", 39.8744, -75.2424),
    "KMCO": Airport("KMCO", "Orlando", 28.4312, -81.3081),
    "KSLC": Airport("KSLC", "Salt Lake City", 40.7899, -111.9791),
    "KSEA": Airport("KSEA", "Seattle-Tacoma", 47.4502, -122.3088),
    "KMIA": Airport("KMIA", "Miami", 25.7959, -80.2870),
    "KDEN": Airport("KDEN", "Denver", 39.8561, -104.6737),
    "KMSP": Airport("KMSP", "Minneapolis-St. Paul", 44.8848, -93.2223),
    "KRSW": Airport("KRSW", "Fort Myers", 26.5362, -81.7552),
    "KCLT": Airport("KCLT", "Charlotte Douglas", 35.2140, -80.9431),
}


def get_airport(icao: str) -> Airport | None:
    return AIRPORTS.get(icao.upper())
