"""Stock Sprouts — a stock-market learning game for kids (web prototype).

Tracks: Sprouts (ages 6-12) and Traders (ages 13-18).
All money in the game is pretend money. No real trading, no real accounts.
"""

import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import (Flask, g, jsonify, redirect, render_template, request,
                   session, url_for)

import market
from market import TICKERS
import game_data
from game_data import (SPROUTS_LEVELS, TRADERS_LEVELS, HEADLINES, WEATHER,
                       DIVIDEND_RATE, DIVIDEND_COOLDOWN_S, STARTING_CASH)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-stock-sprouts-key")


# ----------------------------------------------------------------------------
# Database (SQLite, zero-config)
# ----------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    track TEXT NOT NULL,
    cash REAL NOT NULL DEFAULT 1000,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS spots (
    profile_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    spotted_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, ticker)
);
CREATE TABLE IF NOT EXISTS holdings (
    profile_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    qty REAL NOT NULL,
    PRIMARY KEY (profile_id, ticker)
);
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL,
    made_at TEXT NOT NULL,
    target_date TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    correct INTEGER
);
CREATE TABLE IF NOT EXISTS meta (
    profile_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (profile_id, key)
);
"""


def db_path():
    return os.environ.get("STOCK_SPROUTS_DB") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data.db")


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(db_path())
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(db_path())
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


init_db()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def current_profile():
    pid = session.get("profile_id")
    if not pid:
        return None
    return get_db().execute("SELECT * FROM profiles WHERE id = ?", (pid,)).fetchone()


def get_meta(pid, key, default=None):
    row = get_db().execute(
        "SELECT value FROM meta WHERE profile_id = ? AND key = ?", (pid, key)).fetchone()
    return row["value"] if row else default


def set_meta(pid, key, value):
    get_db().execute(
        "INSERT INTO meta (profile_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT (profile_id, key) DO UPDATE SET value = excluded.value",
        (pid, key, str(value)))
    get_db().commit()


def bump_meta(pid, key):
    val = int(get_meta(pid, key, "0") or "0") + 1
    set_meta(pid, key, val)
    return val


def portfolio(pid):
    """Holdings valued at current prices, plus cash and day P&L."""
    db = get_db()
    prof = db.execute("SELECT * FROM profiles WHERE id = ?", (pid,)).fetchone()
    prices = market.get_prices()
    rows = db.execute(
        "SELECT ticker, qty FROM holdings WHERE profile_id = ?", (pid,)).fetchall()
    holdings, stock_value, day_pl = [], 0.0, 0.0
    for r in rows:
        q = prices.get(r["ticker"])
        if not q:
            continue
        value = q["price"] * r["qty"]
        dpl = (q["price"] - q["prev_close"]) * r["qty"]
        stock_value += value
        day_pl += dpl
        holdings.append({
            "ticker": r["ticker"], "brand": q["brand"], "blurb": q["blurb"],
            "qty": r["qty"], "price": q["price"],
            "change_pct": q["change_pct"], "value": value, "day_pl": dpl,
        })
    holdings.sort(key=lambda h: h["value"], reverse=True)
    cash = prof["cash"]
    return {"holdings": holdings, "stock_value": stock_value, "cash": cash,
            "total": cash + stock_value, "day_pl": day_pl,
            "prices": prices, "name": prof["name"], "track": prof["track"]}


def level_progress(pid):
    """Derive each level's progress from what the kid has actually done."""
    db = get_db()
    spots = db.execute(
        "SELECT COUNT(*) c FROM spots WHERE profile_id = ?", (pid,)).fetchone()["c"]
    distinct = db.execute(
        "SELECT COUNT(*) c FROM holdings WHERE profile_id = ?", (pid,)).fetchone()["c"]
    any_holding = distinct > 0
    divs = int(get_meta(pid, "dividends_count", "0") or "0")
    visited_weather = get_meta(pid, "visited_weather") == "1"
    news = int(get_meta(pid, "news_guesses", "0") or "0")
    storm_done = get_meta(pid, "storm_done") == "1"
    preds = db.execute(
        "SELECT COUNT(*) c FROM predictions WHERE profile_id = ?", (pid,)).fetchone()["c"]

    sprouts = [
        {"info": SPROUTS_LEVELS[0], "done": spots >= 10,
         "pct": min(spots, 10) / 10 * 100, "detail": f"{spots} of 10 brands spotted"},
        {"info": SPROUTS_LEVELS[1], "done": any_holding,
         "pct": 100 if any_holding else 0, "detail": "Buy your first slice" if not any_holding else "First slice owned!"},
        {"info": SPROUTS_LEVELS[2], "done": divs >= 1,
         "pct": 100 if divs >= 1 else 0, "detail": f"{divs} dividend payout collected" if divs else "Collect a dividend from your tree"},
        {"info": SPROUTS_LEVELS[3], "done": visited_weather,
         "pct": 100 if visited_weather else 0, "detail": "Visit the Market Weather page" if not visited_weather else "Weather watched!"},
        {"info": SPROUTS_LEVELS[4], "done": distinct >= 4,
         "pct": min(distinct, 4) / 4 * 100, "detail": f"{distinct} of 4 different companies owned"},
    ]
    traders = [
        {"info": TRADERS_LEVELS[0], "done": distinct >= 5,
         "pct": min(distinct, 5) / 5 * 100, "detail": f"{distinct} of 5 stocks in the portfolio"},
        {"info": TRADERS_LEVELS[1], "done": preds >= 1,
         "pct": 100 if preds >= 1 else 0, "detail": f"{preds} prediction made" if preds else "Lock in a daily prediction"},
        {"info": TRADERS_LEVELS[2], "done": news >= 3,
         "pct": min(news, 3) / 3 * 100, "detail": f"{news} of 3 headline calls made"},
        {"info": TRADERS_LEVELS[3], "done": storm_done,
         "pct": 100 if storm_done else 0, "detail": "Survive the Stormy Week simulator" if not storm_done else "Storm survived!"},
        {"info": TRADERS_LEVELS[4], "done": False,
         "pct": 0, "detail": "Finish the other boards to unlock the graduation guide"},
    ]
    return sprouts, traders


def _profile_or_401():
    p = current_profile()
    if not p:
        return None, (jsonify({"ok": False, "error": "Pick a kid profile first."}), 401)
    return p, None


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html", profile=current_profile(),
                           price_mode=market.mode())


@app.route("/profile", methods=["GET", "POST"])
def profile():
    db = get_db()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:24] or "Rookie"
        track = request.form.get("track") or "sprouts"
        if track not in ("sprouts", "traders"):
            track = "sprouts"
        cur = db.execute(
            "INSERT INTO profiles (name, track, cash, created_at) VALUES (?, ?, ?, ?)",
            (name, track, STARTING_CASH, datetime.now().isoformat()))
        db.commit()
        session["profile_id"] = cur.lastrowid
        return redirect(url_for("play" if track == "sprouts" else "traders"))
    profiles = db.execute("SELECT * FROM profiles ORDER BY id DESC").fetchall()
    return render_template("profile.html", profiles=profiles,
                           profile=current_profile())


@app.get("/play")
def play():
    p = current_profile()
    if not p:
        return redirect(url_for("profile"))
    db = get_db()
    spotted = {r["ticker"] for r in db.execute(
        "SELECT ticker FROM spots WHERE profile_id = ?", (p["id"],))}
    prices = market.get_prices()
    cards = []
    for t in TICKERS:
        q = prices[t["ticker"]]
        cards.append({"ticker": t["ticker"], "brand": t["brand"],
                      "blurb": t["blurb"], "spotted": t["ticker"] in spotted,
                      "price": q["price"], "change_pct": q["change_pct"]})
    return render_template("play.html", profile=p, cards=cards,
                           spotted_count=len(spotted), price_mode=market.mode())


@app.get("/portfolio")
def portfolio_page():
    p = current_profile()
    if not p:
        return redirect(url_for("profile"))
    pf = portfolio(p["id"])
    leaves = min(4 + 2 * len(pf["holdings"]), 16)
    return render_template("portfolio.html", profile=p, pf=pf, leaves=leaves)


@app.get("/weather")
def weather():
    p = current_profile()
    if not p:
        return redirect(url_for("profile"))
    set_meta(p["id"], "visited_weather", "1")
    prices = market.get_prices()
    avg = sum(q["change_pct"] for q in prices.values()) / len(prices)
    key = "sunny" if avg > 0.3 else "stormy" if avg < -0.3 else "cloudy"
    ups = sum(1 for q in prices.values() if q["change_pct"] > 0)
    return render_template("weather.html", profile=p, w=WEATHER[key],
                           key=key, avg=avg, ups=ups, total=len(prices))


@app.get("/traders")
def traders():
    p = current_profile()
    if not p:
        return redirect(url_for("profile"))
    pf = portfolio(p["id"])
    # latest prediction status
    db = get_db()
    pred = db.execute(
        "SELECT * FROM predictions WHERE profile_id = ? ORDER BY id DESC LIMIT 1",
        (p["id"],)).fetchone()
    pred_info = None
    if pred:
        pred_info = {"ticker": pred["ticker"], "direction": pred["direction"],
                     "target_date": pred["target_date"],
                     "resolved": bool(pred["resolved"]), "correct": pred["correct"]}
    storm_active = get_meta(p["id"], "storm_active") == "1"
    return render_template("traders.html", profile=p, pf=pf,
                           tickers=TICKERS, headlines=HEADLINES,
                           pred=pred_info, storm_active=storm_active,
                           price_mode=market.mode())


@app.get("/levels")
def levels():
    p = current_profile()
    if not p:
        return redirect(url_for("profile"))
    sprouts, traders_lv = level_progress(p["id"])
    return render_template("levels.html", profile=p,
                           sprouts=sprouts, traders_lv=traders_lv)


# ----------------------------------------------------------------------------
# JSON APIs
# ----------------------------------------------------------------------------
@app.get("/api/prices")
def api_prices():
    return jsonify({"ok": True, "mode": market.mode(),
                    "prices": market.get_prices()})


@app.get("/api/history")
def api_history():
    ticker = (request.args.get("ticker") or "AAPL").upper()
    return jsonify({"ok": True, "ticker": ticker,
                    "points": market.get_history(ticker)})


@app.post("/api/profile/select")
def api_profile_select():
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("id")
    row = get_db().execute("SELECT id FROM profiles WHERE id = ?", (pid,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Profile not found."}), 404
    session["profile_id"] = row["id"]
    return jsonify({"ok": True})


@app.post("/api/spot")
def api_spot():
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    ticker = (data.get("ticker") or "").upper()
    prices = market.get_prices()
    if ticker not in prices:
        return jsonify({"ok": False, "error": "Unknown brand."}), 400
    db = get_db()
    db.execute("INSERT OR IGNORE INTO spots (profile_id, ticker, spotted_at) "
               "VALUES (?, ?, ?)", (p["id"], ticker, datetime.now().isoformat()))
    db.commit()
    count = db.execute("SELECT COUNT(*) c FROM spots WHERE profile_id = ?",
                       (p["id"],)).fetchone()["c"]
    q = prices[ticker]
    return jsonify({"ok": True, "spotted_count": count, "card": q})


@app.post("/api/buy")
def api_buy():
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    ticker = (data.get("ticker") or "").upper()
    prices = market.get_prices()
    if ticker not in prices:
        return jsonify({"ok": False, "error": "Unknown company."}), 400
    price = prices[ticker]["price"]
    try:
        if data.get("shares"):
            qty = float(data["shares"])
            cost = qty * price
        else:
            cost = float(data.get("amount", 0))
            qty = cost / price if price > 0 else 0
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "That number did not make sense."}), 400
    if cost <= 0 or qty <= 0:
        return jsonify({"ok": False, "error": "Pick an amount greater than zero."}), 400
    db = get_db()
    prof = db.execute("SELECT cash FROM profiles WHERE id = ?", (p["id"],)).fetchone()
    if prof["cash"] < cost:
        return jsonify({"ok": False, "error": "Not enough pretend cash for that."}), 400
    db.execute("UPDATE profiles SET cash = cash - ? WHERE id = ?", (cost, p["id"]))
    db.execute("INSERT INTO holdings (profile_id, ticker, qty) VALUES (?, ?, ?) "
               "ON CONFLICT (profile_id, ticker) DO UPDATE SET qty = qty + excluded.qty",
               (p["id"], ticker, qty))
    db.commit()
    row = db.execute("SELECT qty FROM holdings WHERE profile_id = ? AND ticker = ?",
                     (p["id"], ticker)).fetchone()
    cash = db.execute("SELECT cash FROM profiles WHERE id = ?", (p["id"],)).fetchone()["cash"]
    return jsonify({"ok": True, "ticker": ticker, "qty": round(row["qty"], 4),
                    "cash": round(cash, 2)})


@app.post("/api/sell")
def api_sell():
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    ticker = (data.get("ticker") or "").upper()
    prices = market.get_prices()
    if ticker not in prices:
        return jsonify({"ok": False, "error": "Unknown company."}), 400
    try:
        qty = float(data.get("qty", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "That number did not make sense."}), 400
    if qty <= 0:
        return jsonify({"ok": False, "error": "Pick shares greater than zero."}), 400
    db = get_db()
    row = db.execute("SELECT qty FROM holdings WHERE profile_id = ? AND ticker = ?",
                     (p["id"], ticker)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "You do not own that many shares."}), 400
    holding = row["qty"]
    if holding < qty - 1e-9:
        # Tolerate a dust-sized overshoot: quantities are shown rounded to 4
        # decimals, so "sell everything I own" can arrive up to half a
        # 4th-decimal above the stored amount. Clamp to the full holding
        # instead of erroring.
        if qty - holding <= 1e-4:
            qty = holding
        else:
            return jsonify({"ok": False, "error": "You do not own that many shares."}), 400
    proceeds = qty * prices[ticker]["price"]
    new_qty = row["qty"] - qty
    if new_qty < 1e-9:
        db.execute("DELETE FROM holdings WHERE profile_id = ? AND ticker = ?",
                   (p["id"], ticker))
        new_qty = 0.0
    else:
        db.execute("UPDATE holdings SET qty = ? WHERE profile_id = ? AND ticker = ?",
                   (new_qty, p["id"], ticker))
    db.execute("UPDATE profiles SET cash = cash + ? WHERE id = ?", (proceeds, p["id"]))
    db.commit()
    return jsonify({"ok": True, "proceeds": round(proceeds, 2),
                    "remaining_qty": round(new_qty, 4)})


@app.post("/api/dividends")
def api_dividends():
    p, err = _profile_or_401()
    if err:
        return err
    last = get_meta(p["id"], "last_dividend_at")
    now = datetime.now()
    if last:
        try:
            wait = DIVIDEND_COOLDOWN_S - (now - datetime.fromisoformat(last)).total_seconds()
            if wait > 0:
                return jsonify({"ok": False, "error": f"Your tree needs a minute to grow more coins ({int(wait)}s)."}), 429
        except ValueError:
            pass
    pf = portfolio(p["id"])
    if pf["stock_value"] <= 0:
        return jsonify({"ok": False, "error": "Own a slice of a company first, then your tree can drop coins."}), 400
    payout = round(pf["stock_value"] * DIVIDEND_RATE, 2)
    db = get_db()
    db.execute("UPDATE profiles SET cash = cash + ? WHERE id = ?", (payout, p["id"]))
    db.commit()
    set_meta(p["id"], "last_dividend_at", now.isoformat())
    count = bump_meta(p["id"], "dividends_count")
    return jsonify({"ok": True, "payout": payout, "count": count})


@app.post("/api/predict")
def api_predict():
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    ticker = (data.get("ticker") or "AAPL").upper()
    direction = (data.get("direction") or "").lower()
    if ticker not in market.get_prices():
        return jsonify({"ok": False, "error": "Unknown company."}), 400
    if direction not in ("up", "down"):
        return jsonify({"ok": False, "error": "Pick up or down."}), 400
    target = (date.today() + timedelta(days=1)).isoformat()
    db = get_db()
    db.execute("INSERT INTO predictions (profile_id, ticker, direction, made_at, target_date) "
               "VALUES (?, ?, ?, ?, ?)",
               (p["id"], ticker, direction, datetime.now().isoformat(), target))
    db.commit()
    return jsonify({"ok": True, "ticker": ticker, "direction": direction,
                    "target_date": target})


@app.get("/api/prediction")
def api_prediction():
    p, err = _profile_or_401()
    if err:
        return err
    db = get_db()
    row = db.execute("SELECT * FROM predictions WHERE profile_id = ? "
                     "ORDER BY id DESC LIMIT 1", (p["id"],)).fetchone()
    if not row:
        return jsonify({"ok": True, "prediction": None})
    if not row["resolved"] and row["target_date"] <= date.today().isoformat():
        q = market.get_prices().get(row["ticker"])
        actual = "up" if q and q["change_pct"] >= 0 else "down"
        correct = 1 if actual == row["direction"] else 0
        db.execute("UPDATE predictions SET resolved = 1, correct = ? WHERE id = ?",
                   (correct, row["id"]))
        db.commit()
        row = db.execute("SELECT * FROM predictions WHERE id = ?", (row["id"],)).fetchone()
    return jsonify({"ok": True, "prediction": {
        "ticker": row["ticker"], "direction": row["direction"],
        "target_date": row["target_date"], "resolved": bool(row["resolved"]),
        "correct": row["correct"]}})


@app.post("/api/news_guess")
def api_news_guess():
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        idx = int(data.get("index", -1))
    except (TypeError, ValueError):
        idx = -1
    direction = (data.get("direction") or "").lower()
    if not (0 <= idx < len(HEADLINES)) or direction not in ("up", "down"):
        return jsonify({"ok": False, "error": "Pick a headline and a direction."}), 400
    card = HEADLINES[idx]
    q = market.get_prices().get(card["ticker"])
    actual = "up" if q and q["change_pct"] >= 0 else "down"
    count = bump_meta(p["id"], "news_guesses")
    return jsonify({"ok": True, "correct": actual == direction,
                    "actual": actual, "actual_change": q["change_pct"] if q else 0,
                    "why": card["why"], "ticker": card["ticker"],
                    "brand": q["brand"] if q else card["ticker"], "count": count})


@app.post("/api/storm")
def api_storm():
    """The Correction Gauntlet: a simulated -15% week, then Hold vs Panic Sell."""
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    action = (data.get("action") or "").lower()
    if action == "start":
        pf = portfolio(p["id"])
        if pf["total"] <= 0:
            return jsonify({"ok": False, "error": "Build a portfolio first, then brave the storm."}), 400
        set_meta(p["id"], "storm_v0", round(pf["total"], 2))
        set_meta(p["id"], "storm_active", "1")
        return jsonify({"ok": True, "v0": round(pf["total"], 2), "drop_pct": 15})
    if action in ("hold", "sell"):
        if get_meta(p["id"], "storm_active") != "1":
            return jsonify({"ok": False, "error": "Start a Stormy Week first."}), 400
        v0 = float(get_meta(p["id"], "storm_v0", "0") or "0")
        v_storm = round(v0 * 0.85, 2)
        v_end = round(v_storm * 1.12, 2) if action == "hold" else v_storm
        set_meta(p["id"], "storm_active", "0")
        set_meta(p["id"], "storm_done", "1")
        return jsonify({"ok": True, "choice": action, "v0": v0,
                        "v_storm": v_storm, "v_end": v_end,
                        "lesson": ("You held on — and the recovery did the work. "
                                   "Time in the market beats timing the market.")
                        if action == "hold" else
                        ("Panic selling locked in the loss. The storm passed, "
                         "but your money didn't get to enjoy the sunshine.")})
    return jsonify({"ok": False, "error": "Unknown storm action."}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
