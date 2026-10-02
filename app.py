"""Stock Quest — a stock-market learning game for kids (web prototype).

Quest-based game: age brackets, avatars, Fortune City hub, quests, Stock Coins,
XP levels, Money Bank. Market engine (market.py) shared with the classic
Sprouts/Traders screens, which stay available.
All money in the game is pretend money. No real trading, no real accounts.
"""

import json
import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import (Flask, g, jsonify, redirect, render_template, request,
                   session, url_for)

import market
from market import TICKERS
import game_data
from game_data import (SPROUTS_LEVELS, TRADERS_LEVELS, HEADLINES, WEATHER,
                       DIVIDEND_RATE, DIVIDEND_COOLDOWN_S, STARTING_CASH,
                       BRACKETS, BRACKET_IDS, LEVELS, QUESTS, QUIZ_Q1,
                       SORT_ITEMS, BADGES, AVATAR_PORTRAITS,
                       AVATAR_ACCESSORIES, AVATAR_FRAMES, AVATAR_A11Y,
                       MASCOTS)
from game_data import bracket_for, level_for_xp, quest_for

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
CREATE TABLE IF NOT EXISTS quests_done (
    profile_id INTEGER NOT NULL,
    quest_id TEXT NOT NULL,
    done_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, quest_id)
);
CREATE TABLE IF NOT EXISTS badges (
    profile_id INTEGER NOT NULL,
    badge_id TEXT NOT NULL,
    earned_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, badge_id)
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


def migrate():
    """Add v2 profile columns to databases created before the quest update."""
    conn = sqlite3.connect(db_path())
    cols = {r[1] for r in conn.execute("PRAGMA table_info(profiles)").fetchall()}
    for col, ddl in (("bracket", "TEXT"), ("avatar", "TEXT"),
                     ("coins", "REAL NOT NULL DEFAULT 0"),
                     ("xp", "INTEGER NOT NULL DEFAULT 0")):
        if col not in cols:
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {col} {ddl}")
    conn.commit()
    conn.close()


init_db()
migrate()


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


# ----------------------------------------------------------------------------
# Stock Quest v2 helpers: levels, badges, quest state
# ----------------------------------------------------------------------------
def grant_badge(pid, badge_id):
    """Award a badge; returns True if it is new."""
    db = get_db()
    cur = db.execute(
        "INSERT OR IGNORE INTO badges (profile_id, badge_id, earned_at) VALUES (?, ?, ?)",
        (pid, badge_id, datetime.now().isoformat()))
    db.commit()
    return cur.rowcount > 0


def add_unlock(pid, unlock_id):
    unlocks = set((get_meta(pid, "unlocks") or "").split(",")) - {""}
    if unlock_id not in unlocks:
        unlocks.add(unlock_id)
        set_meta(pid, "unlocks", ",".join(sorted(unlocks)))
        return True
    return False


def award(pid, coins=0, xp=0):
    """Add Stock Coins and XP; returns (total_coins, total_xp, level, leveled_up)."""
    db = get_db()
    before = db.execute("SELECT coins, xp FROM profiles WHERE id = ?",
                        (pid,)).fetchone()
    old_level = level_for_xp(before["xp"] or 0)["n"]
    db.execute("UPDATE profiles SET coins = coins + ?, xp = xp + ? WHERE id = ?",
               (coins, xp, pid))
    db.commit()
    row = db.execute("SELECT coins, xp FROM profiles WHERE id = ?",
                     (pid,)).fetchone()
    new_level = level_for_xp(row["xp"] or 0)
    return (row["coins"] or 0, row["xp"] or 0, new_level,
            new_level["n"] > old_level)


def quest_state(pid):
    """Everything the v2 UI needs about a player."""
    db = get_db()
    p = db.execute("SELECT * FROM profiles WHERE id = ?", (pid,)).fetchone()
    done = {r["quest_id"] for r in db.execute(
        "SELECT quest_id FROM quests_done WHERE profile_id = ?", (pid,))}
    earned = {r["badge_id"] for r in db.execute(
        "SELECT badge_id FROM badges WHERE profile_id = ?", (pid,))}
    unlocks = set((get_meta(pid, "unlocks") or "").split(",")) - {""}
    avatar = {}
    try:
        avatar = json.loads(p["avatar"] or "{}")
    except (TypeError, ValueError):
        avatar = {}
    avatar.setdefault("portrait", "age-9-12")
    avatar.setdefault("accessory", "none")
    avatar.setdefault("frame", "gold")
    if not isinstance(avatar.get("a11y"), list):
        avatar["a11y"] = []
    avatar["a11y"] = [a for a in avatar["a11y"] if a in AVATAR_A11Y]
    coins = p["coins"] or 0
    xp = p["xp"] or 0
    level = level_for_xp(xp)
    nxt = next((L for L in LEVELS if L["xp"] > xp), None)
    bank_balance = float(get_meta(pid, "bank_balance", "0") or 0)
    holdings = db.execute(
        "SELECT COUNT(*) c FROM holdings WHERE profile_id = ?", (pid,)).fetchone()["c"]
    return {
        "profile": p, "avatar": avatar, "coins": coins, "xp": xp,
        "level": level, "next_level": nxt,
        "done": done, "badges": earned, "unlocks": unlocks,
        "bank_balance": bank_balance, "holdings": holdings,
        "bracket": bracket_for(p["bracket"]) if p["bracket"] else None,
    }


def render_v2(template, p, **kw):
    """Render a v2 page with quest state injected."""
    return render_template(template, profile=p, v2=quest_state(p["id"]), **kw)


def _v2_profile_or_redirect():
    p = current_profile()
    if not p:
        return None, redirect(url_for("start"))
    return p, None


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
    p = current_profile()
    if p:
        return redirect(url_for("city"))
    return render_template("opening.html", price_mode=market.mode())


@app.get("/parents")
def parents():
    return render_template("parents.html", profile=current_profile())


@app.get("/signout")
def signout():
    session.pop("profile_id", None)
    return redirect(url_for("index"))


@app.route("/start", methods=["GET", "POST"])
def start():
    """Choose an age bracket (v2 onboarding). POSTs into /profile with bracket."""
    if request.method == "POST":
        return profile()
    return render_template("age_select.html", brackets=BRACKETS,
                           profile=current_profile())


@app.route("/profile", methods=["GET", "POST"])
def profile():
    db = get_db()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:24] or "Rookie"
        bracket_id = request.form.get("bracket") or ""
        if bracket_id in BRACKET_IDS:
            b = bracket_for(bracket_id)
            track = b["track"]
            cur = db.execute(
                "INSERT INTO profiles (name, track, bracket, cash, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, track, bracket_id, STARTING_CASH, datetime.now().isoformat()))
            db.commit()
            session["profile_id"] = cur.lastrowid
            return redirect(url_for("avatar_creator"))
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


@app.get("/avatar")
def avatar_creator():
    p = current_profile()
    if not p:
        return redirect(url_for("start"))
    st = quest_state(p["id"])
    return render_template("avatar.html", profile=p, v2=st,
                           portraits=AVATAR_PORTRAITS,
                           accessories=AVATAR_ACCESSORIES,
                           frames=AVATAR_FRAMES, a11y_opts=AVATAR_A11Y)


@app.get("/city")
def city():
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    st = quest_state(p["id"])
    quests = []
    for q in QUESTS:
        quests.append({"q": q, "done": q["id"] in st["done"]})
    districts = [
        {"id": "starter", "name": "Starter Town", "art": "starter-town.webp",
         "href": url_for("quest_intro", qid="q1"),
         "state": "done" if "q1" in st["done"] else "open",
         "sub": "BULL RUN \u2014 play to earn stock money"},
        {"id": "mart", "name": "Quest Mart", "art": "quest-mart.webp",
         "href": url_for("quest_intro", qid="q2"),
         "state": "done" if "q2" in st["done"] else "open",
         "sub": "Quest 2 · Needs vs. Wants"},
        {"id": "bank", "name": "Money Bank", "art": "money-bank.webp",
         "href": url_for("bank"),
         "state": "open" if "money-bank" in st["unlocks"] else "locked",
         "sub": "Unlocks after Quest 1"},
        {"id": "exchange", "name": "Stock Exchange", "art": "city-panorama.webp",
         "href": url_for("exchange"),
         "state": "done" if "q3" in st["done"] else "open",
         "sub": "Quest 3 · Your First Slice"},
        {"id": "academy", "name": "Skyline Academy", "art": "city-panorama.webp",
         "href": url_for("levels"),
         "state": "open", "sub": "Lessons & level progress"},
        {"id": "lab", "name": "The Lab", "art": "city-panorama.webp",
         "href": "", "state": "soon", "sub": "Experiments coming soon"},
    ]
    return render_template("city.html", profile=p, v2=st,
                           quests=quests, districts=districts)


@app.get("/quest/<qid>")
def quest_intro(qid):
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    q = quest_for(qid)
    if not q:
        return redirect(url_for("city"))
    st = quest_state(p["id"])
    step_states = []
    for s in q["steps"]:
        done = bool(s.get("done_key") and get_meta(p["id"], s["done_key"]) == "1")
        if q.get("auto") == "holding" and st["holdings"] > 0:
            done = True
        step_states.append({"s": s, "done": done})
    return render_template("quest_intro.html", profile=p, v2=st, q=q,
                           steps=step_states, done=qid in st["done"],
                           mascots=MASCOTS)


@app.get("/quest/q1/play")
def quest_catch():
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    return render_v2("quest_catch.html", p)


@app.get("/quest/q1/quiz")
def quest_quiz():
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    return render_v2("quest_quiz.html", p, quiz=QUIZ_Q1)


@app.get("/quest/q2/play")
def quest_sort():
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    return render_v2("quest_sort.html", p, items=SORT_ITEMS)


@app.get("/quest/<qid>/complete")
def quest_complete_page(qid):
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    q = quest_for(qid)
    if not q:
        return redirect(url_for("city"))
    st = quest_state(p["id"])
    return render_template("quest_complete.html", profile=p, v2=st, q=q,
                           done=qid in st["done"])


@app.get("/bank")
def bank():
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    st = quest_state(p["id"])
    if "money-bank" not in st["unlocks"]:
        return redirect(url_for("quest_intro", qid="q1"))
    return render_template("bank.html", profile=p, v2=st)


@app.get("/me")
def me():
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    st = quest_state(p["id"])
    badge_list = [{"b": b, "earned": b["id"] in st["badges"]} for b in BADGES]
    return render_template("me.html", profile=p, v2=st, badges=badge_list,
                           quests_done=len(st["done"]), quest_total=len(QUESTS))


@app.get("/exchange")
def exchange():
    p, redir = _v2_profile_or_redirect()
    if redir:
        return redir
    pf = portfolio(p["id"])
    storm_active = get_meta(p["id"], "storm_active") == "1"
    return render_v2("exchange.html", p, pf=pf, tickers=TICKERS,
                     headlines=HEADLINES, storm_active=storm_active,
                     price_mode=market.mode())


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
    storm_active = get_meta(p["id"], "storm_active") == "1"
    # Classic route now serves the Stock Exchange district (v2 art direction).
    if p["bracket"]:
        return render_v2("exchange.html", p, pf=pf, tickers=TICKERS,
                         headlines=HEADLINES, storm_active=storm_active,
                         price_mode=market.mode())
    return render_template("traders.html", profile=p, pf=pf,
                           tickers=TICKERS, headlines=HEADLINES,
                           storm_active=storm_active,
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
        grant_badge(p["id"], "storm-survivor")
        return jsonify({"ok": True, "choice": action, "v0": v0,
                        "v_storm": v_storm, "v_end": v_end,
                        "lesson": ("You held on — and the recovery did the work. "
                                   "Time in the market beats timing the market.")
                        if action == "hold" else
                        ("Panic selling locked in the loss. The storm passed, "
                         "but your money didn't get to enjoy the sunshine.")})
    return jsonify({"ok": False, "error": "Unknown storm action."}), 400


# ----------------------------------------------------------------------------
# Stock Quest v2 JSON APIs
# ----------------------------------------------------------------------------
@app.post("/api/avatar/save")
def api_avatar_save():
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    portrait = data.get("portrait") or "age-9-12"
    accessory = data.get("accessory") or "none"
    frame = data.get("frame") or "gold"
    if portrait not in AVATAR_PORTRAITS:
        portrait = "age-9-12"
    if accessory not in AVATAR_ACCESSORIES:
        accessory = "none"
    if frame not in AVATAR_FRAMES:
        frame = "gold"
    raw_a11y = data.get("a11y") or []
    if not isinstance(raw_a11y, list):
        raw_a11y = []
    a11y = [a for a in raw_a11y if a in AVATAR_A11Y]
    avatar = {"portrait": portrait, "accessory": accessory, "frame": frame,
              "a11y": a11y}
    get_db().execute("UPDATE profiles SET avatar = ? WHERE id = ?",
                     (json.dumps(avatar), p["id"]))
    get_db().commit()
    return jsonify({"ok": True, "avatar": avatar})


@app.post("/api/coins/add")
def api_coins_add():
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        amount = int(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "That number did not make sense."}), 400
    if amount <= 0 or amount > 10000:
        return jsonify({"ok": False, "error": "Pick 1–10000 coins."}), 400
    coins, xp, level, leveled = award(p["id"], coins=amount)
    return jsonify({"ok": True, "added": amount, "coins": coins,
                    "level": level["n"], "level_name": level["name"],
                    "leveled_up": leveled})


# Bull Run brand tokens: 3 of one brand in a run -> one $5 stock slice.
TOKEN_TICKERS = {"MCD", "NVDA", "RBLX", "NKE", "AAPL", "DIS"}
TOKEN_SLICE_USD = 5.0


@app.post("/api/game/catch")
def api_game_catch():
    """Bull Run results: score -> Stock Coins + pretend cash, brand tokens -> stock slices."""
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        score = max(0, int(data.get("score", 0)))
        caught = max(0, int(data.get("caught", 0)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "That score did not make sense."}), 400
    raw_tokens = data.get("tokens") or {}
    tokens = {}
    for k, v in (raw_tokens.items() if isinstance(raw_tokens, dict) else []):
        key = str(k).upper()
        if key in TOKEN_TICKERS or key == "FORTNITE":
            try:
                n = int(v)
            except (TypeError, ValueError):
                continue
            if n > 0:
                tokens[key] = min(n, 50)
    coins_earned = min(score // 10, 100)
    cash_awarded = min(score // 20, 50)
    # Daily double: the first Bull Run per calendar day earns 2x coins and 2x cash.
    today = datetime.now().date().isoformat()
    doubled = get_meta(p["id"], "bullrun_last_2x") != today
    if doubled:
        set_meta(p["id"], "bullrun_last_2x", today)
        coins_earned *= 2
        cash_awarded *= 2
    coins, xp, level, leveled = award(p["id"], coins=coins_earned)
    db = get_db()
    if cash_awarded > 0:
        db.execute("UPDATE profiles SET cash = cash + ? WHERE id = ?",
                   (cash_awarded, p["id"]))
    set_meta(p["id"], "q1_caught", "1")
    set_meta(p["id"], "q1_best", str(max(score, int(get_meta(p["id"], "q1_best", "0") or 0))))
    badge = grant_badge(p["id"], "coin-catcher") if caught >= 20 else False
    # Brand tokens -> $5 stock slices (one slice per brand that reached 3).
    prices = market.get_prices()
    brand_for = {t["ticker"]: t["brand"] for t in market.TICKERS}
    slices_earned = []
    for key, n in tokens.items():
        if key == "FORTNITE" or key not in prices or n < 3:
            continue
        price = prices[key]["price"]
        qty = TOKEN_SLICE_USD / price if price > 0 else 0
        if qty <= 0:
            continue
        db.execute("INSERT INTO holdings (profile_id, ticker, qty) VALUES (?, ?, ?) "
                   "ON CONFLICT (profile_id, ticker) DO UPDATE SET qty = qty + excluded.qty",
                   (p["id"], key, qty))
        slices_earned.append({"ticker": key, "brand": brand_for.get(key, key),
                              "qty": round(qty, 4)})
    bonus_note = None
    if tokens.get("FORTNITE"):
        # Fortnite is not publicly traded: bonus Stock Coins + teachable moment.
        coins, xp, level, leveled = award(p["id"], coins=25)
        bonus_note = ("Some companies you love aren't on the stock market "
                      "\u2014 yet! +25 bonus Stock Coins.")
    brand_badge = ("brand-collector"
                   if slices_earned and grant_badge(p["id"], "brand-collector")
                   else None)
    db.commit()
    return jsonify({"ok": True, "score": score, "caught": caught, "tokens": tokens,
                    "coins_earned": coins_earned, "coins": coins,
                    "cash_awarded": cash_awarded, "doubled": doubled,
                    "slices_earned": slices_earned, "bonus_note": bonus_note,
                    "badge": "coin-catcher" if badge else None,
                    "badge2": brand_badge})


@app.post("/api/game/sort")
def api_game_sort():
    """Quest 2 sorting results."""
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        correct = max(0, int(data.get("correct", 0)))
        total = max(1, int(data.get("total", len(SORT_ITEMS))))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "That score did not make sense."}), 400
    correct = min(correct, total)
    passed = correct >= 5
    coins_earned = min(correct * 5, 50)
    coins, xp, level, leveled = award(p["id"], coins=coins_earned)
    if passed:
        set_meta(p["id"], "q2_sorted", "1")
    return jsonify({"ok": True, "correct": correct, "total": total,
                    "passed": passed, "coins_earned": coins_earned,
                    "coins": coins})


@app.post("/api/game/quiz")
def api_game_quiz():
    """Grade the Quest 1 quiz."""
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    answers = data.get("answers") or []
    results, correct = [], 0
    for i, item in enumerate(QUIZ_Q1):
        try:
            picked = int(answers[i]) if i < len(answers) else -1
        except (TypeError, ValueError):
            picked = -1
        ok = picked == item["answer"]
        correct += 1 if ok else 0
        results.append({"correct": ok, "picked": picked,
                        "answer": item["answer"], "explain": item["explain"]})
    passed = correct >= 2
    if passed:
        set_meta(p["id"], "q1_quiz_passed", "1")
    return jsonify({"ok": True, "correct": correct, "total": len(QUIZ_Q1),
                    "passed": passed, "results": results})


def _quest_steps_done(pid, q):
    """Check whether a quest's required steps are complete."""
    if q.get("auto") == "holding":
        n = get_db().execute(
            "SELECT COUNT(*) c FROM holdings WHERE profile_id = ?", (pid,)).fetchone()["c"]
        return n > 0
    for s in q["steps"]:
        key = s.get("done_key")
        if key and get_meta(pid, key) != "1":
            return False
    return True


@app.post("/api/quest/complete")
def api_quest_complete():
    p, err = _profile_or_401()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    q = quest_for((data.get("quest_id") or "").strip())
    if not q:
        return jsonify({"ok": False, "error": "Unknown quest."}), 404
    db = get_db()
    already = db.execute(
        "SELECT 1 FROM quests_done WHERE profile_id = ? AND quest_id = ?",
        (p["id"], q["id"])).fetchone()
    if already:
        st = quest_state(p["id"])
        return jsonify({"ok": True, "already": True, "coins": st["coins"],
                        "xp": st["xp"], "level": st["level"]})
    if not _quest_steps_done(p["id"], q):
        return jsonify({"ok": False,
                        "error": "Finish the quest steps first!"}), 400
    coins, xp, level, leveled = award(p["id"], coins=q["coins"], xp=q["xp"])
    new_unlocks = [u for u in q.get("unlocks", []) if add_unlock(p["id"], u)]
    badge_new = grant_badge(p["id"], q["badge"]) if q.get("badge") else False
    db.execute("INSERT INTO quests_done (profile_id, quest_id, done_at) VALUES (?, ?, ?)",
               (p["id"], q["id"], datetime.now().isoformat()))
    db.commit()
    st = quest_state(p["id"])
    return jsonify({"ok": True, "coins_earned": q["coins"], "xp_earned": q["xp"],
                    "coins": coins, "xp": xp,
                    "level": {"n": level["n"], "name": level["name"]},
                    "leveled_up": leveled, "unlocks": new_unlocks,
                    "badge": q.get("badge") if badge_new else None,
                    "next_level": st["next_level"]})


@app.post("/api/bank/deposit")
def api_bank_deposit():
    p, err = _profile_or_401()
    if err:
        return err
    st = quest_state(p["id"])
    if "money-bank" not in st["unlocks"]:
        return jsonify({"ok": False, "error": "Finish Quest 1 to unlock the Money Bank."}), 403
    data = request.get_json(force=True, silent=True) or {}
    try:
        amount = int(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "That number did not make sense."}), 400
    if amount <= 0:
        return jsonify({"ok": False, "error": "Deposit at least 1 coin."}), 400
    if amount > st["coins"]:
        return jsonify({"ok": False, "error": "You don't have that many coins."}), 400
    db = get_db()
    db.execute("UPDATE profiles SET coins = coins - ? WHERE id = ?", (amount, p["id"]))
    db.commit()
    balance = float(get_meta(p["id"], "bank_balance", "0") or 0) + amount
    set_meta(p["id"], "bank_balance", str(balance))
    grant_badge(p["id"], "saver")
    coins = db.execute("SELECT coins FROM profiles WHERE id = ?",
                       (p["id"],)).fetchone()["coins"]
    return jsonify({"ok": True, "deposited": amount,
                    "bank_balance": balance, "coins": coins})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
