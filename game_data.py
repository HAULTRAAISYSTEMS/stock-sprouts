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
