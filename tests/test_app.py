"""pytest suite for Stock Sprouts. Run from the repo root: pytest"""

import os
import tempfile
from datetime import datetime

import pytest

# Point the app at a throwaway SQLite DB before importing it.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["STOCK_SPROUTS_DB"] = _tmp.name

import app as app_module  # noqa: E402

app_module.app.config["TESTING"] = True


@pytest.fixture(autouse=True)
def _frozen_market_time(monkeypatch):
    """Freeze the simulator's intraday clock so prices can't drift mid-test."""
    import market

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 1, 12, 0, 0)

    monkeypatch.setattr(market, "datetime", _FrozenDateTime)


@pytest.fixture()
def client():
    with app_module.app.test_client() as c:
        yield c


def _make_profile(client, name="TestKid", track="sprouts"):
    res = client.post("/profile", data={"name": name, "track": track},
                      follow_redirects=False)
    assert res.status_code == 302
    return res


def test_landing_loads(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Spot It. Own It." in res.data
    assert b"Sprouts" in res.data and b"Traders" in res.data


def test_api_prices_returns_12_tickers(client):
    res = client.get("/api/prices")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    prices = body["prices"]
    assert len(prices) == 12
    for sym, q in prices.items():
        assert q["price"] > 0
        assert "prev_close" in q and "change_pct" in q
        assert q["brand"] and q["blurb"]


def test_simulator_is_deterministic():
    import market
    a = market.get_prices()
    b = market.get_prices()
    assert a == b
    hist = market.get_history("AAPL", 7)
    assert len(hist) == 7
    assert all(p["close"] > 0 for p in hist)


def test_profile_create_and_buy_slice_flow(client):
    _make_profile(client, name="Zy", track="sprouts")

    # spot a brand
    res = client.post("/api/spot", json={"ticker": "NKE"})
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    # buy a $50 slice
    res = client.post("/api/buy", json={"ticker": "NKE", "amount": 50})
    body = res.get_json()
    assert body["ok"] is True
    assert body["cash"] == pytest.approx(950.0)

    # portfolio page shows the holding and correct math
    res = client.get("/portfolio")
    assert res.status_code == 200
    assert b"Nike" in res.data

    import market as m
    price = m.get_prices()["NKE"]["price"]
    expected_qty = 50 / price
    assert body["qty"] == pytest.approx(expected_qty, rel=1e-3)

    # cannot overspend
    res = client.post("/api/buy", json={"ticker": "NKE", "amount": 99999})
    assert res.status_code == 400

    # sell it all back
    res = client.post("/api/sell", json={"ticker": "NKE", "qty": body["qty"]})
    assert res.get_json()["ok"] is True


def test_dividends_need_holdings_and_pay_out(client):
    _make_profile(client, name="DivKid", track="sprouts")
    # no holdings yet -> 400
    res = client.post("/api/dividends")
    assert res.status_code == 400

    client.post("/api/buy", json={"ticker": "AAPL", "amount": 100})
    res = client.post("/api/dividends")
    body = res.get_json()
    assert body["ok"] is True
    assert body["payout"] > 0

    # cooldown blocks an immediate second claim
    res = client.post("/api/dividends")
    assert res.status_code == 429


def test_traders_pages_and_storm(client):
    _make_profile(client, name="Tra", track="traders")

    res = client.get("/traders")
    assert res.status_code == 200
    assert b"Correction Gauntlet" in res.data

    res = client.get("/levels")
    assert res.status_code == 200
    assert b"Brand Hunter" in res.data and b"Paper Portfolio" in res.data

    res = client.get("/weather")
    assert res.status_code == 200
    assert b"Market Weather" in res.data

    # build a portfolio, then run the storm simulator
    client.post("/api/buy", json={"ticker": "AAPL", "shares": 2})
    res = client.post("/api/storm", json={"action": "start"})
    v0 = res.get_json()["v0"]
    assert v0 > 0

    res = client.post("/api/storm", json={"action": "hold"})
    body = res.get_json()
    assert body["ok"] is True
    assert body["v_storm"] == pytest.approx(v0 * 0.85, rel=1e-2)
    assert body["v_end"] > body["v_storm"]  # holding beats panic selling

    # prediction round-trip
    res = client.post("/api/predict", json={"ticker": "AAPL", "direction": "up"})
    assert res.get_json()["ok"] is True
    res = client.get("/api/prediction")
    assert res.get_json()["prediction"]["direction"] == "up"


def test_history_endpoint(client):
    res = client.get("/api/history?ticker=MSFT")
    body = res.get_json()
    assert body["ok"] is True
    assert len(body["points"]) == 7
