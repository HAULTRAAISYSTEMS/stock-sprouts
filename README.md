# Stock Sprouts

A stock-market learning game for kids — web prototype. Two tracks:

- **Sprouts (ages 6–12):** spot brands in the wild, buy pretend "slices" of real
  companies, grow a money tree that drops dividend coins, and learn market
  weather (sunny days, stormy days).
- **Traders (ages 13–18):** paper portfolio with full shares, 7-day price charts,
  daily prediction cards, headline challenges, and the Correction Gauntlet —
  a simulated -15% storm week where Hold vs. Panic Sell teaches the real lesson.

All money in the game is **pretend money**. Prices run on a built-in simulator
by default; set `FINNHUB_API_KEY` to switch to live Finnhub quotes.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000.

Optional env vars:

| Var | Effect |
| --- | ------ |
| `FINNHUB_API_KEY` | Live quotes from Finnhub (cached 60s). Without it, the deterministic simulator runs. |
| `SIMULATE` | Set to `"1"` to force the simulator even with a key present (default when no key). |
| `SECRET_KEY` | Flask session key. Defaults to a dev-only value. |
| `PORT` | Port to listen on (default 5000). |
| `STOCK_SPROUTS_DB` | SQLite path (default `./data.db`). |

Run the tests:

```bash
pytest
```

## Deploy on Render

1. Push this repo to GitHub.
2. Render dashboard → **New** → **Blueprint** → select the repo.
3. Render reads `render.yaml` (service `stock-sprouts`, gunicorn start command).
4. Optionally set `FINNHUB_API_KEY` in the Render dashboard for live prices.
   Leave it empty to keep the simulator.

## Project layout

```
app.py            Flask app: pages, game logic, JSON APIs
market.py         Price engine (Finnhub live or deterministic simulator)
game_data.py      Levels, lessons, headlines, weather lines
templates/        Jinja pages (landing, play, portfolio, weather, traders, levels)
static/css/       Kid-friendly design system (Baloo 2, chunky cards)
static/js/        Fetch helpers + page scripts
static/img/       Art from the game design doc
tests/            pytest suite
render.yaml       Render Blueprint
```
