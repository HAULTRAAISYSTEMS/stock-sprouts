"""Price engine for Stock Sprouts.

Two modes:
  * LIVE  - FINNHUB_API_KEY is set (and SIMULATE != "1"): quotes from Finnhub,
            cached in memory for 60 seconds.
  * SIM   - deterministic random-walk simulator, seeded per ticker and per day,
            so the game works with zero config and prices are stable within a
            day but move day to day.

Public API:
  get_prices()            -> {ticker: {ticker, brand, blurb, price, prev_close, change_pct}}
  get_history(ticker, n)  -> [{"label": "Sep 28", "close": 123.45}, ...]  (n days, oldest first)
  mode()                  -> "live" | "simulated"
"""

import hashlib
import math
import os
import random
import time
from datetime import date, datetime, timedelta

import requests

# ----------------------------------------------------------------------------
# Kid-relevant tickers: brand name + one-line kid-friendly "what they make".
# ----------------------------------------------------------------------------
TICKERS = [
    {"ticker": "RBLX",  "brand": "Roblox",      "blurb": "The game world where you build and play millions of games."},
    {"ticker": "NKE",   "brand": "Nike",        "blurb": "The sneakers and sports gear with the famous swoosh."},
    {"ticker": "MCD",   "brand": "McDonald's",  "blurb": "Burgers, fries, and the golden arches on every corner."},
    {"ticker": "DIS",   "brand": "Disney",      "blurb": "Movies, theme parks, and the magic of Mickey Mouse."},
    {"ticker": "AAPL",  "brand": "Apple",       "blurb": "iPhones, iPads, and the computers with the apple logo."},
    {"ticker": "SBUX",  "brand": "Starbucks",   "blurb": "The coffee shop with the green mermaid sign."},
    {"ticker": "TSLA",  "brand": "Tesla",       "blurb": "Electric cars that can drive themselves."},
    {"ticker": "AMZN",  "brand": "Amazon",      "blurb": "The store that delivers almost anything to your door."},
    {"ticker": "MSFT",  "brand": "Microsoft",   "blurb": "Windows, Xbox games, and Minecraft."},
    {"ticker": "NVDA",  "brand": "Nvidia",      "blurb": "The computer chips that power AI and video games."},
    {"ticker": "GOOGL", "brand": "Google",      "blurb": "Search, YouTube videos, and Android phones."},
    {"ticker": "WMT",   "brand": "Walmart",     "blurb": "The giant store where families buy everything."},
    {"ticker": "MAT",   "brand": "Mattel",      "blurb": "Hot Wheels cars and Barbie dolls."},
]

# Anchor prices for the simulator (roughly real-world scale, pretend money).
_BASE_PRICE = {
    "RBLX": 78.0, "NKE": 92.0, "MCD": 305.0, "DIS": 118.0,
    "AAPL": 238.0, "SBUX": 98.0, "TSLA": 255.0, "AMZN": 225.0,
    "MSFT": 512.0, "NVDA": 175.0, "GOOGL": 242.0, "WMT": 97.0, "MAT": 21.0,
}

_DAILY_VOL = 0.018          # ~1.8% daily wiggle
_ANNUAL_DRIFT = 0.10       # gentle long-run upward drift, like the real market
_WINDOW = 400              # days of history the walk accumulates over
_EPOCH = date(1970, 1, 1)


def _day_index(d=None):
    d = d or date.today()
    return (d - _EPOCH).days


def _seeded(ticker, day):
    h = hashlib.md5(f"stocksprouts:{ticker}:{day}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _daily_return(ticker, day):
    rng = _seeded(ticker, day)
    drift = math.log(1 + _ANNUAL_DRIFT) / 252
    return rng.gauss(drift, _DAILY_VOL)


def _sim_close(ticker, day):
    total = 0.0
    for d in range(day - _WINDOW, day + 1):
        total += _daily_return(ticker, d)
    return round(_BASE_PRICE[ticker] * math.exp(total), 2)


def _sim_live(ticker):
    """Today's close plus a tiny deterministic intraday wiggle so the
    market feels alive when a kid refreshes."""
    now = datetime.now()
    day = _day_index()
    close = _sim_close(ticker, day)
    rng = _seeded(ticker, day)
    phase = rng.random() * 2 * math.pi
    hour_frac = now.hour + now.minute / 60.0
    jitter = 0.004 * math.sin(2 * math.pi * hour_frac / 24 + phase)
    return round(close * (1 + jitter), 2)


# ----------------------------------------------------------------------------
# Finnhub live quotes (cached 60s in memory).
# ----------------------------------------------------------------------------
_FINNHUB_CACHE = {"at": 0.0, "quotes": {}}
_QUOTE_URL = "https://finnhub.io/api/v1/quote"
_CANDLE_URL = "https://finnhub.io/api/v1/stock/candle"


def _live_enabled():
    return bool(os.environ.get("FINNHUB_API_KEY")) and os.environ.get("SIMULATE", "1") != "1"


def _finnhub_quotes():
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        return None
    now = time.time()
    if _FINNHUB_CACHE["quotes"] and now - _FINNHUB_CACHE["at"] < 60:
        return _FINNHUB_CACHE["quotes"]
    quotes = {}
    for t in TICKERS:
        sym = t["ticker"]
        resp = requests.get(_QUOTE_URL, params={"symbol": sym, "token": key}, timeout=8)
        resp.raise_for_status()
        q = resp.json()
        if q.get("c"):
            quotes[sym] = {
                "price": round(float(q["c"]), 2),
                "prev_close": round(float(q.get("pc") or q["c"]), 2),
            }
    _FINNHUB_CACHE.update({"at": now, "quotes": quotes})
    return quotes


def mode():
    return "live" if _live_enabled() else "simulated"


def get_prices():
    """{ticker: {ticker, brand, blurb, price, prev_close, change_pct}}"""
    live = None
    if _live_enabled():
        try:
            live = _finnhub_quotes()
        except Exception:
            live = None  # fall back to the simulator, never break the game
    out = {}
    day = _day_index()
    for t in TICKERS:
        sym = t["ticker"]
        if live and sym in live:
            price = live[sym]["price"]
            prev = live[sym]["prev_close"]
        else:
            price = _sim_live(sym)
            prev = _sim_close(sym, day - 1)
        chg = (price - prev) / prev * 100 if prev else 0.0
        out[sym] = {
            "ticker": sym,
            "brand": t["brand"],
            "blurb": t["blurb"],
            "price": price,
            "prev_close": prev,
            "change_pct": round(chg, 2),
        }
    return out


def get_history(ticker, n=7):
    """Last n daily closes, oldest first: [{"label": "Sep 28", "close": ...}]."""
    ticker = ticker.upper()
    if ticker not in _BASE_PRICE:
        return []
    if _live_enabled():
        try:
            key = os.environ.get("FINNHUB_API_KEY")
            to_ts = int(datetime.now().timestamp())
            from_ts = to_ts - (n + 5) * 86400
            resp = requests.get(
                _CANDLE_URL,
                params={"symbol": ticker, "resolution": "D",
                        "from": from_ts, "to": to_ts, "token": key},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("s") == "ok" and data.get("c"):
                pts = sorted(zip(data["t"], data["c"]))[-n:]
                return [
                    {"label": datetime.fromtimestamp(ts).strftime("%b %d"),
                     "close": round(float(c), 2)}
                    for ts, c in pts
                ]
        except Exception:
            pass  # fall through to the simulator
    day = _day_index()
    pts = []
    for d in range(day - n + 1, day + 1):
        dt = _EPOCH + timedelta(days=d)
        pts.append({"label": dt.strftime("%b %d"), "close": _sim_close(ticker, d)})
    return pts
