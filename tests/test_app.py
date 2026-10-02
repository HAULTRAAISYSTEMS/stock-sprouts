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
    assert b"STOCK QUEST" in res.data
    assert b"START YOUR JOURNEY" in res.data


def test_api_prices_returns_13_tickers(client):
    res = client.get("/api/prices")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    prices = body["prices"]
    assert len(prices) == 13
    for sym, q in prices.items():
        assert q["price"] > 0
        assert "prev_close" in q and "change_pct" in q
        assert q["brand"] and q["blurb"]
    # NVDA joined the brand grid (Bull Run brand token).
    assert "NVDA" in prices
    assert "AI" in prices["NVDA"]["blurb"]


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


# ----------------------------------------------------------------------------
# Stock Quest v2: brackets, avatars, quests, bank
# ----------------------------------------------------------------------------

def _make_v2_profile(client, name="QuestKid", bracket="junior"):
    res = client.post("/profile", data={"name": name, "bracket": bracket},
                      follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/avatar")
    return res


def _profile_row(name):
    import sqlite3
    db = sqlite3.connect(app_module.db_path())
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM profiles WHERE name = ?", (name,)).fetchone()
    db.close()
    return row


def test_age_bracket_stored_and_track_mapped(client):
    _make_v2_profile(client, name="BracketKid", bracket="master")
    row = _profile_row("BracketKid")
    assert row["bracket"] == "master"
    assert row["track"] == "traders"  # 13–15 maps to the traders track

    _make_v2_profile(client, name="BracketKid2", bracket="explorer")
    row = _profile_row("BracketKid2")
    assert row["bracket"] == "explorer"
    assert row["track"] == "sprouts"

    # v2 pages render for the new profile
    res = client.get("/city")
    assert res.status_code == 200
    assert b"Fortune" in res.data


def test_avatar_save_roundtrip(client):
    _make_v2_profile(client, name="AvatarKid", bracket="junior")
    res = client.post("/api/avatar/save", json={
        "portrait": "age-13-15", "accessory": "crown", "frame": "teal",
        "a11y": ["glasses", "wheelchair", "bogus"]})
    body = res.get_json()
    assert body["ok"] is True
    assert body["avatar"] == {"portrait": "age-13-15", "accessory": "crown",
                              "frame": "teal",
                              "a11y": ["glasses", "wheelchair"]}

    row = _profile_row("AvatarKid")
    import json as _json
    saved = _json.loads(row["avatar"])
    assert saved["accessory"] == "crown"
    assert saved["a11y"] == ["glasses", "wheelchair"]

    res = client.get("/me")
    assert res.status_code == 200
    assert b"age-13-15.webp" in res.data
    assert b"a11y-glasses" in res.data
    assert b"a11y-chair" in res.data

    # invalid values fall back to safe defaults, never 500
    res = client.post("/api/avatar/save", json={
        "portrait": "nope", "accessory": "nope", "frame": "nope",
        "a11y": "not-a-list"})
    body = res.get_json()["avatar"]
    assert body["portrait"] == "age-9-12"
    assert body["a11y"] == []


def test_coin_catch_submit_awards_coins_and_badge(client):
    _make_v2_profile(client, name="CatchKid", bracket="explorer")
    res = client.post("/api/game/catch", json={"score": 250, "caught": 22})
    body = res.get_json()
    assert body["ok"] is True
    # first Bull Run of the day: daily double applies
    assert body["doubled"] is True
    assert body["coins_earned"] == 50  # (score // 10) x2
    assert body["cash_awarded"] == 24  # (score // 20) x2, pretend cash for stocks
    assert body["badge"] == "coin-catcher"

    row = _profile_row("CatchKid")
    assert row["coins"] == pytest.approx(50.0)
    assert row["cash"] == pytest.approx(1024.0)  # 1000 starting + 24

    # quest pages render
    assert client.get("/quest/q1/play").status_code == 200
    assert client.get("/quest/q1/quiz").status_code == 200
    res = client.get("/quest/q1/play")
    assert b"Bull Run" in res.data
    assert b"bullrun-splash.webp" in res.data


def test_quest_catch_exposes_avatar_url(client):
    _make_profile(client, name="AvatarKid", track="sprouts")
    res = client.get("/quest/q1/play")
    assert res.status_code == 200
    # default portrait is age-9-12; the page must expose it to the runner
    assert b'window.AVATAR_URL = "/static/img/v2/age-9-12.webp"' in res.data
    # chase-mode HUD: distance + liabilities bar, no countdown
    assert b'id="catchDist"' in res.data
    assert b'id="liabFill"' in res.data
    assert b'id="catchTime"' not in res.data


def test_quest1_completion_awards_and_unlocks_bank(client):
    _make_v2_profile(client, name="Q1Kid", bracket="junior")

    # step 1: coin catch
    res = client.post("/api/game/catch", json={"score": 120, "caught": 12})
    assert res.get_json()["ok"] is True  # 12 coins, no badge

    # step 2: quiz — all three correct
    res = client.post("/api/game/quiz", json={"answers": [0, 1, 0]})
    body = res.get_json()
    assert body["ok"] is True
    assert body["passed"] is True
    assert body["correct"] == 3

    # completing too early is blocked
    _make_v2_profile(client, name="Q1Early", bracket="junior")
    res = client.post("/api/quest/complete", json={"quest_id": "q1"})
    assert res.status_code == 400

    # now complete for real
    _make_v2_profile(client, name="Q1Kid2", bracket="junior")
    client.post("/api/game/catch", json={"score": 100, "caught": 10})
    client.post("/api/game/quiz", json={"answers": [0, 1, 0]})
    res = client.post("/api/quest/complete", json={"quest_id": "q1"})
    body = res.get_json()
    assert body["ok"] is True
    assert body["coins_earned"] == 100
    assert body["xp_earned"] == 50
    assert "money-bank" in body["unlocks"]
    assert body["badge"] == "first-steps"
    # 20 (catch, daily-double 2x) + 100 (quest) coins
    assert body["coins"] == pytest.approx(120.0)

    row = _profile_row("Q1Kid2")
    assert row["xp"] == 50

    # idempotent: no double rewards
    res = client.post("/api/quest/complete", json={"quest_id": "q1"})
    body = res.get_json()
    assert body["already"] is True
    row = _profile_row("Q1Kid2")
    assert row["coins"] == pytest.approx(120.0)

    # bank is now unlocked and accepts deposits
    res = client.get("/bank")
    assert res.status_code == 200
    assert b"Money Bank" in res.data
    res = client.post("/api/bank/deposit", json={"amount": 60})
    body = res.get_json()
    assert body["ok"] is True
    assert body["bank_balance"] == pytest.approx(60.0)
    assert body["coins"] == pytest.approx(60.0)


def test_bank_locked_before_quest1(client):
    _make_v2_profile(client, name="LockedKid", bracket="junior")
    res = client.get("/bank", follow_redirects=False)
    assert res.status_code == 302  # bounced to Quest 1
    res = client.post("/api/bank/deposit", json={"amount": 10})
    assert res.status_code == 403


def test_quest2_sort_flow(client):
    _make_v2_profile(client, name="Q2Kid", bracket="explorer")
    res = client.get("/quest/q2/play")
    assert res.status_code == 200
    assert b"Quest Mart" in res.data

    # perfect sort
    res = client.post("/api/game/sort", json={"correct": 6, "total": 6})
    body = res.get_json()
    assert body["passed"] is True
    assert body["coins_earned"] == 30

    res = client.post("/api/quest/complete", json={"quest_id": "q2"})
    body = res.get_json()
    assert body["ok"] is True
    assert body["badge"] == "smart-shopper"
    assert body["xp_earned"] == 60

    # failing sort does not set the step flag
    _make_v2_profile(client, name="Q2Fail", bracket="explorer")
    res = client.post("/api/game/sort", json={"correct": 3, "total": 6})
    assert res.get_json()["passed"] is False
    res = client.post("/api/quest/complete", json={"quest_id": "q2"})
    assert res.status_code == 400


def test_quest3_completes_when_holding_owned(client):
    _make_v2_profile(client, name="Q3Kid", bracket="wealth")
    # no holding yet -> blocked
    res = client.post("/api/quest/complete", json={"quest_id": "q3"})
    assert res.status_code == 400

    client.post("/api/buy", json={"ticker": "AAPL", "amount": 100})
    res = client.post("/api/quest/complete", json={"quest_id": "q3"})
    body = res.get_json()
    assert body["ok"] is True
    assert body["badge"] == "shareholder"
    assert body["coins_earned"] == 150


def test_exchange_renders_for_v2_profile(client):
    _make_v2_profile(client, name="ExKid", bracket="master")
    res = client.get("/exchange")
    assert res.status_code == 200
    assert b"Correction Gauntlet" in res.data
    res = client.get("/traders")
    assert res.status_code == 200
    assert b"Correction Gauntlet" in res.data


def test_mascot_names_per_approved_direction(client):
    _make_v2_profile(client, name="MascotKid", bracket="junior")
    res = client.get("/quest/q1")
    assert res.status_code == 200
    assert b"Benny Bull" in res.data
    assert b"mascot-benny-bull.webp" in res.data
    res = client.get("/quest/q2")
    assert res.status_code == 200
    assert b"Barry Bear" in res.data
    assert b"mascot-barry-bear.webp" in res.data
    # opening screen introduces both mascots by name (logged-out view)
    with client.session_transaction() as s:
        s.clear()
    res = client.get("/")
    assert res.status_code == 200
    assert b"Benny Bull" in res.data and b"Barry Bear" in res.data


def _holdings(name):
    import sqlite3
    db = sqlite3.connect(app_module.db_path())
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT ticker, qty FROM holdings WHERE profile_id = "
        "(SELECT id FROM profiles WHERE name = ?)", (name,)).fetchall()
    db.close()
    return {r["ticker"]: r["qty"] for r in rows}


def _badges(name):
    import sqlite3
    db = sqlite3.connect(app_module.db_path())
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT badge_id FROM badges WHERE profile_id = "
        "(SELECT id FROM profiles WHERE name = ?)", (name,)).fetchall()
    db.close()
    return {r["badge_id"] for r in rows}


def test_bullrun_tokens_award_stock_slice(client):
    """3 brand tokens in a run -> one $5 stock slice at the market price."""
    import market
    _make_v2_profile(client, name="TokenKid", bracket="junior")
    res = client.post("/api/game/catch",
                      json={"score": 300, "caught": 25,
                            "tokens": {"MCD": 3, "NVDA": 1}})
    body = res.get_json()
    assert body["ok"] is True
    assert body["tokens"] == {"MCD": 3, "NVDA": 1}
    # only MCD reached 3 -> exactly one slice
    assert body["slices_earned"] == [
        {"ticker": "MCD", "brand": "McDonald's",
         "qty": round(5.0 / market.get_prices()["MCD"]["price"], 4)}
    ]
    holdings = _holdings("TokenKid")
    assert "MCD" in holdings
    assert holdings["MCD"] == pytest.approx(
        5.0 / market.get_prices()["MCD"]["price"])
    assert "NVDA" not in holdings
    # brand-collector badge granted on the first slice
    assert body["badge2"] == "brand-collector"
    assert "brand-collector" in _badges("TokenKid")


def test_bullrun_fortnite_token_grants_bonus_coins_not_holdings(client):
    """Fortnite is not publicly traded: +25 Stock Coins, no holdings."""
    _make_v2_profile(client, name="FnKid", bracket="explorer")
    res = client.post("/api/game/catch",
                      json={"score": 100, "caught": 5,
                            "tokens": {"FORTNITE": 2}})
    body = res.get_json()
    assert body["ok"] is True
    assert body["slices_earned"] == []
    assert body["bonus_note"] is not None
    assert "stock market" in body["bonus_note"]
    assert _holdings("FnKid") == {}
    # 20 Stock Coins (10 x2 daily double) + 25 Fortnite bonus
    assert _profile_row("FnKid")["coins"] == pytest.approx(45.0)


def test_bullrun_cash_award_formula_and_cap(client):
    """cash_awarded = min(score // 20, 50) — real pretend cash for stocks."""
    _make_v2_profile(client, name="CashKid", bracket="junior")
    # first run of the day: doubled
    b1 = client.post("/api/game/catch",
                     json={"score": 400, "caught": 10}).get_json()
    assert b1["doubled"] is True
    assert b1["cash_awarded"] == 40
    # second run: base formula, no double
    b2 = client.post("/api/game/catch",
                     json={"score": 400, "caught": 10}).get_json()
    assert b2["doubled"] is False
    assert b2["cash_awarded"] == 20  # 400 // 20
    # huge score: capped at 50
    b3 = client.post("/api/game/catch",
                     json={"score": 2000, "caught": 10}).get_json()
    assert b3["cash_awarded"] == 50
    assert b3["coins_earned"] == 100  # score // 10 capped at 100
    assert _profile_row("CashKid")["cash"] == pytest.approx(1000 + 40 + 20 + 50)


def test_bullrun_daily_double_only_once_per_day(client):
    """2x coins and 2x cash on the first Bull Run each calendar day."""
    _make_v2_profile(client, name="DoubleKid", bracket="explorer")
    first = client.post("/api/game/catch",
                        json={"score": 100, "caught": 5}).get_json()
    second = client.post("/api/game/catch",
                         json={"score": 100, "caught": 5}).get_json()
    assert first["doubled"] is True
    assert first["coins_earned"] == 20   # (100 // 10) x2
    assert first["cash_awarded"] == 10   # (100 // 20) x2
    assert second["doubled"] is False
    assert second["coins_earned"] == 10
    assert second["cash_awarded"] == 5
