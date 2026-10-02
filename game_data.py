"""Game content for Stock Sprouts: levels, lessons, headlines, weather lines.

Level names and lessons come from the game design doc
(~/workspace/your_files/kids-stock-game-design/kids-stock-game-design.pdf).
"""

SPROUTS_LEVELS = [
    {"n": 1, "name": "Brand Hunter", "tag": "SPOT IT",
     "lesson": "Companies are real — and every one has a name you can know."},
    {"n": 2, "name": "First Slice", "tag": "OWN IT",
     "lesson": "A stock is a slice of a real company — buying one makes it partly yours."},
    {"n": 3, "name": "The Money Tree", "tag": "GROW IT",
     "lesson": "Dividends are the company's thank-you note — patience has a paycheck."},
    {"n": 4, "name": "Sunny Days, Stormy Days", "tag": "WEATHER",
     "lesson": "Prices go up AND down — down is normal, and storms always pass."},
    {"n": 5, "name": "The Whole Grove", "tag": "SPREAD IT",
     "lesson": "Don't put all your apples in one tree — spread out to survive being wrong."},
]

TRADERS_LEVELS = [
    {"n": 1, "name": "Paper Portfolio", "tag": "START",
     "lesson": "Buying is a decision with a reason, not a vibe."},
    {"n": 2, "name": "Reading the Chart", "tag": "HIGHS & LOWS",
     "lesson": "Price history and honest scorekeeping — today's high was once unthinkable."},
    {"n": 3, "name": "News Moves Markets", "tag": "HEADLINES",
     "lesson": "Prices move on expectations — early and right beats loud."},
    {"n": 4, "name": "The Correction Gauntlet", "tag": "STORM TEST",
     "lesson": "Corrections are the price of admission — time horizon is a superpower."},
    {"n": 5, "name": "Graduation Board", "tag": "REAL WORLD READY",
     "lesson": "Broad, patient, and automatic beats clever."},
]

# Kid-friendly market headlines for the Traders news game.
# Each card: a headline, the company it is about, and a 2-line "why it moved".
HEADLINES = [
    {"ticker": "RBLX",
     "headline": "Roblox says a record number of players joined this summer",
     "why": "More players can mean more Robux bought. Investors got excited about future money, so the price jumped."},
    {"ticker": "NKE",
     "headline": "Nike's new shoe sells out in one day",
     "why": "A sellout means huge demand. When a company sells everything it makes, investors expect bigger profits."},
    {"ticker": "MCD",
     "headline": "McDonald's opens its 40,000th restaurant",
     "why": "More restaurants can mean more burgers sold. Growth like this makes investors hungry for the stock."},
    {"ticker": "DIS",
     "headline": "Disney's new movie breaks opening-weekend records",
     "why": "A hit movie means ticket sales plus toys, shirts, and theme-park visits. One win feeds many businesses."},
    {"ticker": "AAPL",
     "headline": "Apple shows off a brand-new iPhone",
     "why": "New iPhones can mean a wave of upgrades. But if fans yawn, the price can fall — hype is not a guarantee."},
    {"ticker": "SBUX",
     "headline": "Starbucks adds a drink that everyone is posting about",
     "why": "A viral drink fills stores with lines out the door. Busy stores today can mean bigger sales tomorrow."},
    {"ticker": "TSLA",
     "headline": "Tesla delivers more cars than anyone expected",
     "why": "Beating expectations is the market's favorite surprise. Missing them is its least favorite — same company, different story."},
    {"ticker": "AMZN",
     "headline": "Amazon's biggest sale day ever breaks records",
     "why": "Record sales days show the store is winning. Investors pay more for a winner."},
    {"ticker": "MSFT",
     "headline": "Minecraft gets its biggest update in years",
     "why": "Big updates bring old players back — and old players spend money. Microsoft owns Minecraft, so it wins too."},
    {"ticker": "GOOGL",
     "headline": "YouTube announces a new way for creators to earn money",
     "why": "Happy creators make more videos, more videos bring more viewers, and more viewers see more ads. Google keeps a slice of every ad."},
]

WEATHER = {
    "sunny": {
        "title": "Sunny Day",
        "line": "Most prices are up! Good news made investors excited to buy.",
    },
    "cloudy": {
        "title": "Cloudy Day",
        "line": "Prices are barely moving. The market is waiting for news — and that's okay.",
    },
    "stormy": {
        "title": "Stormy Day",
        "line": "Most prices are down. Storms are normal weather — they always pass.",
    },
}

DIVIDEND_RATE = 0.002      # 0.2% of stock value per pretend dividend payout
DIVIDEND_COOLDOWN_S = 60   # seconds between payouts (prototype-friendly)
STARTING_CASH = 1000.0     # pretend dollars every kid starts with


# ----------------------------------------------------------------------------
# Stock Quest v2: brackets, levels, quests, quizzes, badges
# ----------------------------------------------------------------------------

# Age brackets (chosen at onboarding). Each maps to a market track.
BRACKETS = [
    {"id": "explorer", "label": "6–8", "name": "Money Explorers", "track": "sprouts",
     "blurb": "Start with the basics: what money is and how it grows.",
     "art": "age-6-8.webp"},
    {"id": "junior", "label": "9–12", "name": "Junior Investors", "track": "sprouts",
     "blurb": "Own slices of the brands you love and watch them move.",
     "art": "age-9-12.webp"},
    {"id": "master", "label": "13–15", "name": "Market Masters", "track": "traders",
     "blurb": "Real prices, real charts, real market weather.",
     "art": "age-13-15.webp"},
    {"id": "wealth", "label": "16–18", "name": "Future Wealth", "track": "traders",
     "blurb": "Think like an owner: corrections, compounding, the long game.",
     "art": "age-16-18.webp"},
]
BRACKET_IDS = [b["id"] for b in BRACKETS]


def bracket_for(bracket_id):
    return next((b for b in BRACKETS if b["id"] == bracket_id), BRACKETS[0])


# XP levels (progression titles, separate from age brackets).
LEVELS = [
    {"n": 1, "name": "Rookie", "xp": 0},
    {"n": 2, "name": "Riser", "xp": 200},
    {"n": 3, "name": "Builder", "xp": 500},
    {"n": 4, "name": "Mogul", "xp": 1000},
]


def level_for_xp(xp):
    lvl = LEVELS[0]
    for cand in LEVELS:
        if xp >= cand["xp"]:
            lvl = cand
    return lvl


# Mascots: keys map to art files under static/img/v2/.
MASCOTS = {
    "benny-bull": {"name": "Benny Bull", "role": "quest guide",
                   "art": "mascot-benny-bull.webp"},
    "barry-bear": {"name": "Barry Bear", "role": "money coach",
                   "art": "mascot-barry-bear.webp"},
}

# Quests: id, title, district, rewards, unlocks, badge, mascot dialogue, steps.
QUESTS = [
    {
        "id": "q1", "title": "What Is Money?", "district": "Starter Town",
        "coins": 100, "xp": 50, "unlocks": ["money-bank"], "badge": "first-steps",
        "mascot": "benny-bull",
        "tagline": "Learn what money is and how it works!",
        "dialogue": [
            ("benny-bull", "Hey! I'm Benny Bull. I'll guide you on your quests and show you how money works!"),
            ("benny-bull", "Money helps us get the things we need and the things we want. You can earn it, spend it, or save it."),
            ("benny-bull", "Your mission: run the Bull Run, snag brand tokens, then prove what you've learned. Let's go!"),
        ],
        "steps": [
            {"kind": "game", "label": "Play Bull Run to earn money for stocks!", "href": "/quest/q1/play",
             "done_key": "q1_caught", "done_label": "Bull Run played"},
            {"kind": "quiz", "label": "Complete the money quiz", "href": "/quest/q1/quiz",
             "done_key": "q1_quiz_passed", "done_label": "Quiz passed"},
        ],
    },
    {
        "id": "q2", "title": "Needs vs. Wants", "district": "Quest Mart",
        "coins": 120, "xp": 60, "unlocks": [], "badge": "smart-shopper",
        "mascot": "barry-bear",
        "tagline": "Learn the difference and make smart choices!",
        "dialogue": [
            ("barry-bear", "Welcome to Quest Mart! I'm Barry Bear, your money coach."),
            ("barry-bear", "Smart spenders know the difference between NEEDS and WANTS."),
            ("barry-bear", "Sort 6 items into the right carts — get 5 right to pass!"),
        ],
        "steps": [
            {"kind": "game", "label": "Sort 6 items into Needs or Wants", "href": "/quest/q2/play",
             "done_key": "q2_sorted", "done_label": "Sorting passed"},
        ],
    },
    {
        "id": "q3", "title": "Your First Slice", "district": "Stock Exchange",
        "coins": 150, "xp": 80, "unlocks": [], "badge": "shareholder",
        "mascot": "benny-bull",
        "tagline": "Own a slice of a real company!",
        "dialogue": [
            ("benny-bull", "Ready for the big leagues? A stock is a slice of a real company."),
            ("benny-bull", "Visit the Learn shop, spot a brand you know, and buy your first slice."),
            ("benny-bull", "Come back here when you own one — your reward is waiting!"),
        ],
        "steps": [
            {"kind": "action", "label": "Spot a brand and buy a slice in the Learn shop", "href": "/play",
             "done_key": None, "done_label": "First slice owned"},
        ],
        "auto": "holding",
    },
]


def quest_for(quest_id):
    return next((q for q in QUESTS if q["id"] == quest_id), None)


# Quest 1 quiz: 3 questions about money.
QUIZ_Q1 = [
    {"q": "What is money for?",
     "choices": ["Getting things we need and want", "Decorating your room",
                 "Feeding a pet dinosaur"],
     "answer": 0,
     "explain": "Money is a tool — it helps us get the things we need and the things we want."},
    {"q": "Which of these is EARNING money?",
     "choices": ["Buying candy", "Doing chores for allowance", "Watching TV"],
     "answer": 1,
     "explain": "Earning means money comes IN — like allowance you get for chores."},
    {"q": "Why do people SAVE money?",
     "choices": ["So it can grow for later", "Because coins are shiny",
                 "To hide it from everyone"],
     "answer": 0,
     "explain": "Saved money can grow over time — that is how small money becomes big money."},
]

# Quest 2 sorting items.
SORT_ITEMS = [
    {"name": "Water bottle", "kind": "need", "icon": "drop",
     "note": "Your body needs water every day."},
    {"name": "Apple", "kind": "need", "icon": "apple",
     "note": "Food keeps you going."},
    {"name": "House", "kind": "need", "icon": "house",
     "note": "Everyone needs a safe place to live."},
    {"name": "Sneakers", "kind": "want", "icon": "shoe",
     "note": "Cool — but your old shoes still work!"},
    {"name": "Game controller", "kind": "want", "icon": "gamepad",
     "note": "Fun — but fun can wait."},
    {"name": "Teddy bear", "kind": "want", "icon": "teddy",
     "note": "Cute — but not a need."},
]

# Badges shown on the player profile.
BADGES = [
    {"id": "first-steps", "name": "First Steps", "desc": "Completed Quest 1: What Is Money?", "icon": "star"},
    {"id": "coin-catcher", "name": "Coin Catcher", "desc": "Caught 20 coins in Bull Run", "icon": "target"},
    {"id": "brand-collector", "name": "Brand Collector", "desc": "Earned a stock slice from Bull Run brand tokens", "icon": "trophy"},
    {"id": "smart-shopper", "name": "Smart Shopper", "desc": "Completed Quest 2: Needs vs. Wants", "icon": "cart"},
    {"id": "shareholder", "name": "Shareholder", "desc": "Own a slice of a real company", "icon": "coin"},
    {"id": "saver", "name": "Super Saver", "desc": "Deposited Stock Coins in the Money Bank", "icon": "bank"},
    {"id": "storm-survivor", "name": "Storm Survivor", "desc": "Survived the Correction Gauntlet", "icon": "bolt"},
]

# Avatar creator options (portraits double as the age-bracket art).
AVATAR_PORTRAITS = ["age-6-8", "age-9-12", "age-13-15", "age-16-18"]
AVATAR_ACCESSORIES = ["none", "star", "crown", "bolt", "heart"]
AVATAR_FRAMES = ["gold", "teal", "coral", "navy"]
# Accessibility & representation options (multi-select, rendered as overlays).
AVATAR_A11Y = ["glasses", "hearing-aid", "wheelchair"]
