import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN        = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
ADMIN_IDS        = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "-1001234567890"))
GTR_GROUP_ID     = int(os.getenv("GTR_GROUP_ID", "-1001234567891"))
GTR_CHANNEL_ID   = int(os.getenv("GTR_CHANNEL_ID", "-1001234567892"))
GTR_MASTER_WALLET = os.getenv("GTR_MASTER", "EQD-l2uSxw6HeLW3TjALtHK2tHRhamTnXa8CFf5CyVcF06zQ")
BOT_USERNAME     = os.getenv("BOT_USERNAME", "GTrustBot")
DB_PATH          = os.getenv("DB_PATH", "gtrust.db")
WEB_APP_URL      = os.getenv("WEB_APP_URL", "https://yourdomain.com")

_key = os.getenv("SECRET_KEY", "GTrustAES256KeyFor32BytesSafe!!!")
SECRET_KEY = _key.encode()[:32].ljust(32, b"0")

DAILY_BONUS    = 0.1
AD_VIEW_BONUS  = 0.001
JOIN_BONUS     = 0.001
REFERRAL_BONUS = 0.01
WIFI_SELL_FEE  = 0.05
WEEKLY_POOL    = 500.0
WEEKLY_TOP     = 100

TARIFFS = {
    "starter":  {"name": "🟢 Starter",  "ton": 0.5,  "days": 30, "views": 500},
    "standard": {"name": "🔵 Standard", "ton": 1.5,  "days": 30, "views": 2000},
    "premium":  {"name": "⭐ Premium",  "ton": 3.0,  "days": 30, "views": 99999},
}

WIFI_SPEEDS = {
    "basic":   {"name": "🟢 Basic",   "mbps": "10",   "gtr_per_hour": 0.5},
    "fast":    {"name": "🔵 Fast",    "mbps": "50",   "gtr_per_hour": 1.0},
    "ultra":   {"name": "⭐ Ultra",   "mbps": "100",  "gtr_per_hour": 2.0},
    "gigabit": {"name": "🚀 Gigabit", "mbps": "1000", "gtr_per_hour": 5.0},
}

CATEGORIES = {
    "hotel":      "🏨 Mehmonxona & Turizm",
    "restaurant": "🍽️ Restoran & Kafe",
    "shop":       "🛍️ Do'kon & Savdo",
    "beauty":     "💆 Go'zallik & Sog'liq",
    "transport":  "🚗 Transport",
    "internet":   "📡 WiFi & Internet",
    "sport":      "🏋️ Sport & Fitness",
    "education":  "🎓 Ta'lim & Kurslar",
    "home":       "🔧 Uy-joy xizmatlari",
    "pharmacy":   "💊 Dorixona",
    "tech":       "💻 Texnologiya",
    "other":      "📌 Boshqa",
}

BANNED_WORDS = [
    "spirt","alkogol","vodka","beer","pivo","wine","alcohol",
    "casino","kazino","qimor","gambling","poker","bet",
    "porn","erotica","xxx","18+","adult","sex",
    "drug","giyohvand","narkotik","heroin","kokain",
    "weapon","qurol","bomba","terrorist",
]

LANGS = {
    "uz": "🇺🇿 O'zbek",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
}
