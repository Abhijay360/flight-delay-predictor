# Flight Delay Predictor

Predicts the **risk of departure delays** for upcoming flights by joining live
aviation weather forecasts with scheduled flight data, scoring each flight, and
storing predictions so they can later be compared against actual outcomes.

It flags a flight as **High Risk of Delay** *before* the airline officially
updates its status.

## How it works

```
Flight data (mock, AeroAPI-shaped) ─┐
                                    ├─► join on (airport, departure hour) ─► risk scorer ─► predictions DB ─► API / console
NOAA TAF forecasts (live, no key) ──┘                                             │
                                                            (next day) backfill actual outcomes ─► /accuracy report
```

1. **Flight data** — `MockFlightProvider` serves ~20 cached Boston Logan
   (`KBOS`) departures with times relative to now. It implements the same
   interface as a future `AeroApiFlightProvider`, so swapping to live
   [AeroAPI](https://www.flightaware.com/commercial/aeroapi/) data is a
   one-class change.
2. **Weather data** — `NoaaWeatherClient` pulls **TAF** forecasts from the free,
   no-key [NOAA Aviation Weather Center API](https://aviationweather.gov/data/api/).
3. **TAF parsing** — `app/parsing/taf.py` selects the forecast segment(s)
   covering each flight's scheduled departure hour (handling `FM`/`TEMPO`/`PROB`
   overlays by worst case) and distills visibility, wind gusts, and severe
   weather.
4. **Risk scoring** — `RuleBasedScorer` applies a weight matrix:

   | Condition | Points |
   |---|---|
   | Visibility < 2 mi | +30 |
   | Wind gusts > 25 kt | +25 |
   | Thunderstorm / freezing precip in forecast | +40 |
   | Inbound aircraft already delayed (ripple effect) | +20 |

   Total ≥ **70** ⇒ flagged **High Risk**. The scorer is a pure function, so a
   `scikit-learn` model can replace it later without changing the pipeline.
5. **Persistence & accuracy** — predictions are stored in SQLite. The
   `actual_*` columns start empty; backfill them with real outcomes to compute
   precision/recall via `/accuracy`.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Console demo (fetches live KBOS weather, scores cached flights):
python -m app.pipeline

# Or run the API:
uvicorn app.main:app --reload
```

### API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/run?airport=KBOS` | Fetch, score, and persist predictions |
| `GET` | `/predictions?airport=KBOS` | All latest scored flights |
| `GET` | `/predictions/high-risk` | Only flights flagged high risk |
| `GET` | `/accuracy` | Precision/recall once actuals are backfilled |

## Configuration

All settings live in `app/config.py` and can be overridden with `FDP_`-prefixed
environment variables (e.g. `FDP_DEFAULT_AIRPORT=KSFO`,
`FDP_HIGH_RISK_THRESHOLD=60`).

## Tests

```bash
pytest
```

## Roadmap

- Swap `MockFlightProvider` for live AeroAPI data.
- Implement the inbound-delay ("ripple effect") lookup via tail-number tracking.
- Add a backfill job that records actual delays the following day.
- Replace the rule-based scorer with a trained `scikit-learn` model.
- Add a web dashboard.
