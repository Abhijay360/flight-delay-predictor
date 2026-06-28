"""Airport coordinate lookup (ICAO -> lat/lon/name).

Used to draw flight arcs on the globe. A static table seeds the major airports;
`remember_airport` lets the pipeline auto-learn coordinates from the NOAA TAF
response (which includes lat/lon), so adding new airports to the flight dataset
requires no manual coordinate entry.
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
    "KMDW": Airport("KMDW", "Chicago Midway", 41.7868, -87.7522),
    "KATL": Airport("KATL", "Atlanta Hartsfield", 33.6407, -84.4277),
    "KSFO": Airport("KSFO", "San Francisco", 37.6213, -122.3790),
    "KLAX": Airport("KLAX", "Los Angeles", 33.9416, -118.4085),
    "KSAN": Airport("KSAN", "San Diego", 32.7338, -117.1933),
    "KDFW": Airport("KDFW", "Dallas/Fort Worth", 32.8998, -97.0403),
    "KDAL": Airport("KDAL", "Dallas Love", 32.8471, -96.8518),
    "KIAH": Airport("KIAH", "Houston Bush", 29.9902, -95.3368),
    "KHOU": Airport("KHOU", "Houston Hobby", 29.6454, -95.2789),
    "KDTW": Airport("KDTW", "Detroit Metro", 42.2162, -83.3554),
    "KFLL": Airport("KFLL", "Fort Lauderdale", 26.0742, -80.1506),
    "KIAD": Airport("KIAD", "Washington Dulles", 38.9531, -77.4565),
    "KDCA": Airport("KDCA", "Washington Reagan", 38.8512, -77.0402),
    "KPHL": Airport("KPHL", "Philadelphia", 39.8744, -75.2424),
    "KMCO": Airport("KMCO", "Orlando", 28.4312, -81.3081),
    "KSLC": Airport("KSLC", "Salt Lake City", 40.7899, -111.9791),
    "KSEA": Airport("KSEA", "Seattle-Tacoma", 47.4502, -122.3088),
    "KMIA": Airport("KMIA", "Miami", 25.7959, -80.2870),
    "KDEN": Airport("KDEN", "Denver", 39.8561, -104.6737),
    "KMSP": Airport("KMSP", "Minneapolis-St. Paul", 44.8848, -93.2223),
    "KRSW": Airport("KRSW", "Fort Myers", 26.5362, -81.7552),
    "KCLT": Airport("KCLT", "Charlotte Douglas", 35.2140, -80.9431),
    "KPHX": Airport("KPHX", "Phoenix Sky Harbor", 33.4342, -112.0080),
    "KLAS": Airport("KLAS", "Las Vegas Harry Reid", 36.0840, -115.1537),
    "KBWI": Airport("KBWI", "Baltimore/Washington", 39.1754, -76.6683),
    "KTPA": Airport("KTPA", "Tampa", 27.9755, -82.5332),
    "KPDX": Airport("KPDX", "Portland", 45.5898, -122.5951),
    "KAUS": Airport("KAUS", "Austin-Bergstrom", 30.1975, -97.6664),
    "KBNA": Airport("KBNA", "Nashville", 36.1245, -86.6782),
    "KMCI": Airport("KMCI", "Kansas City", 39.2976, -94.7139),
    "KSTL": Airport("KSTL", "St. Louis Lambert", 38.7487, -90.3700),
    "KSJC": Airport("KSJC", "San Jose", 37.3626, -121.9291),
    "KOAK": Airport("KOAK", "Oakland", 37.7126, -122.2197),
    "KSAT": Airport("KSAT", "San Antonio", 29.5337, -98.4698),
    "KCLE": Airport("KCLE", "Cleveland Hopkins", 41.4117, -81.8498),
    "KPIT": Airport("KPIT", "Pittsburgh", 40.4915, -80.2329),
    "KIND": Airport("KIND", "Indianapolis", 39.7173, -86.2944),
    "KRDU": Airport("KRDU", "Raleigh-Durham", 35.8776, -78.7875),
    "KMEM": Airport("KMEM", "Memphis", 35.0424, -89.9767),
    "PHNL": Airport("PHNL", "Honolulu", 21.3187, -157.9224),
    "PANC": Airport("PANC", "Anchorage", 61.1743, -149.9962),
}

# ICAO -> IATA for the airports above. Used to talk to APIs (e.g. AirLabs) that
# key on IATA codes, while the rest of the system uses ICAO.
ICAO_TO_IATA: dict[str, str] = {
    "KBOS": "BOS", "KJFK": "JFK", "KLGA": "LGA", "KEWR": "EWR", "KORD": "ORD",
    "KMDW": "MDW", "KATL": "ATL", "KSFO": "SFO", "KLAX": "LAX", "KSAN": "SAN",
    "KDFW": "DFW", "KDAL": "DAL", "KIAH": "IAH", "KHOU": "HOU", "KDTW": "DTW",
    "KFLL": "FLL", "KIAD": "IAD", "KDCA": "DCA", "KPHL": "PHL", "KMCO": "MCO",
    "KSLC": "SLC", "KSEA": "SEA", "KMIA": "MIA", "KDEN": "DEN", "KMSP": "MSP",
    "KRSW": "RSW", "KCLT": "CLT", "KPHX": "PHX", "KLAS": "LAS", "KBWI": "BWI",
    "KTPA": "TPA", "KPDX": "PDX", "KAUS": "AUS", "KBNA": "BNA", "KMCI": "MCI",
    "KSTL": "STL", "KSJC": "SJC", "KOAK": "OAK", "KSAT": "SAT", "KCLE": "CLE",
    "KPIT": "PIT", "KIND": "IND", "KRDU": "RDU", "KMEM": "MEM", "PHNL": "HNL",
    "PANC": "ANC",
}
IATA_TO_ICAO: dict[str, str] = {v: k for k, v in ICAO_TO_IATA.items()}


def icao_to_iata(icao: str) -> str | None:
    return ICAO_TO_IATA.get(icao.upper())


def iata_to_icao(iata: str) -> str | None:
    return IATA_TO_ICAO.get(iata.upper())


# Coordinates discovered at runtime from the NOAA TAF response.
_LEARNED: dict[str, Airport] = {}


def remember_airport(icao: str, name: str | None, lat: float | None, lon: float | None) -> None:
    """Cache coordinates discovered from a weather response for an airport we
    don't already know about. Lets the dataset grow without manual coord entry."""
    icao = icao.upper()
    if lat is None or lon is None:
        return
    if icao in AIRPORTS or icao in _LEARNED:
        return
    _LEARNED[icao] = Airport(icao, name or icao, float(lat), float(lon))


def get_airport(icao: str) -> Airport | None:
    icao = icao.upper()
    return AIRPORTS.get(icao) or _LEARNED.get(icao)
