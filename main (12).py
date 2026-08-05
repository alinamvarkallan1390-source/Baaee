#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║              🤖 Life Simulator AI — ربات بازی بله 🤖              ║
║        بازی متنی شبیه‌ساز زندگی برای پیام‌رسان بله (Bale)         ║
╠══════════════════════════════════════════════════════════════════╣
║  راه‌اندازی (گوشی / Pydroid):                                     ║
║    1) pip install requests                                        ║
║    2) ساخت ربات در بله و گرفتن Token از ربات سازنده‌ی بله        ║
║    3) در بخش «تنظیمات ربات» (خطوط اول) توکن و آیدی عددی خودت     ║
║       را بنویس:  BOT_TOKEN = "..."   MY_ADMIN_IDS = [آیدی-تو]    ║
║    4) دکمه Run ▶                                                 ║
║  روی سرور: متغیرهای BALE_BOT_TOKEN و BALE_ADMIN_IDS هم کار می‌کنند║
║                                                                  ║
║  ساختار فایل (ماژولار در قالب یک فایل):                          ║
║    [1] تنظیمات و ثابت‌ها        [6] موتور داستانی (AI)          ║
║    [2] کلاینت Bale Bot API      [7] هندلرهای بازی (منوها)        ║
║    [3] لایه دیتابیس (SQLite)    [8] پنل ادمین                     ║
║    [4] مدل‌ها و منطق بازی       [9] دیسپچر آپدیت‌ها              ║
║    [5] ابزارهای کمکی            [10] حلقه‌ی اجرای اصلی           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import random
import logging
import sqlite3
import threading
from datetime import datetime
from collections import defaultdict

import requests

# ══════════════════════════════════════════════════════════════════
# ⚙️ [1] تنظیمات ربات — مهم‌ترین بخش!
#    📱 روی گوشی (Pydroid): توکن و آیدی را همین‌جا بین کوتیشن‌ها بنویس.
#    💻 روی سرور/کامپیوتر: می‌توانی با متغیر محیطی هم مقدار بدهی.
# ══════════════════════════════════════════════════════════════════

# ایم‌جا: توکنی که ربات‌ساز بله داده را بین کوتیشن‌ها بگذار ↓
BOT_TOKEN = "1907079142:3ZbqH3BxKwIdGBttQTgOR_7TcNfRVUYZqG0"      # مثل: "1234567890:AAf3k..."

# ایم‌جا: آیدی عددی خودت در بله (برای حق ادمین) ↓
MY_ADMIN_IDS = [1975639269]                                # مثل: [123456789]

_env_tok = (os.getenv("BALE_BOT_TOKEN") or "").strip()
if _env_tok:                                       # اولویت با متغیر محیطی
    BOT_TOKEN = _env_tok
BOT_TOKEN = (BOT_TOKEN or "").strip()              # هیچ‌وقت None نمی‌شود

_env_adm = os.getenv("BALE_ADMIN_IDS") or ""
ADMIN_IDS = set(MY_ADMIN_IDS or []) | {int(x) for x in _env_adm.replace(" ", "").split(",") if x.isdigit()}

# مسیر دیتابیس — سازگار با حالت اجرای موبایل (Pydroid)
try:
    _HERE = os.path.dirname(os.path.abspath(__file__ or ""))
    if not os.path.isdir(_HERE):
        raise ValueError
except Exception:
    _HERE = os.getcwd()
DB_PATH = (os.getenv("LIFE_SIM_DB") or "").strip() or os.path.join(_HERE, "life_simulator.db")

RATE_LIMIT        = 30      # حداکثر اکشن در دقیقه برای هر کاربر (ضد اسپم/تقلب)
WORK_COOLDOWN     = 45      # ثانیه — فاصله بین دو شیفت کاری
REST_COOLDOWN     = 60      # ثانیه — فاصله بین دو استراحت
EVENT_ENERGY_COST = 10
WORK_ENERGY_COST  = 20
TRAIN_ENERGY_COST = 15

# ── تنظیمات سیستم‌های جدید (بازار / جنگ / VIP) ──
MARKET_INTERVAL     = 1200  # ثانیه — قیمت‌های بازار هر ۲۰ دقیقه عوض می‌شوند
TRADE_FEE           = 0.02  # کارمزد خرید/فروش بازار (۲٪)
ATTACK_COOLDOWN     = 300   # ثانیه — فاصله بین دو حمله
ATTACK_ENERGY_COST  = 25
BOSS_GEMS_REWARD    = 5     # سکه طلای جایزه‌ی باسِ روزانه

# 💳 درآمد تو: شماره کارتی که کاربر به آن واریز می‌کند (ادمین می‌تواند از پنل هم عوضش کند)
OWNER_CARD_NUM = "6037-0000-0000-0000"      # ← شماره کارت خودت را اینجا بگذار
# 📡 کانال اخبار: آیدی کانال (ادمین از پنل هم می‌تواند تنظیم کند). ربات باید ادمین کانال باشد!
CHANNEL_DEFAULT = ""                        # ← مثل: "@mynewschannel" یا "-1001234567890"

# 💎 بسته‌های سکه طلا (پول واقعی → سکه → درآمد صاحب ربات)
#    (شناسه, عنوان, تعداد سکه, قیمت به تومان)
GEM_PACKS = [
    ("p1", "💎 ۱۰۰ سکه طلا",              100, 50_000),
    ("p2", "💎 ۲۵۰ سکه طلا",              250, 100_000),
    ("p3", "💎 ۶۵۰ سکه طلا ⭐ پرفروش",     650, 200_000),
]

# 🏪 دارایی‌های بازار (بورس) — (نماد, نام, قیمت پایه)
SEED_MARKETS = [
    ("gold",  "🥇 طلا",        5000),
    ("usd",   "💵 دلار",       6000),
    ("bale",  "🪙 بله‌کوین",   2500),
    ("oil",   "🛢 نفت",        3000),
    ("btc",   "₿ بیت‌کوین",    50000),
    ("eth",   "⟠ اتریوم",      20000),
    ("steel", "🏭 سهام فولاد",  4000),
    ("petro", "⛽ سهام پترو",   3500),
    ("land",  "🏞 زمین",       45000),
    ("silver","🥈 نقره",       2500),
]
MARKET_BASE = {s: p for s, _, p in SEED_MARKETS}

# 🏰 منابع امپراتوری — فروش مواد اولیه در امپراتوری: (نام، تعداد، قیمت)
RES_SHOP = {
    "food": ("🌾 بسته غذا ×۱۰", 10, 120),
    "med":  ("💊 دارو ×۵",       5, 150),
    "iron": ("⚒️ آهن ×۵",        5, 200),
}
BUILDINGS = {
    "farm":     ("🚜 مزرعه",     "هر ۶ ساعت: +۵×سطح غذا"),
    "mine":     ("⛏ معدن",      "هر ۶ ساعت: +۳×سطح آهن"),
    "hospital": ("🏥 بیمارستان", "هر ۶ ساعت: درمان مجروح‌ها (هر نفر ۱ دارو)"),
    "barracks": ("🏟 سربازخانه", "ظرفیت ارتش: ۱۰×سطح سرباز"),
    "wall":     ("🧱 دیوار",     "دفاع+ در جنگ‌ها و حمله‌های ارتش"),
}
TICK_SEC = 6 * 3600  # هر تیک امپراتوری = ۶ ساعت

# 🕶 تجهیزات هک — (آیدی، نام، قدرت، قیمت)
HACK_ATK = [("keylogger", "🐛 کیلاگر",      1, 800),
            ("botnet",    "🌐 بات‌نت",       3, 2500),
            ("exploit",   "💣 اکسپلویت",     5, 6000),
            ("aihack",    "🤖 هک AI",        8, 15000)]
HACK_DEF = [("antivirus", "🛡 آنتی‌ویروس",   1, 700),
            ("firewall",  "🔥 فایروال",      3, 2200),
            ("quantum",   "🔐 رمزنگار",      5, 6500),
            ("honeypot",  "🕸 هانی‌پات",     8, 14000)]
HACK_ALL = {t[0]: t for t in HACK_ATK + HACK_DEF}
HACK_ENERGY_COST = 15
HACK_COOLDOWN = 600      # ثانیه بین دو هک
RAID_COOLDOWN = 900      # ثانیه بین دو حمله ارتشی
DUEL_STAKES = [500, 1000, 5000]

# ── v4: خانواده / اتحاد / پت / بانک / رویداد جهانی ──
MARRIAGE_RING_COST = 2000   # هزینه حلقه و درخواست ازدواج
CHILD_COST = 2500           # هزینه بچه‌دار شدن
MAX_CHILDREN = 4
GUILD_CREATE_COST = 5000
LOAN_INTEREST = 1.15        # ۱۵٪ سود وام
LOAN_DAYS = 3

# 🐾 پت‌ها: (آیدی، نام، قیمت پول، قیمت سکه، بونس جنگ پایه)
PETS = [
    ("cat",    "🐱 گربه",        800,  0,  2),
    ("rabbit", "🐰 خرگوش",       1200, 0,  2),
    ("dog",    "🐕 سگ",          1500, 0,  4),
    ("eagle",  "🦅 عقاب",        5000, 0,  8),
    ("dragon", "🐲 اژدهای کوچولو", 0,  80, 15),
]

# 🌍 رویدادهای جهانی سراسری (۴ ساعت فعال‌اند)
WORLD_EVENTS = {
    "festival":  ("🎊 جشنواره شهر",     "حقوق‌ها ۲× شد! برو کار کن!"),
    "recession": ("📉 رکود اقتصادی",    "حقوق‌ها ۳۰٪ کمتر شد... بازار سخته."),
    "quake":     ("🌋 زمین‌لرزه",       "۵٪ ارتش‌ها تلفات ساختند و همه سلامتی‌شان کم شد!"),
    "epidemic":  ("🤒 همه‌گیری",        "استراحت و ورزش نصفه اثر می‌کنند! بیمارستان مداوا می‌کند."),
    "rally":     ("🚀 رونق بازار",      "همه قیمت‌های بورس +۱۰٪ جهش کردند!"),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
log = logging.getLogger("LifeSim")

# ─────────────── داده‌های ثابت بازی ───────────────

TRAITS = {
    "smart":    {"label": "🧠 باهوش",    "skill": "int",   "bonus": 2, "desc": "یادگیری سریع‌تر و شانس بیشتر در سرمایه‌گذاری"},
    "creative": {"label": "🎨 خلاق",      "skill": "crea",  "bonus": 2, "desc": "پرسپکتیو متفاوت به رویدادها و شانس داستان‌های بهتر"},
    "social":   {"label": "🗣 اجتماعی",   "skill": "comm",  "bonus": 2, "desc": "روابط سریع‌تر و موفقیت در مذاکره"},
    "risky":    {"label": "🎲 ریسک‌پذیر", "skill": None,    "bonus": 0, "desc": "شانس برد در سرمایه‌گذاری و انتخاب‌های جسورانه +۱۰٪"},
    "hardwork": {"label": "💪 سخت‌کوش",   "skill": "mgmt",  "bonus": 2, "desc": "مدیریت بهتر، انرژی پایدارتر"},
}

SKILLS = {
    "prog": "👨‍💻 برنامه‌نویسی",
    "mgmt": "📊 مدیریت",
    "comm": "🗣 ارتباطات",
    "crea": "🎨 خلاقیت",
    "int":  "🧠 هوش",
    "hack": "🕶 هک",
}

CITIES = ["تهران", "مشهد", "اصفهان", "شیراز", "تبریز", "رشت", "اهواز", "کرج"]

SEED_JOBS = [
    # (id, عنوان, مهارت لازم, حداقل مهارت, حداقل لول شخصیت, حقوق پایه)
    ("worker",   "🛠 کارگر",        None,   0, 1,  300),
    ("seller",   "🛍 فروشنده",      "comm", 2, 1,  600),
    ("dev",      "👨‍💻 برنامه‌نویس", "prog", 3, 2,  1500),
    ("manager",  "📊 مدیر",         "mgmt", 4, 4,  3000),
    ("founder",  "🚀 کارآفرین",     "mgmt", 6, 6,  5000),
    ("investor", "📈 سرمایه‌گذار",  "int",  6, 8,  8000),
]

SEED_ITEMS = [
    # (emoji, نام, دسته, قیمت, متن اثر, اثر JSON)
    ("📱", "موبایل",   "shop", 800,   "+۵ شادی 😊",                    {"happiness": 5}),
    ("🎮", "کنسول بازی", "shop", 1500, "+۱۰ شادی 😊، +۴۰ امتیاز XP",    {"happiness": 10, "xp": 40}),
    ("💻", "لپ‌تاپ",   "shop", 2500,  "+۱ برنامه‌نویسی 👨‍💻، +۳ شادی", {"skill:prog": 1, "happiness": 3}),
    ("🎧", "هدفون",    "shop", 900,   "+۶ شادی 😊، +۵ انرژی ⚡",        {"happiness": 6, "energy": 5}),
    ("📚", "کتابخانه شخصی", "shop", 1200, "+۱ هوش 🧠",                 {"skill:int": 1}),
    ("🚗", "ماشین",    "shop", 20000, "+۱۰ شادی، +۱۵ اعتبار 🏆",        {"happiness": 10, "reputation": 15}),
    ("🏠", "اتاق اجاره‌ای", "house", 3000,  "+۵ سلامتی ❤️، +۵ انرژی ⚡",  {"health": 5,  "energy": 5}),
    ("🏡", "آپارتمان",     "house", 15000, "+۱۰ سلامتی ❤️، +۱۰ انرژی ⚡", {"health": 10, "energy": 10}),
    ("🏰", "ویلای لوکس",   "house", 60000, "+۲۵ سلامتی، +۲۰ انرژی، +۱۰ اعتبار", {"health": 25, "energy": 20, "reputation": 10}),
]

NPC_NAMES  = ["آرش", "نیما", "کیان", "مهران", "سارا", "نازنین", "الهه", "درسا", "بردیا", "رهام", "تارا", "یاسمین"]
NPC_TRAITS = ["مهربون", "کنایه‌ای", "جاه‌طلب", "وفادار", "حسود", "شوخ‌طبع", "جدی", "مرموز"]
NPC_ROLES  = [("friend", "🫂 دوست", 60), ("colleague", "💼 همکار", 50), ("rival", "⚔️ رقیب", 25)]

NPC_CHAT_LINES = [
    "«{name}» گفت: این روزها شهر خیلی قشنگ شده، نه؟",
    "«{name}» درباره‌ی یک فرصت جدید توی {city} باهات حرف زد.",
    "«{name}» خندید و گفت: تو از بقیه متفاوتی؛ همین باعث پیشرفتته.",
    "«{name}» یه قهوه تعارف کرد و حسابی دم در رابطه‌تون گذاشتید.",
    "«{name}» گفت: اگه یه روز مشهور شدی، منو یادت نره!",
    "«{name}» یه راز کوچیک درباره‌ی شهر بهت گفت.",
]

RIVAL_LINES = [
    "«{name}» با لبخند مصنوعی گفت: هنوز داری تلاش می‌کنی؟",
    "«{name}» بهت طعنه زد و رفت... حس بدی نداشتی، فقط انگیزه گرفتی.",
]

# ══════════════════════════════════════════════════════════════════
# [2] کلاینت Bale Bot API  (tapi.bale.ai — سازگار با Telegram Bot API)
# ══════════════════════════════════════════════════════════════════

class BaleAPI:
    """لایه‌ی ارتباط با API رسمی ربات بله — با مدیریت خطا و تلاش مجدد."""

    BASE = "https://tapi.bale.ai"

    def __init__(self, token: str):
        self.token   = token
        self.session = requests.Session()
        self.offset  = 0

    def call(self, method: str, timeout: int = 40, **params):
        url = f"{self.BASE}/bot{self.token}/{method}"
        for attempt in range(3):
            try:
                r = self.session.post(url, json=params, timeout=timeout)
                data = r.json()
                if data.get("ok"):
                    return data.get("result")
                log.warning(f"⚠️ Bale API [{method}]: {data}")
                return None
            except Exception as e:  # قطعی شبکه، DNS، ...
                log.warning(f"🌐 خطای شبکه در {method} (تلاش {attempt+1}): {e}")
                time.sleep(1.5 * (attempt + 1))
        return None

    def get_updates(self):
        res = self.call("getUpdates", timeout=40, offset=self.offset, timeout_s=25) or \
              self.call("getUpdates", timeout=40, offset=self.offset)
        return res

    def poll(self):
        """لانگ‌پولینگ روی getUpdates"""
        try:
            r = self.session.post(
                f"{self.BASE}/bot{self.token}/getUpdates",
                json={"offset": self.offset, "timeout": 25, "limit": 100},
                timeout=40,
            )
            data = r.json()
            if data.get("ok"):
                updates = data.get("result", [])
                if updates:
                    self.offset = max(u["update_id"] for u in updates) + 1
                return updates
            log.warning(f"⚠️ getUpdates: {data}")
        except Exception as e:
            log.warning(f"🌐 خطای polling: {e}")
            time.sleep(3)
        return []

    # ── ارسال ──
    def send_message(self, chat_id, text, reply_markup=None):
        p = {"chat_id": chat_id, "text": text[:4096]}
        if reply_markup:
            p["reply_markup"] = reply_markup
        return self.call("sendMessage", **p)

    def edit_message(self, chat_id, message_id, text, reply_markup=None):
        p = {"chat_id": chat_id, "message_id": message_id, "text": text[:4096]}
        if reply_markup:
            p["reply_markup"] = reply_markup
        return self.call("editMessageText", **p)

    def answer_callback(self, cb_id, text=None):
        p = {"callback_query_id": cb_id}
        if text:
            p["text"] = text[:200]
        return self.call("answerCallbackQuery", **p)


api = None  # در main() مقداردهی می‌شود


# ─────────────── سازنده‌های کیبورد ───────────────

def reply_keyboard(rows, resize=True):
    return {"keyboard": [[{"text": str(b)} for b in row] for row in rows], "resize_keyboard": resize}

def inline_keyboard(rows):
    return {"inline_keyboard": [[{"text": str(t), "callback_data": str(d)} for t, d in row] for row in rows]}

MAIN_KB = reply_keyboard([
    ["🎮 بازی", "👤 پروفایل"],
    ["💼 شغل", "🏠 خانه"],
    ["🏪 بازار", "⚔️ جنگ"],
    ["🏰 امپراتوری", "🕶 هک"],
    ["👨‍👩‍👧 خانواده", "🤝 اتحاد"],
    ["🐾 پت", "🏦 بانک"],
    ["💰 اقتصاد", "📚 مهارت‌ها"],
    ["👥 روابط", "🎯 ماموریت‌ها"],
    ["💎 VIP", "🏆 رتبه‌بندی"],
    ["⚙ تنظیمات"],
])

ADMIN_KB = reply_keyboard([
    ["👥 مدیریت کاربران", "📊 آمار ربات"],
    ["🏪 مدیریت اقتصاد", "🎲 مدیریت رویدادها"],
    ["💎 سفارش‌ها و درآمد", "🎛 کنترل بازار"],
    ["📢 پیام همگانی", "📨 پیام به کاربر"],
    ["📣 اطلاعیه همگانی", "🛰 تنظیمات کانال"],
    ["🌍 رویداد جهانی", "🚪 خروج از پنل ادمین"],
])


# ══════════════════════════════════════════════════════════════════
# [3] لایه دیتابیس (SQLite — تک‌فایل، امن، قابل ارتقا به PostgreSQL)
# ══════════════════════════════════════════════════════════════════

class Database:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.lock = threading.RLock()
        self._init_schema()
        self._seed()

    def execute(self, sql, params=()):
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def fetchone(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def _init_schema(self):
        with self.lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                created_at TEXT,
                last_seen  TEXT,
                is_banned  INTEGER DEFAULT 0,
                state      TEXT,
                state_data TEXT
            );
            CREATE TABLE IF NOT EXISTS profiles(
                user_id       INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                name          TEXT,
                age           INTEGER,
                city          TEXT,
                trait         TEXT,
                money         INTEGER DEFAULT 1000,
                level         INTEGER DEFAULT 1,
                xp            INTEGER DEFAULT 0,
                energy        INTEGER DEFAULT 100,
                health        INTEGER DEFAULT 100,
                happiness     INTEGER DEFAULT 80,
                reputation    INTEGER DEFAULT 10,
                job_id        TEXT,
                job_level     INTEGER DEFAULT 1,
                home          TEXT DEFAULT 'پناهگاه',
                skills_json   TEXT DEFAULT '{}',
                pending_event TEXT,
                last_work     TEXT,
                last_rest     TEXT,
                games_played  INTEGER DEFAULT 0,
                created_at    TEXT
            );
            CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, title TEXT,
                min_skill TEXT, min_skill_level INTEGER,
                min_level INTEGER DEFAULT 1, base_salary INTEGER
            );
            CREATE TABLE IF NOT EXISTS items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emoji TEXT, name TEXT, category TEXT DEFAULT 'shop',
                price INTEGER, effect_text TEXT, effect_json TEXT,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS inventory(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, item_id INTEGER, purchased_at TEXT,
                UNIQUE(user_id, item_id)
            );
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, text TEXT, probability REAL,
                reward_json TEXT, penalty_json TEXT,
                created_by INTEGER, is_active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS transactions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, amount INTEGER,
                type TEXT, description TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS admins(
                user_id INTEGER PRIMARY KEY, added_at TEXT
            );
            CREATE TABLE IF NOT EXISTS logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor INTEGER, action TEXT, details TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS npcs(
                user_id INTEGER, npc_id TEXT, name TEXT, role TEXT,
                personality TEXT, relation INTEGER DEFAULT 50,
                PRIMARY KEY(user_id, npc_id)
            );
            CREATE TABLE IF NOT EXISTS missions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, mkey TEXT, title TEXT,
                target INTEGER, reward TEXT,
                progress INTEGER DEFAULT 0, done INTEGER DEFAULT 0, day TEXT,
                UNIQUE(user_id, mkey, day)
            );
            CREATE TABLE IF NOT EXISTS announcements(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY, value TEXT
            );
            CREATE TABLE IF NOT EXISTS markets(
                symbol TEXT PRIMARY KEY, name TEXT,
                price INTEGER, prev_price INTEGER,
                trend REAL DEFAULT 0, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS portfolio(
                user_id INTEGER, symbol TEXT,
                amount REAL DEFAULT 0, avg_price REAL DEFAULT 0,
                PRIMARY KEY(user_id, symbol)
            );
            CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, pack TEXT, gems INTEGER,
                price_toman INTEGER, status TEXT DEFAULT 'pending',
                created_at TEXT, processed_by INTEGER, processed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS war_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attacker INTEGER, defender INTEGER,
                result TEXT, loot INTEGER, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS resources(
                user_id INTEGER PRIMARY KEY,
                food REAL DEFAULT 20, iron REAL DEFAULT 5, medicine REAL DEFAULT 3,
                soldiers INTEGER DEFAULT 2, wounded INTEGER DEFAULT 0,
                farm INTEGER DEFAULT 1, mine INTEGER DEFAULT 1,
                hospital INTEGER DEFAULT 1, barracks INTEGER DEFAULT 1, wall INTEGER DEFAULT 1,
                last_tick TEXT, last_hack TEXT, last_raid TEXT
            );
            CREATE TABLE IF NOT EXISTS hack_gear(
                user_id INTEGER, tool_id TEXT,
                PRIMARY KEY(user_id, tool_id)
            );
            CREATE TABLE IF NOT EXISTS duels(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenger INTEGER, opponent INTEGER, stake INTEGER,
                status TEXT DEFAULT 'pending', result TEXT,
                created_at TEXT, finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS family(
                user_id INTEGER PRIMARY KEY,
                spouse_id INTEGER, married_at TEXT,
                children INTEGER DEFAULT 0, last_bonus TEXT
            );
            CREATE TABLE IF NOT EXISTS guilds(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, leader_id INTEGER, bank INTEGER DEFAULT 0,
                donations INTEGER DEFAULT 0, last_war TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS guild_members(
                user_id INTEGER PRIMARY KEY, guild_id INTEGER,
                role TEXT DEFAULT 'member', joined_at TEXT
            );
            CREATE TABLE IF NOT EXISTS pets(
                user_id INTEGER PRIMARY KEY,
                species TEXT, name TEXT,
                hunger INTEGER DEFAULT 20, happy INTEGER DEFAULT 70,
                level INTEGER DEFAULT 1,
                adopted_at TEXT, last_tick TEXT
            );
            """)
            self.conn.commit()
        self._migrate()

    def _migrate(self):
        """افزودن ستون‌های جدید به دیتابیس‌های قدیمی بدون پاک شدن داده‌ها"""
        cols = {r[1] for r in self.fetchall("PRAGMA table_info(profiles)")}
        for col, ddl in {"gems": "INTEGER DEFAULT 0", "vip": "INTEGER DEFAULT 0",
                         "shield_until": "TEXT", "last_attack": "TEXT", "last_boss": "TEXT",
                         "bank_balance": "INTEGER DEFAULT 0", "loan_debt": "INTEGER DEFAULT 0",
                         "loan_due": "TEXT", "bank_last_int": "TEXT"}.items():
            if col not in cols:
                self.execute(f"ALTER TABLE profiles ADD COLUMN {col} {ddl}")

    def _seed(self):
        # شغل‌ها
        for j in SEED_JOBS:
            self.execute("INSERT OR IGNORE INTO jobs(id,title,min_skill,min_skill_level,min_level,base_salary) VALUES(?,?,?,?,?,?)", j)
        # آیتم‌ها
        if not self.fetchone("SELECT id FROM items LIMIT 1"):
            for it in SEED_ITEMS:
                self.execute(
                    "INSERT INTO items(emoji,name,category,price,effect_text,effect_json) VALUES(?,?,?,?,?,?)",
                    (it[0], it[1], it[2], it[3], it[4], json.dumps(it[5], ensure_ascii=False)),
                )
        # دارایی‌های بازار
        for s, name, price in SEED_MARKETS:
            self.execute(
                "INSERT OR IGNORE INTO markets(symbol,name,price,prev_price,updated_at,trend) VALUES(?,?,?,?,?,0)",
                (s, name, price, price, now_iso()))
        # ادمین‌های متغیر محیطی
        for aid in ADMIN_IDS:
            self.execute("INSERT OR IGNORE INTO admins(user_id, added_at) VALUES(?,?)", (aid, now_iso()))
        self.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('income_rate','1.0')")
        if not self.fetchone("SELECT id FROM announcements LIMIT 1"):
            self.execute("INSERT INTO announcements(text,created_at) VALUES(?,?)",
                         ("به «Life Simulator AI» خوش اومدی! 🎉 هر روز یک زندگی جدید.", now_iso()))


db = None  # در main() مقداردهی می‌شود


# ══════════════════════════════════════════════════════════════════
# [4] ابزارهای کمکی + منطق بازی
# ══════════════════════════════════════════════════════════════════

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

def fn(x) -> str:
    """اعداد فارسی"""
    return str(x).translate(FA_DIGITS)

def fmt_money(n: int) -> str:
    return fn(f"{int(n):,}")

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def bar(value: int, size: int = 10) -> str:
    value = max(0, min(100, int(value)))
    full = round(value / 100 * size)
    return "▮" * full + "▯" * (size - full)

def pick(lst):
    return random.choice(lst)

def jd(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)

def jl(s, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


# ───── کاربران ─────

def ensure_user(tg_user: dict):
    uid = int(tg_user["id"])
    row = db.fetchone("SELECT * FROM users WHERE user_id=?", (uid,))
    if not row:
        db.execute(
            "INSERT INTO users(user_id,username,first_name,created_at,last_seen) VALUES(?,?,?,?,?)",
            (uid, tg_user.get("username", ""), tg_user.get("first_name", ""), now_iso(), now_iso()),
        )
    else:
        db.execute("UPDATE users SET last_seen=?, username=? WHERE user_id=?",
                   (now_iso(), tg_user.get("username", ""), uid))
    return uid

def is_banned(uid) -> bool:
    r = db.fetchone("SELECT is_banned FROM users WHERE user_id=?", (uid,))
    return bool(r and r["is_banned"])

def profile(uid):
    r = db.fetchone("SELECT * FROM profiles WHERE user_id=?", (uid,))
    return dict(r) if r else None

def set_profile(uid, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE profiles SET {keys} WHERE user_id=?", (*fields.values(), uid))

def get_state(uid):
    r = db.fetchone("SELECT state, state_data FROM users WHERE user_id=?", (uid,))
    return (r["state"], jl(r["state_data"], {})) if r else (None, {})

def set_state(uid, state=None, data=None):
    db.execute("UPDATE users SET state=?, state_data=? WHERE user_id=?",
               (state, jd(data) if data is not None else None, uid))

def log_action(actor, action, details=""):
    db.execute("INSERT INTO logs(actor,action,details,created_at) VALUES(?,?,?,?)",
               (actor, action, details, now_iso()))

def get_setting(key, default=""):
    r = db.fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default

def set_setting(key, value):
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?", (key, value, value))

def is_admin(uid) -> bool:
    return uid in ADMIN_IDS or bool(db.fetchone("SELECT user_id FROM admins WHERE user_id=?", (uid,)))


# ───── پول و تراکنش ─────

def change_money(uid, amount, ttype, desc):
    p = profile(uid)
    if not p:
        return
    new_money = max(0, int(p["money"]) + int(amount))
    db.execute("UPDATE profiles SET money=? WHERE user_id=?", (new_money, uid))
    db.execute("INSERT INTO transactions(user_id,amount,type,description,created_at) VALUES(?,?,?,?,?)",
               (uid, int(amount), ttype, desc, now_iso()))


# ───── XP و لول ─────

def xp_needed(level):
    return level * 100

def gain_xp(uid, amount):
    """افزودن XP و مدیریت لول‌اپ. خروجی: لیست پیام‌ها"""
    p = profile(uid)
    msgs = []
    lvl, xp = p["level"], p["xp"] + amount
    while xp >= xp_needed(lvl):
        xp -= xp_needed(lvl)
        lvl += 1
        bonus = 100 * lvl
        db.execute("UPDATE profiles SET money=money+?, happiness=MIN(100,happiness+5), reputation=MIN(100,reputation+2) WHERE user_id=?",
                   (bonus, uid))
        msgs.append(f"🆙🎉 لول‌آپ! به لول {fn(lvl)} رسیدی! (جایزه: {fmt_money(bonus)} تومان 💰)")
        log_action(uid, "level_up", f"level={lvl}")
    db.execute("UPDATE profiles SET level=?, xp=? WHERE user_id=?", (lvl, xp, uid))
    return msgs


# ───── مهارت‌ها ─────

def get_skills(uid):
    p = profile(uid)
    skills = {k: 0 for k in SKILLS}
    skills.update(jl(p["skills_json"], {}) if p else {})
    return skills

def gain_skill(uid, key, amount=1):
    skills = get_skills(uid)
    skills[key] = min(10, skills.get(key, 0) + amount)
    set_profile(uid, skills_json=jd(skills))
    return skills[key]


# ───── اعمال اثرات رویداد/آیتم ─────

def apply_effects(uid, effects: dict, source="رویداد"):
    """
    اثرات قابل پشتیبانی:
    money, xp, energy, health, happiness, reputation, skill:<key>
    مقدار می‌تواند عدد یا بازه [min,max] باشد.
    """
    p = profile(uid)
    if not p:
        return []
    lines = []
    adds = defaultdict(int)
    for key, val in effects.items():
        if isinstance(val, list):
            val = random.randint(int(val[0]), int(val[1]))
        val = int(val)
        if key == "money" and val:
            change_money(uid, val, "event", source)
            lines.append(f"💰 {'+' if val>0 else ''}{fmt_money(val)} تومان")
        elif key == "xp" and val:
            lines.append(f"⭐ +{fn(val)} XP")
            msgs = gain_xp(uid, val)
            lines.extend(msgs)
        elif key.startswith("skill:"):
            sk = key.split(":", 1)[1]
            if val > 0:
                nv = gain_skill(uid, sk, val)
                lines.append(f"{SKILLS.get(sk, sk)} +{fn(val)} (لول {fn(nv)})")
        elif key in ("energy", "health", "happiness", "reputation") and val:
            adds[key] = val
            emoji = {"energy": "⚡", "health": "❤️", "happiness": "😊", "reputation": "🏆"}[key]
            lines.append(f"{emoji} {'+' if val>0 else ''}{fn(val)}")
    if adds:
        sets = ", ".join(f"{k}=MAX(0,MIN(100,{k}+?))" for k in adds)
        db.execute(f"UPDATE profiles SET {sets} WHERE user_id=?",
                   (*adds.values(), uid))
    return lines


# ───── NPC ─────

def create_npcs(uid):
    names = random.sample(NPC_NAMES, 3)
    for (npc_id, role, base_rel), name in zip(NPC_ROLES, names):
        db.execute(
            "INSERT OR IGNORE INTO npcs(user_id,npc_id,name,role,personality,relation) VALUES(?,?,?,?,?,?)",
            (uid, npc_id, name, role, pick(NPC_TRAITS), base_rel),
        )

def get_npcs(uid):
    if not db.fetchone("SELECT npc_id FROM npcs WHERE user_id=? LIMIT 1", (uid,)):
        create_npcs(uid)
    return [dict(r) for r in db.fetchall("SELECT * FROM npcs WHERE user_id=?", (uid,))]

def change_relation(uid, npc_id, delta):
    db.execute("UPDATE npcs SET relation=MAX(0,MIN(100,relation+?)) WHERE user_id=? AND npc_id=?",
               (delta, uid, npc_id))

def relation_label(rel):
    if rel >= 80: return "💖 صمیمی"
    if rel >= 60: return "🤝 دوست خوب"
    if rel >= 40: return "🙂 آشنا"
    if rel >= 20: return "😬 سرد"
    return "💢 دشمن"


# ───── ماموریت‌های روزانه ─────

DAILY_MISSIONS = [
    ("life",   "🎲 یک رویداد زندگی را تجربه کن", 1, {"money": 200, "xp": 25}),
    ("work",   "💼 یک شیفت کار کن",              1, {"money": 250, "xp": 30}),
    ("train",  "📚 یک مهارت را تقویت کن",        1, {"xp": 40}),
    ("social", "👥 با یکی از آشناها گپ بزن",     1, {"money": 150, "happiness": 8}),
    ("war",    "⚔️ یک جنگ انجام بده",            1, {"money": 300, "xp": 40}),
]

def ensure_missions(uid):
    for mkey, title, target, reward in DAILY_MISSIONS:
        db.execute(
            "INSERT OR IGNORE INTO missions(user_id,mkey,title,target,reward,day) VALUES(?,?,?,?,?,?)",
            (uid, mkey, title, target, jd(reward), today()),
        )

def mission_progress(uid, mkey):
    db.execute(
        "UPDATE missions SET progress=MIN(target, progress+1) WHERE user_id=? AND mkey=? AND day=? AND done=0",
        (uid, mkey, today()),
    )


# ───── محدودکننده (ضد تقلب/اسپم) ─────

_rate = defaultdict(list)

def rate_limit_ok(uid) -> bool:
    now = time.time()
    _rate[uid] = [t for t in _rate[uid] if now - t < 60]
    if len(_rate[uid]) >= RATE_LIMIT:
        return False
    _rate[uid].append(now)
    return True

def cooldown_ok(uid, field, seconds):
    p = profile(uid)
    last = p.get(field)
    return (not last) or ((datetime.now() - datetime.fromisoformat(last)).total_seconds() >= seconds)

def touch_cooldown(uid, field):
    db.execute(f"UPDATE profiles SET {field}=? WHERE user_id=?", (now_iso(), uid))


# ───── رندر پروفایل ─────

def render_profile(uid):
    p = profile(uid)
    if not p:
        return "❌ هنوز کاراکتری نساختی! /start رو بزن."
    job = db.fetchone("SELECT title FROM jobs WHERE id=?", (p["job_id"],)) if p["job_id"] else None
    job_txt = f"{job['title']} (سطح {fn(p['job_level'])})" if job else "بیکار 😅"
    trait = TRAITS.get(p["trait"], {})
    return (
        f"👤 پروفایل {p['name']}\n"
        f"───────────────\n"
        f"👤 نام: {p['name']}\n"
        f"🎂 سن: {fn(p['age'])}\n"
        f"🏙 شهر: {p['city']}\n"
        f"🌟 ویژگی: {trait.get('label', '—')}\n"
        f"───────────────\n"
        f"💰 پول: {fmt_money(p['money'])} تومان\n"
        f"⭐ لول: {fn(p['level'])}  (XP: {fn(p['xp'])}/{fn(xp_needed(p['level']))})\n"
        f"⚡ انرژی:  {bar(p['energy'])} {fn(p['energy'])}\n"
        f"❤️ سلامتی: {bar(p['health'])} {fn(p['health'])}\n"
        f"😊 شادی:   {bar(p['happiness'])} {fn(p['happiness'])}\n"
        f"🏆 اعتبار: {fn(p['reputation'])}\n"
        f"───────────────\n"
        f"💼 شغل: {job_txt}\n"
        f"🏠 خانه: {p['home']}\n"
        f"💎 سکه طلا: {fn(p.get('gems') or 0)}{' 👑 VIP' if p.get('vip') else ''}\n"
        f"⚔️ قدرت جنگ: {fn(battle_power(uid))}\n"
        f"{family_line(uid)}"
        f"🎲 رویدادهای زندگی: {fn(p['games_played'])}"
    )


def family_line(uid):
    fam = db.fetchone("SELECT spouse_id, children FROM family WHERE user_id=?", (uid,))
    if fam and fam["spouse_id"]:
        sp = profile(fam["spouse_id"]) or {}
        return f"💑 همسر: {sp.get('name','?')} | 👶 فرزند: {fn(fam['children'])}\n"
    return ""


# ══════════════════════════════════════════════════════════════════
# [6] موتور داستانی (AI) — تولید رویداد، داستان و رفتار NPC
# ══════════════════════════════════════════════════════════════════

STORY_OPENERS = [
    "صبح زود از خواب بیدار شدی و",
    "ظهر که شد،",
    "عصر، توی خیابون‌های {city}،",
    "یه روز معمولی بود تا اینکه",
    "شب که رسید،",
    "وسط هفته،",
]

STORY_PLACES = ["کافه‌ی قدیمی محله", "پارک شهر", "کتابخانه‌ی مرکزی", "ایستگاه مترو", "بازار", "ساحل", "دانشگاه", "خیابان اصلی"]

# رویدادهای داخلی بازی — هر آپشن: label/result/effects (+ chance/skill_mod اختیاری برای شانس موفقیت)
BUILTIN_EVENTS = [
    {
        "title": "💼 پیشنهاد کار",
        "text": "یک پیام روی گوشی‌ات داری: «شرکت {city}نوا دنبال نیرو می‌گردد.»\nچه می‌کنی؟",
        "options": [
            {"label": "✅ قبول کار", "result": "پیشنهاد را پذیرفتی؛ چند ساعت کار ارزشمند کردی.",
             "effects": {"money": [200, 500], "xp": 30, "energy": -10, "reputation": 2}},
            {"label": "❌ رد کردن", "result": "ردش کردی و به روتینت برگشتی.",
             "effects": {"happiness": 3}},
            {"label": "🤝 مذاکره", "result": "مذاکره عالی بود! شرایط بهتری گرفتی.",
             "fail_result": "مذاکره جایی نرسید... وقتت تلف شد.",
             "chance": 0.5, "skill_mod": "comm",
             "effects": {"money": [400, 900], "xp": 20, "energy": -10},
             "fail_effects": {"energy": -10, "happiness": -4}},
        ],
    },
    {
        "title": "🎁 بسته مرسوله",
        "text": "یک بسته‌ی ناشناس پشت در است. بازش می‌کنی؟",
        "options": [
            {"label": "📦 باز کردن", "result": "داخلش کارت هدیه بود! چه روزی!",
             "fail_result": "فاکتور قدیمی خودت بود 😅",
             "chance": 0.7, "effects": {"money": [300, 800], "happiness": 8},
             "fail_effects": {"happiness": -2}},
            {"label": "🚮 دور انداختن", "result": "محتاطانه بود، ولی خیالت راحت شد.",
             "effects": {"happiness": 1}},
            {"label": "🔍 بررسی", "result": "دقیق بررسی‌اش کردی؛ هدیه‌ای از یک دوست قدیمی بود.",
             "effects": {"money": [100, 400], "xp": 15, "happiness": 5}},
        ],
    },
    {
        "title": "🏃 تصمیم سلامت",
        "text": "حس می‌کنی بدنت نیاز به تحرک دارد. چه می‌کنی؟",
        "options": [
            {"label": "🏃 دویدن در پارک", "result": "یک دور دویدی؛ هوایت عوض شد و احساس طراوت داری.",
             "effects": {"health": 8, "energy": -8, "happiness": 6}},
            {"label": "🛋 استراحت", "result": "یک ساعت چرت زدی و حسابی شارژ شدی.",
             "effects": {"energy": 15, "health": 2}},
            {"label": "🍔 فست‌فود", "result": "یک میل چرب خوشمزه! بدن چندان راضی نیست...",
             "effects": {"happiness": 7, "health": -6, "money": [-150, -80]}},
        ],
    },
    {
        "title": "💡 ایده‌ی ناگهانی",
        "text": "وسط راه ناگهان یک ایده به سرت زد! دنبالش می‌روی؟",
        "options": [
            {"label": "🚀 دنبالش کن", "result": "ایده جواب داد! یک قدم جلوتر از بقیه‌ای.",
             "fail_result": "ایده‌ات آبرو نداشت و خراب شد 😬",
             "chance": 0.55, "skill_mod": "crea",
             "effects": {"money": [300, 1000], "xp": 40, "reputation": 3, "energy": -12},
             "fail_effects": {"money": [-200, -50], "happiness": -5, "energy": -12}},
            {"label": "📝 یادداشت کن", "result": "یادداشتش کردی؛ شاید روزی به کار آید.",
             "effects": {"xp": 20}},
            {"label": "🙈 نادیده بگیر", "result": "ازش گذشتی... شاید فرصتی بود که رفت.",
             "effects": {"happiness": -2}},
        ],
    },
    {
        "title": "🫂 دعوت {npc_friend}",
        "text": "{npc_friend} بهت زنگ زد: «امروز وقت داری؟ یه برنامه داریم!»",
        "options": [
            {"label": "🎉 قبول دعوت", "result": "عصر خوبی با دوستت گذروندی؛ حالت عالی شد.",
             "effects": {"happiness": 12, "reputation": 2, "money": [-120, -50], "energy": -8}},
            {"label": "📵 جواب نده", "result": "جواب ندادی... دوستت کمی ناراحت شد.",
             "effects": {"happiness": -4}},
            {"label": "🤝 قرار دیگه", "result": "قرار دیگری گذاشتید و دوستت قانع شد.",
             "effects": {"happiness": 4, "xp": 10}},
        ],
    },
    {
        "title": "⚔️ چشم‌وهم‌چشمی با {npc_rival}",
        "text": "{npc_rival} جلوی بقیه از تو تعریف را تعریف نکرد؛ دقیقا برعکس!",
        "options": [
            {"label": "🔥 پاسخ محکم", "result": "خیلی محکم جوابش را دادی؛ جمع عوض شد.",
             "fail_result": "حرفت به جایی برخورد و خودت دعوا پیدا کردی.",
             "chance": 0.5, "skill_mod": "comm",
             "effects": {"reputation": 6, "happiness": 5},
             "fail_effects": {"reputation": -4, "happiness": -6}},
            {"label": "😌 بی‌خیال", "result": "خونسرد ماندی؛ بعضی‌ها ارزش جواب ندارند.",
             "effects": {"xp": 15, "happiness": 2}},
            {"label": "🤝 آشتی", "result": "پیش‌قدم شدی و دستت را دراز کردی. جمع تعجب کرد.",
             "effects": {"reputation": 5, "happiness": 4}},
        ],
    },
    {
        "title": "📈 فرصت سرمایه‌گذاری",
        "text": "یکی از آشناها می‌گوید یک فرصت «تضمینی» در {city} دارد. ورود می‌کنی؟",
        "options": [
            {"label": "💸 ورود سنگین", "result": "وای! ضربه‌ی بزرگی زدی و پولت دوبرابر شد!",
             "fail_result": "تضمینی نبود... بخشی از پولت سوخت.",
             "chance": 0.45, "skill_mod": "int",
             "effects": {"money": [-500, 1500], "xp": 20},
             "fail_effects": {"money": [-800, -300], "happiness": -6}},
            {"label": "🤏 کم وارد شو", "result": "با احتیاط سود کمی گرفتی.",
             "effects": {"money": [50, 250], "xp": 10}},
            {"label": "🚫 رد کن", "result": "ریسک نکردی. عاقلانه بود؟ خودت می‌دانی.",
             "effects": {"happiness": 1}},
        ],
    },
    {
        "title": "📚 کلاس آموزشی",
        "text": "یک کارگاه آموزشی رایگان در شهر برگزار می‌شود.",
        "options": [
            {"label": "✍️ ثبت‌نام", "result": "یک عصر پر از یادگیری! ذهنت بازتر شد.",
             "effects": {"xp": 50, "energy": -10, "happiness": 3}},
            {"label": "🎥 تماشا از خانه", "result": "از خانه نگاه کردی؛ نصفِ نصف یاد گرفتی.",
             "effects": {"xp": 20, "energy": -3}},
            {"label": "🏃 فرار", "result": "درِ کلاس را ندیدی... روز آرامی بود.",
             "effects": {"happiness": 2}},
        ],
    },
    {
        "title": "🌧 روز بارانی",
        "text": "ناگهان باران گرفت و تو چتر نداری!",
        "options": [
            {"label": "☔ دویدن به خانه", "result": "خیس شدی ولی رسیدی! حالا چای داغ.",
             "effects": {"health": -3, "happiness": 3}},
            {"label": "🚕 تاکسی", "result": "یک تاکسی گرفتی؛ نان از برات گرگ رفت ولی خشک ماندی.",
             "effects": {"money": [-90, -40], "happiness": 2}},
            {"label": "🌧 زیر بارون رقصیدن", "result": "زیر بارون رقصیدی! آدمای {city} بهت لبخند زدند.",
             "effects": {"happiness": 10, "reputation": 3, "health": -2}},
        ],
    },
    {
        "title": "🤝 آشنایی جدید در {place}",
        "text": "در {place} با یک فرد جالب آشنا شدی که در حوزه‌ی کارت فعالیت دارد.",
        "options": [
            {"label": "🗣 گپ عمیق", "result": "گفت‌وگوی عمیقی شد؛ از تجربه‌اش چیزهای زیادی آموختی.",
             "effects": {"xp": 35, "reputation": 3, "happiness": 4}},
            {"label": "📇 تبادل شماره", "result": "شبکه‌ی ارتباطیت یک نفر قوی‌تر شد.",
             "effects": {"reputation": 4, "xp": 10}},
            {"label": "🙂 فقط سلام", "result": "سلام‌وعلیکی کردی و رد شدی.",
             "effects": {"happiness": 1}},
        ],
    },
    {
        "title": "🛒 حراج بزرگ",
        "text": "فروشگاه محله حراج ۷۰٪ زده! وسوسه شدی...",
        "options": [
            {"label": "🛍 خرید میدانی", "result": "خرید عالی شد! جنس‌های قشنگی گیر آوردی.",
             "effects": {"money": [-400, -150], "happiness": 10}},
            {"label": "👀 فقط نگاه", "result": "فقط نگاه کردی... یکی‌دو تا چیز هم گیرت آمد.",
             "effects": {"money": [-80, -20], "happiness": 3}},
            {"label": "🚶 عبور", "result": "وسوسه‌ات را شکستی؛ حس پیروزی داری.",
             "effects": {"xp": 15, "happiness": 2}},
        ],
    },
    {
        "title": "🎮 مسابقه بازی",
        "text": "یک تورنمنت بازی در شهر برگزار شده. شرکت می‌کنی؟",
        "options": [
            {"label": "🏆 شرکت کن", "result": "قهرمان شدی! جام را بالای سرت بردی! 🏆",
             "fail_result": "سخت بود... در مرحله‌ی اول حذف شدی.",
             "chance": 0.4, "effects": {"money": [400, 900], "reputation": 6, "happiness": 12, "energy": -10},
             "fail_effects": {"happiness": -4, "energy": -10}},
            {"label": "🍿 تماشا", "result": "از کنار زمین لذت بردی و حرکات یاد گرفتی.",
             "effects": {"xp": 15, "happiness": 5}},
            {"label": "🏠 برو خونه", "result": "جمعیت زیاد بود؛ به خانه برگشتی.",
             "effects": {"energy": 5}},
        ],
    },
]

# قالب‌های داینامیک برای تولید نامحدود داستان + NPC
DYNAMIC_SCENARIOS = [
    "{opener} در {place} اتفاق جالبی افتاد: یک نفر کیف پولش را گم کرده بود و {actor} کمکش کرد. تو هم آنجا بودی...",
    "{opener} خبر شنیدی که یک شرکت بزرگ به {city} آمده و دنبال نیروی تازه‌نفس است.",
    "{opener} {npc} بهت پیام داد: «یه طرح جدید دارم که شاید به دردت بخوره.»",
    "{opener} در {place} یه مسابقه‌ی داوطلبانه برگزار شده؛ برنده‌اش معروف می‌شه.",
    "{opener} یک غریبه عجول بهت زد و باعث شد وسایلت بیفتن... مردم نگاه می‌کردند.",
    "{opener} یک سرمایه‌دار بهدنبال پروژه‌های جدید در {city} می‌گردد و تو هم می‌توانی طرحت را معرفی کنی.",
]


def generate_story(uid) -> str:
    """یک خط داستانی تصادفی (AI-ish) برای حال‌وهوای بازی"""
    p = profile(uid)
    npcs = {n["npc_id"]: n for n in get_npcs(uid)}
    line = pick(STORY_OPENERS).replace("{city}", p["city"])
    extra = ""
    # رفتار NPC رقیب با رابطه‌ی کم → فشار داستان
    rival = npcs.get("rival")
    if rival and rival["relation"] < 30 and random.random() < 0.25:
        extra = "\n" + pick(RIVAL_LINES).replace("{name}", rival["name"])
    return f"📖 {line} «{pick(STORY_PLACES)}» ...{extra}"


def resolve_text(text: str, uid) -> str:
    p = profile(uid)
    npcs = {n["npc_id"]: n for n in get_npcs(uid)}
    return (text
            .replace("{city}", p["city"])
            .replace("{place}", pick(STORY_PLACES))
            .replace("{npc_friend}", npcs.get("friend", {}).get("name", "دوستت"))
            .replace("{npc_rival}", npcs.get("rival", {}).get("name", "رقیبت"))
            .replace("{npc}", npcs.get("colleague", {}).get("name", "همکارت")))


def make_dynamic_event(uid) -> dict:
    """رویداد داینامیک: ترکیب سناریو + سه انتخاب کلی با شانس‌های مبتنی بر ویژگی/مهارت"""
    p = profile(uid)
    npcs = get_npcs(uid)
    any_npc = pick(npcs)
    scenario = pick(DYNAMIC_SCENARIOS)
    scenario = (scenario
                .replace("{opener}", pick(STORY_OPENERS))
                .replace("{place}", pick(STORY_PLACES))
                .replace("{city}", p["city"])
                .replace("{npc}", any_npc["name"])
                .replace("{actor}", any_npc["name"]))
    title = pick(["🏙 گوشه‌ای از شهر", "🎭 اتفاق روز", "✨ سرنوشت امروز", "🌆 لحظه‌ای از زندگی"])
    return {
        "title": title,
        "text": scenario + "\nچه واکنشی داری؟",
        "options": [
            {"label": "🔥 جسورانه عمل کن", "result": "جسورانه عمل کردی و نتیجه‌ی خوبی گرفتی! شهر از تو حرف می‌زند.",
             "fail_result": "جسورانه بود ولی این‌بار شانس با تو نبود...",
             "chance": 0.45, "skill_mod": "int",
             "effects": {"money": [200, 700], "xp": 30, "reputation": 3, "energy": -10},
             "fail_effects": {"money": [-150, -50], "happiness": -4, "energy": -10}},
            {"label": "🤝 محتاطانه پیش برو", "result": "با احتیاط قدم برداشتی و از ماجرا عبور کردی.",
             "effects": {"xp": 15, "happiness": 2, "money": [0, 150]}},
            {"label": "🚶 رد شو", "result": "از کنار ماجرا گذشتی. روز خودت را داری.",
             "effects": {"happiness": 1, "energy": 2}},
        ],
    }


def choose_event(uid) -> dict:
    """
    انتخاب رویداد با ترکیب:
    25٪ داینامیک | بقیه: رویداد ادمین (با احتمال خودش) یا داخلی
    """
    if random.random() < 0.25:
        return make_dynamic_event(uid)

    admin_events = db.fetchall("SELECT * FROM events WHERE is_active=1")
    for ev in admin_events:
        if random.random() < (ev["probability"] or 0) / 100.0:
            reward  = jl(ev["reward_json"], {})
            penalty = jl(ev["penalty_json"], {})
            return {
                "title": "🎲 " + ev["title"],
                "text": ev["text"],
                "options": [
                    {"label": "✅ انجام بده", "result": "انجامش دادی و جایزه گرفتی!",
                     "effects": reward},
                    {"label": "🎲 ریسک کن (جایزه دوبرابر)",
                     "result": "ریسک کردی و دوبرابر بردی! 🎉",
                     "fail_result": "ریسکت جواب نداد و متحمل جریمه شدی...",
                     "chance": 0.5,
                     "effects": {k: (v * 2 if isinstance(v, int) else v) for k, v in reward.items()},
                     "fail_effects": penalty},
                    {"label": "🙅 نادیده بگیر", "result": "از کنارش گذشتی.",
                     "effects": {"happiness": 1}},
                ],
            }
    return pick(BUILTIN_EVENTS)


# ══════════════════════════════════════════════════════════════════
# [7] هندلرهای بازی (منوهای کاربر)
# ══════════════════════════════════════════════════════════════════

def has_character(uid) -> bool:
    return profile(uid) is not None

def guard_character(chat_id, uid) -> bool:
    if not has_character(uid):
        api.send_message(chat_id, "❌ اول باید کاراکترت را بسازی! /start رو بزن.", MAIN_KB)
        return False
    return True


# ───────── /start و ساخت کاراکتر ─────────

def cmd_start(chat_id, uid):
    if has_character(uid):
        api.send_message(chat_id,
                         f"🌞 دوباره سلام {profile(uid)['name']}!\nبه زندگیت در Life Simulator AI ادامه بده! 👇",
                         MAIN_KB)
        return
    api.send_message(chat_id, (
        "🎮 به «Life Simulator AI» خوش اومدی!\n\n"
        "اینجا یک زندگی مجازی می‌سازی: کار می‌کنی، 🏠 خانه و 🚗 ماشین می‌خری، "
        "دوست و رقیب پیدا می‌کنی و با هر انتخاب، سرنوشتت عوض می‌شه!\n\n"
        "✍️ قدم اول: اسم کاراکترت رو بنویس (مثلا: آرمان)"
    ), reply_keyboard([["لغو ❌"]]))
    set_state(uid, "create_name")


def handle_state_text(chat_id, uid, text, state, data):
    """ورودی‌های چندمرحله‌ای: ساخت کاراکتر + فرم‌های ادمین + تنظیمات"""

    if text in ("لغو ❌", "/cancel"):
        set_state(uid)
        api.send_message(chat_id, "❌ عملیات لغو شد.", MAIN_KB)
        return True

    # ─── ساخت کاراکتر ───
    if state == "create_name":
        if not (2 <= len(text) <= 30):
            api.send_message(chat_id, "⚠️ اسم باید بین ۲ تا ۳۰ حرف باشه. دوباره بنویس:")
            return True
        set_state(uid, "create_age", {"name": text})
        api.send_message(chat_id, f"👍 خوش اومدی {text}!\n🎂 حالا سنت رو به عدد بنویس (۱۰ تا ۹۰):")
        return True

    if state == "create_age":
        if not text.isdigit() or not (10 <= int(text) <= 90):
            api.send_message(chat_id, "⚠️ یک سن معتبر بین ۱۰ تا ۹۰ وارد کن:")
            return True
        data["age"] = int(text)
        set_state(uid, "create_city", data)
        rows, row = [], []
        for i, c in enumerate(CITIES):
            row.append((c, f"crt:city:{i}"))
            if len(row) == 4:
                rows.append(row); row = []
        if row:
            rows.append(row)
        rows.append([("✍️ شهر دیگه...", "crt:city:custom")])
        api.send_message(chat_id, "🏙 شهرته کجاست؟", inline_keyboard(rows))
        return True

    if state == "create_city_custom":
        if not (2 <= len(text) <= 30):
            api.send_message(chat_id, "⚠️ نام شهر معتبر نیست:")
            return True
        data["city"] = text
        set_state(uid, "create_trait", data)
        send_trait_picker(chat_id)
        return True

    # ─── تنظیمات: تغییر نام ───
    if state == "rename":
        if not (2 <= len(text) <= 30):
            api.send_message(chat_id, "⚠️ اسم باید بین ۲ تا ۳۰ حرف باشه:")
            return True
        set_profile(uid, name=text)
        set_state(uid)
        api.send_message(chat_id, f"✅ نامت به «{text}» تغییر کرد.", MAIN_KB)
        return True

    # ─── اتحاد: ساخت ───
    if state == "guild_create":
        if not (2 <= len(text) <= 30):
            api.send_message(chat_id, "⚠️ نام اتحاد باید بین ۲ تا ۳۰ حرف باشه:")
            return True
        guild_create_done(chat_id, uid, text)
        return True

    # ─── پت: نام‌گذاری ───
    if state == "pet_name":
        name = text if (1 <= len(text) <= 20) else pick(["میشا", "جبران", "لولا", "رکس", "پینو"])
        db.execute("UPDATE pets SET name=? WHERE user_id=?", (name, uid))
        set_state(uid)
        api.send_message(chat_id, f"🐾 «{name}» به خانواده‌ات پیوست! یادت نره غذاش بدی 🍖", MAIN_KB)
        return True

    # ─── فرم‌های ادمین ───
    if state.startswith("adm_"):
        return handle_admin_state(chat_id, uid, text, state, data)

    return False


def send_trait_picker(chat_id):
    rows = [[(t["label"], f"crt:trait:{k}")] for k, t in TRAITS.items()]
    api.send_message(chat_id,
                     "🌟 ویژگی شخصیتت رو انتخاب کن:" ,
                     inline_keyboard(rows))


def finish_character_creation(chat_id, uid, data):
    trait = TRAITS[data["trait"]]
    skills = {k: 0 for k in SKILLS}
    if trait["skill"]:
        skills[trait["skill"]] = trait["bonus"]
    db.execute("""INSERT INTO profiles(user_id,name,age,city,trait,money,level,xp,energy,health,
                  happiness,reputation,job_level,skills_json,created_at)
                  VALUES(?,?,?,?,?,1000,1,0,100,100,80,10,1,?,?)""",
               (uid, data["name"], data["age"], data["city"], data["trait"], jd(skills), now_iso()))
    create_npcs(uid)
    ensure_missions(uid)
    log_action(uid, "character_created", f"name={data['name']} trait={data['trait']}")
    set_state(uid)
    api.send_message(chat_id, (
        f"🎉 کاراکترت ساخته شد!\n\n{render_profile(uid)}\n\n"
        f"🌟 ویژگی «{trait['label']}»: {trait['desc']}\n"
        f"💸 پول شروع: {fmt_money(1000)} تومان\n\n"
        "از منوی پایین، بازی رو شروع کن! 👇"
    ), MAIN_KB)


# ───────── 🎮 بازی (رویدادهای زندگی) ─────────

def panel_game(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    ensure_missions(uid)
    rows = [
        [("🌅 زندگی کن (رویداد جدید)", "game:new")],
        [("😴 استراحت (+انرژی)", "game:rest"), ("🏃 ورزش (+سلامتی)", "game:sport")],
        [("🎉 تفریح (+شادی)", "game:fun")],
    ]
    p = profile(uid)
    api.send_message(chat_id,
                     f"🎮 اتاق بازی\n⚡ انرژی: {fn(p['energy'])} | ❤️ {fn(p['health'])} | 😊 {fn(p['happiness'])}\n\n"
                     "«زندگی کن» رو بزن تا یک رویداد اتفاق بیفته؛ انتخاب‌هات سرنوشتت رو می‌سازن!",
                     inline_keyboard(rows))


def new_life_event(chat_id, uid):
    p = profile(uid)
    if p["energy"] < EVENT_ENERGY_COST:
        api.send_message(chat_id, "🔋 انرژیت کمه! اول «😴 استراحت» رو بزن.")
        return
    db.execute("UPDATE profiles SET energy=MAX(0,energy-?) WHERE user_id=?", (EVENT_ENERGY_COST, uid))
    event = choose_event(uid)
    ev = {
        "title": resolve_text(event["title"], uid),
        "text":  resolve_text(event["text"], uid),
        "options": event["options"],
    }
    set_profile(uid, pending_event=jd(ev), games_played=p["games_played"] + 1)
    rows = [[(o["label"], f"ev:{i}")] for i, o in enumerate(ev["options"])]
    story = generate_story(uid)
    api.send_message(chat_id,
                     f"{story}\n\n🎬 {ev['title']}\n──────────\n{ev['text']}",
                     inline_keyboard(rows))


def resolve_event_choice(chat_id, uid, message_id, idx):
    p = profile(uid)
    ev = jl(p.get("pending_event"))
    if not ev or idx >= len(ev["options"]):
        api.send_message(chat_id, "⏳ این رویداد منقضی شده؛ دوباره «زندگی کن» رو بزن.")
        return
    option = ev["options"][idx]
    # شانس موفقیت (مهارت/ویژگی)
    chance = option.get("chance", 1.0)
    if "skill_mod" in option:
        chance += get_skills(uid).get(option["skill_mod"], 0) * 0.05
    if profile(uid)["trait"] == "risky" and chance < 1.0:
        chance += 0.10
    success = random.random() < chance

    result_text = option["result"] if success else option.get("fail_result", option["result"])
    effects     = option.get("effects" if success else "fail_effects", option.get("effects", {}))
    lines = apply_effects(uid, effects, source=ev["title"])
    mission_progress(uid, "life")
    set_profile(uid, pending_event=None)

    p2 = profile(uid)
    footer = (f"\n──────────\n⚡ {fn(p2['energy'])} | ❤️ {fn(p2['health'])} | 😊 {fn(p2['happiness'])}"
              f" | 💰 {fmt_money(p2['money'])} | ⭐ لول {fn(p2['level'])}")
    out = (f"🎬 {ev['title']}\n➡️ انتخاب: {option['label']}\n──────────\n"
           f"{result_text}\n\n📊 نتیجه:\n" + ("\n".join(lines) if lines else "—") + footer)
    ok = api.edit_message(chat_id, message_id, out)
    if ok is None:
        api.send_message(chat_id, out, MAIN_KB)


def do_rest(chat_id, uid):
    if not cooldown_ok(uid, "last_rest", REST_COOLDOWN):
        api.send_message(chat_id, f"⏳ تازه استراحت کردی! هر {fn(REST_COOLDOWN)} ثانیه یک‌بار.")
        return
    scale = 0.5 if (world_event() or {}).get("key") == "epidemic" else 1.0
    db.execute("UPDATE profiles SET energy=MIN(100,energy+?), health=MIN(100,health+?) WHERE user_id=?",
               (int(35 * scale), int(5 * scale), uid))
    touch_cooldown(uid, "last_rest")
    sick = "\n🤒 بحران همه‌گیری! اثر استراحت نصف شد." if scale < 1 else ""
    api.send_message(chat_id, f"😴 یک چرت خوب زدی! ⚡ +{fn(int(35*scale))} انرژی و ❤️ +{fn(int(5*scale))} سلامتی.{sick}")


def do_sport(chat_id, uid):
    p = profile(uid)
    if p["energy"] < 10:
        api.send_message(chat_id, "🔋 برای ورزش انرژی نداری! استراحت کن.")
        return
    scale = 0.5 if (world_event() or {}).get("key") == "epidemic" else 1.0
    lines = apply_effects(uid, {"energy": -10, "health": int(6 * scale), "happiness": 3}, "ورزش")
    api.send_message(chat_id, "🏃 ورزش کردی!\n" + "\n".join(lines) +
                     ("\n🤒 هوا آلوده است؛ اثر ورزش کمتر شد." if scale < 1 else ""))


def do_fun(chat_id, uid):
    p = profile(uid)
    if p["money"] < 50:
        api.send_message(chat_id, "💸 برای تفریح حداقل ۵۰ تومان لازمه!")
        return
    lines = apply_effects(uid, {"money": -50, "happiness": 8, "energy": -5}, "تفریح")
    flavor = pick(["🎬 سینما رفتی", "🍨 بستنی خوردی", "🎧 موزیک گوش دادی", "🛍 وینداوشاپ کردی"])
    api.send_message(chat_id, f"🎉 {flavor}!\n" + "\n".join(lines))


# ───────── 👤 پروفایل ─────────

def panel_profile(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    inv = db.fetchall("""SELECT i.emoji,i.name FROM inventory inv JOIN items i ON i.id=inv.item_id
                         WHERE inv.user_id=? ORDER BY inv.id DESC""", (uid,))
    inv_txt = "، ".join(f"{r['emoji']} {r['name']}" for r in inv) if inv else "خالی"
    api.send_message(chat_id, render_profile(uid) + f"\n\n🎒 دارایی‌ها: {inv_txt}", MAIN_KB)


# ───────── 💼 شغل ─────────

def panel_job(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    p = profile(uid)
    if p["job_id"]:
        job = db.fetchone("SELECT * FROM jobs WHERE id=?", (p["job_id"],))
        rows = [[("🛠 کار کردن (-۲۰⚡)", "job:work")],
                [("📈 درخواست ارتقا", "job:promo"), ("🚪 استعفا", "job:quit")]]
        api.send_message(chat_id,
                         f"💼 شغل فعلی: {job['title']} — سطح {fn(p['job_level'])}\n"
                         f"💵 حقوق هر شیفت: حدود {fmt_money(int(job['base_salary'] * p['job_level'] * salary_mult(uid)))} تومان",
                         inline_keyboard(rows))
    else:
        skills = get_skills(uid)
        rows = []
        lines = ["💼 بازار کار — یکی رو انتخاب کن:\n"]
        for j in db.fetchall("SELECT * FROM jobs"):
            ok = (not j["min_skill"] or skills.get(j["min_skill"], 0) >= j["min_skill_level"]) and \
                 p["level"] >= j["min_level"]
            req = f"{SKILLS.get(j['min_skill'],'-')} {fn(j['min_skill_level'])}+ | لول {fn(j['min_level'])}+" if j["min_skill"] else "بدون شرط"
            mark = "✅" if ok else "🔒"
            lines.append(f"{mark} {j['title']} — 💵 {fmt_money(j['base_salary'])}/شیفت ({req})")
            if ok:
                rows.append([(f"استخدام: {j['title']}", f"job:apply:{j['id']}")])
        api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def job_apply(chat_id, uid, job_id):
    job = db.fetchone("SELECT * FROM jobs WHERE id=?", (job_id,))
    p = profile(uid)
    skills = get_skills(uid)
    if not job:
        return "❌ چنین شغلی نیست!"
    if p["job_id"]:
        return "⚠️ اول استعفا بده!"
    if job["min_skill"] and skills.get(job["min_skill"], 0) < job["min_skill_level"]:
        return f"🔒 مهارت {SKILLS[job['min_skill']]} کافی نیست! (نیاز: {fn(job['min_skill_level'])})"
    if p["level"] < job["min_level"]:
        return f"🔒 لول شخصیت کم است! (نیاز: {fn(job['min_level'])})"
    set_profile(uid, job_id=job_id, job_level=1)
    log_action(uid, "job_apply", job_id)
    return f"🎉 تبریک! به‌عنوان {job['title']} استخدام شدی! از پنل «💼 شغل» کار کن."


def job_work(chat_id, uid):
    p = profile(uid)
    if not p["job_id"]:
        return "❌ شغلی نداری! اول استخدام شو."
    if not cooldown_ok(uid, "last_work", WORK_COOLDOWN):
        return f"⏳ خستگی داری! هر {fn(WORK_COOLDOWN)} ثانیه یک شیفت."
    if p["energy"] < WORK_ENERGY_COST:
        return "🔋 انرژی کافی برای کار نداری؛ استراحت کن."
    job = db.fetchone("SELECT * FROM jobs WHERE id=?", (p["job_id"],))
    salary = int(job["base_salary"] * p["job_level"] * salary_mult(uid) * random.uniform(0.9, 1.2))
    db.execute("UPDATE profiles SET energy=MAX(0,energy-?) WHERE user_id=?", (WORK_ENERGY_COST, uid))
    change_money(uid, salary, "salary", f"حقوق {job['title']}")
    lines = gain_xp(uid, 15)
    mission_progress(uid, "work")
    touch_cooldown(uid, "last_work")
    extra = ""
    if job["min_skill"] and random.random() < 0.25:
        nv = gain_skill(uid, job["min_skill"])
        extra = f"\n📈 {SKILLS[job['min_skill']]} +۱ (لول {fn(nv)})"
    return (f"🛠 یک شیفت {job['title']} کامل کردی!\n💵 درآمد: {fmt_money(salary)} تومان"
            f"\n⭐ +۱۵ XP | ⚡ -۲۰ انرژی{extra}" + ("\n" + "\n".join(lines) if lines else ""))


def job_promo(chat_id, uid):
    p = profile(uid)
    if not p["job_id"]:
        return "❌ شغلی نداری!"
    if p["job_level"] >= 5:
        return "👑 در بالاترین سطح شغلی هستی!"
    job = db.fetchone("SELECT * FROM jobs WHERE id=?", (p["job_id"],))
    skills = get_skills(uid)
    need_lvl = p["level"] >= (p["job_level"] + 1) * 2
    need_skill = not job["min_skill"] or skills.get(job["min_skill"], 0) >= job["min_skill_level"] + p["job_level"]
    if need_lvl and need_skill:
        set_profile(uid, job_level=p["job_level"] + 1)
        log_action(uid, "job_promo", f"{p['job_id']} lvl {p['job_level']+1}")
        return f"📈 ارتقا گرفتی! سطح شغلی: {fn(p['job_level']+1)} — حقوقت بیشتر شد! 🎉"
    return (f"🔒 شرایط ارتقا نداری:\n"
            f"• لول شخصیت ≥ {fn((p['job_level']+1)*2)}\n"
            f"• {SKILLS.get(job['min_skill'],'-')} ≥ {fn(job['min_skill_level']+p['job_level']) if job['min_skill'] else '-'}") or ""


def job_quit(chat_id, uid):
    if not profile(uid)["job_id"]:
        return "❌ شغلی نداری!"
    set_profile(uid, job_id=None, job_level=1)
    log_action(uid, "job_quit")
    return "🚪 استعفا دادی. می‌تونی شغل جدید بگیری!"


# ───────── 🛒 فروشگاه و 🏠 خانه ─────────

def panel_shop(chat_id, uid, category="shop"):
    if not guard_character(chat_id, uid):
        return
    items = db.fetchall("SELECT * FROM items WHERE is_active=1 AND category=?", (category,))
    title = "🛒 فروشگاه — خرج کن، قوی شو!" if category == "shop" else "🏠 بازار املاک — خونه‌دار شو!"
    lines = [title + "\n"]
    rows = []
    for it in items:
        owned = db.fetchone("SELECT id FROM inventory WHERE user_id=? AND item_id=?", (uid, it["id"]))
        mark = "✅ داری" if owned else f"💵 {fmt_money(it['price'])}"
        lines.append(f"{it['emoji']} {it['name']} — {mark}\n   ↳ {it['effect_text']}")
        if not owned:
            rows.append([(f"خرید {it['emoji']} {it['name']}", f"shop:buy:{it['id']}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def buy_item(chat_id, uid, item_id):
    it = db.fetchone("SELECT * FROM items WHERE id=? AND is_active=1", (item_id,))
    if not it:
        return "❌ آیتم پیدا نشد!"
    if db.fetchone("SELECT id FROM inventory WHERE user_id=? AND item_id=?", (uid, it["id"])):
        return "⚠️ این آیتم را از قبل داری!"
    p = profile(uid)
    if p["money"] < it["price"]:
        return f"💸 پولت کم است! نیاز: {fmt_money(it['price'])} تومان"
    change_money(uid, -it["price"], "purchase", f"خرید {it['name']}")
    db.execute("INSERT OR IGNORE INTO inventory(user_id,item_id,purchased_at) VALUES(?,?,?)",
               (uid, it["id"], now_iso()))
    lines = apply_effects(uid, jl(it["effect_json"], {}), f"خرید {it['name']}")
    if it["category"] == "house":
        set_profile(uid, home=f"{it['emoji']} {it['name']}")
    log_action(uid, "buy", f"{it['name']} @{it['price']}")
    return (f"🛍 خرید موفق: {it['emoji']} {it['name']}\n"
            f"💸 پرداخت: {fmt_money(it['price'])} تومان\n\n📊 اثر:\n" + ("\n".join(lines) or "—"))


# ───────── 💰 اقتصاد ─────────

def panel_economy(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    p = profile(uid)
    rows = [
        [("🛒 فروشگاه", "eco:shop"), ("📈 سرمایه‌گذاری", "eco:inv")],
        [("🧾 تراکنش‌های اخیر", "eco:tx")],
    ]
    api.send_message(chat_id,
                     f"💰 دفترچه‌ی اقتصاد\n💳 موجودی: {fmt_money(p['money'])} تومان\n"
                     f"📊 نرخ درآمد سرور: ×{get_setting('income_rate','1')}",
                     inline_keyboard(rows))


def panel_invest(chat_id, uid):
    rows = [[("🟢 ۱۰٪ دارایی (ریسک کم)", "inv:small")],
            [("🟡 ۳۰٪ دارایی (ریسک متوسط)", "inv:mid")],
            [("🔴 ۶۰٪ دارایی (ریسک بالا)", "inv:big")]]
    api.send_message(chat_id, "📈 میزان ورود به سرمایه‌گذاری رو انتخاب کن:\n"
                              "شانس برد با 🧠 هوش و 🎲 ریسک‌پذیری بیشتر می‌شه!", inline_keyboard(rows))


def do_invest(chat_id, uid, tier):
    p = profile(uid)
    frac = {"small": 0.10, "mid": 0.30, "big": 0.60}[tier]
    stake = int(p["money"] * frac)
    if stake < 100:
        return "💸 حداقل ۱۰۰ تومان سرمایه لازمه!"
    skills = get_skills(uid)
    chance = 0.45 + skills.get("int", 0) * 0.01 + (0.10 if p["trait"] == "risky" else 0) \
             - {"small": 0, "mid": 0.05, "big": 0.10}[tier]
    win = random.random() < chance
    if win:
        gain = int(stake * random.uniform(0.3, 0.9))
        change_money(uid, gain, "invest", "سود سرمایه‌گذاری")
        lines = gain_xp(uid, 20)
        log_action(uid, "invest_win", f"stake={stake} gain={gain}")
        return (f"📈✅ سرمایه‌گذاری سود داد!\n💰 سود: +{fmt_money(gain)} تومان\n"
                f"(ورودی: {fmt_money(stake)})" + ("\n" + "\n".join(lines) if lines else ""))
    loss = int(stake * random.uniform(0.5, 1.0))
    change_money(uid, -loss, "invest", "زیان سرمایه‌گذاری")
    log_action(uid, "invest_loss", f"stake={stake} loss={loss}")
    return f"📉❌ بازار ریخت!\n💸 ضرر: -{fmt_money(loss)} تومان\n(ورودی: {fmt_money(stake)})"


def panel_transactions(chat_id, uid):
    rows = db.fetchall("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,))
    if not rows:
        api.send_message(chat_id, "🧾 تراکنشی نداری.")
        return
    lines = ["🧾 تراکنش‌های اخیر:\n"]
    for t in rows:
        sign = "+" if t["amount"] > 0 else ""
        lines.append(f"• {sign}{fmt_money(t['amount'])} 💰 | {t['description']} | {t['type']}")
    api.send_message(chat_id, "\n".join(lines))


# ───────── 📚 مهارت‌ها ─────────

def panel_skills(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    skills = get_skills(uid)
    p = profile(uid)
    rows = []
    lines = ["📚 مهارت‌های تو:\n"]
    for k, name in SKILLS.items():
        lvl = skills.get(k, 0)
        cost = 120 * (lvl + 1)
        lines.append(f"{name}: لول {fn(lvl)}/۱۰ {bar(lvl*10, 10)}")
        if lvl < 10:
            rows.append([(f"{name} | تمرین: {fmt_money(cost)}💰 + {fn(TRAIN_ENERGY_COST)}⚡", f"sk:train:{k}")])
    lines.append(f"\n💰 موجودی: {fmt_money(p['money'])} | ⚡ {fn(p['energy'])}")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def train_skill(chat_id, uid, key):
    if key not in SKILLS:
        return "❌ مهارت نامعتبر!"
    skills = get_skills(uid)
    lvl = skills.get(key, 0)
    if lvl >= 10:
        return "👑 این مهارت حداکثر است!"
    cost = 120 * (lvl + 1)
    p = profile(uid)
    if p["money"] < cost:
        return f"💸 هزینه‌ی تمرین {fmt_money(cost)} تومانه؛ پولت کم است."
    if p["energy"] < TRAIN_ENERGY_COST:
        return "🔋 برای تمرین انرژی نداری؛ استراحت کن."
    change_money(uid, -cost, "training", f"تمرین {SKILLS[key]}")
    db.execute("UPDATE profiles SET energy=MAX(0,energy-?) WHERE user_id=?", (TRAIN_ENERGY_COST, uid))
    nv = gain_skill(uid, key)
    lines = gain_xp(uid, 10)
    mission_progress(uid, "train")
    log_action(uid, "skill_train", f"{key} -> {nv}")
    return (f"📚 تمرین موفق! {SKILLS[key]} → لول {fn(nv)}\n"
            f"💸 -{fmt_money(cost)} | ⚡ -{fn(TRAIN_ENERGY_COST)} | ⭐ +۱۰ XP"
            + ("\n" + "\n".join(lines) if lines else ""))


# ───────── 👥 روابط (NPC) ─────────

def panel_relations(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    npcs = get_npcs(uid)
    lines = ["👥 آدم‌های زندگی تو:\n"]
    rows = []
    for n in npcs:
        rel = n["relation"]
        lines.append(f"{n['role']}: {n['name']} — {n['personality']}",
                    )
        lines.append(f"   {relation_label(rel)} {bar(rel)} {fn(rel)}")
        rows.append([(f"💬 گپ با {n['name']}", f"npc:chat:{n['npc_id']}"),
                     (f"🎁 هدیه (۲۰۰💰)", f"npc:gift:{n['npc_id']}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def npc_chat(chat_id, uid, npc_id):
    n = db.fetchone("SELECT * FROM npcs WHERE user_id=? AND npc_id=?", (uid, npc_id))
    p = profile(uid)
    if not n:
        return "❌ NPC پیدا نشد!"
    if p["energy"] < 5:
        return "🔋 حال حرف زدن نداری! استراحت کن."
    db.execute("UPDATE profiles SET energy=MAX(0,energy-5) WHERE user_id=?", (uid,))
    delta = random.randint(2, 6) + (2 if p["trait"] == "social" else 0)
    change_relation(uid, npc_id, delta)
    apply_effects(uid, {"happiness": 3}, "گپ با NPC")
    mission_progress(uid, "social")
    line = (pick(NPC_CHAT_LINES) if n["npc_id"] != "rival" else pick(RIVAL_LINES))
    line = line.replace("{name}", n["name"]).replace("{city}", p["city"])
    return f"{line}\n\n🤝 رابطه +{fn(delta)} (الان: {fn(min(100, n['relation']+delta))})"


def npc_gift(chat_id, uid, npc_id):
    n = db.fetchone("SELECT * FROM npcs WHERE user_id=? AND npc_id=?", (uid, npc_id))
    p = profile(uid)
    if not n:
        return "❌ NPC پیدا نشد!"
    if p["money"] < 200:
        return "💸 هدیه ۲۰۰ تومانه؛ پولت کم است."
    change_money(uid, -200, "gift", f"هدیه به {n['name']}")
    delta = random.randint(8, 15)
    change_relation(uid, npc_id, delta)
    reaction = pick([f"«{n['name']}» چشماش برق زد!", f"«{n['name']}» لبخند بزرگی زد!",
                     f"«{n['name']}» گفت: تو بهترینی!"])
    return f"🎁 هدیه را دادی. {reaction}\n🤝 رابطه +{fn(delta)} (💸 -۲۰۰ تومان)"


# ───────── 🎯 ماموریت‌ها ─────────

def panel_missions(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    ensure_missions(uid)
    rows = db.fetchall("SELECT * FROM missions WHERE user_id=? AND day=?", (uid, today()))
    lines = ["🎯 ماموریت‌های امروز:\n"]
    btns = []
    for m in rows:
        reward = jl(m["reward"], {})
        r_txt = "، ".join((f"{fmt_money(v)}💰" if k == "money" else f"{fn(v)} {'⭐' if k=='xp' else '😊'}")
                          for k, v in reward.items())
        if m["done"]:
            status = "✅ انجام شد"
        elif m["progress"] >= m["target"]:
            status = "🎁 آماده‌ی دریافت!"
            btns.append([(f"دریافت جایزه: {m['title']}", f"ms:claim:{m['id']}")])
        else:
            status = f"⏳ {fn(m['progress'])}/{fn(m['target'])}"
        lines.append(f"{m['title']}\n   {status} | جایزه: {r_txt}")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(btns) if btns else None)


def claim_mission(chat_id, uid, mission_id):
    m = db.fetchone("SELECT * FROM missions WHERE id=? AND user_id=?", (mission_id, uid))
    if not m:
        return "❌ ماموریت پیدا نشد!"
    if m["done"]:
        return "⚠️ جایزه را قبلا گرفتی!"
    if m["progress"] < m["target"]:
        return "⏳ ماموریت کامل نشده!"
    lines = apply_effects(uid, jl(m["reward"], {}), f"ماموریت: {m['title']}")
    db.execute("UPDATE missions SET done=1 WHERE id=?", (mission_id,))
    return f"🎁 جایزه‌ی «{m['title']}» دریافت شد!\n" + "\n".join(lines)


# ───────── 🏆 رتبه‌بندی ─────────

def panel_leaderboard(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    top_money = db.fetchall("SELECT name, money, level FROM profiles ORDER BY money DESC LIMIT 10")
    top_level = db.fetchall("SELECT name, level, xp FROM profiles ORDER BY level DESC, xp DESC LIMIT 5")
    lines = ["🏆 تابلوی افتخار\n\n💰 ثروتمندترین‌ها:"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(top_money):
        m = medals[i] if i < 3 else f"{fn(i+1)}."
        lines.append(f"{m} {r['name']} — {fmt_money(r['money'])} تومان (لول {fn(r['level'])})")
    lines.append("\n⭐ قدرتمندترین‌ها:")
    for i, r in enumerate(top_level):
        m = medals[i] if i < 3 else f"{fn(i+1)}."
        lines.append(f"{m} {r['name']} — لول {fn(r['level'])}")
    top_guilds = db.fetchall("SELECT name, bank, donations FROM guilds ORDER BY donations DESC LIMIT 3")
    if top_guilds:
        lines.append("\n🤝 اتحادهای برتر:")
        for i, g in enumerate(top_guilds):
            lines.append(f"{medals[i]} {g['name']} — خزانه {fmt_money(g['bank'])}")
    api.send_message(chat_id, "\n".join(lines), MAIN_KB)


# ───────── ⚙ تنظیمات ─────────

def panel_settings(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    rows = [
        [("✏️ تغییر نام", "set:rename")],
        [("📣 اطلاعیه‌ها", "set:news"), ("❓ راهنما", "set:help")],
        [("🔄 شروع زندگی جدید (ریست)", "set:reset")],
    ]
    api.send_message(chat_id, "⚙ تنظیمات Life Simulator:", inline_keyboard(rows))


def panel_help(chat_id):
    api.send_message(chat_id, (
        "❓ راهنمای بازی:\n\n"
        "🎮 بازی → هر روز اتفاق‌هایی می‌افتد؛ انتخاب‌هات آینده‌ات را می‌سازند.\n"
        "💼 شغل → استخدام شو، کار کن، ارتقا بگیر.\n"
        "💰 اقتصاد → خرید و سرمایه‌گذاری.\n"
        "📚 مهارت‌ها → مهارت بساز تا شغل‌های بهتر بگیری.\n"
        "👥 روابط → با NPCها دوست شو یا با رقیبت بجنگ.\n"
        "🎯 ماموریت‌ها → کارهای روزانه با جایزه.\n"
        "🏆 رتبه‌بندی → ببین کی سلطان شهر است!\n\n"
        "⚡ انرژی محدود است؛ با «استراحت» شارژش کن."
    ))


# ══════════════════════════════════════════════════════════════════
# [7.5] 🆕 بازار بورس، جنگ (PvP + باس)، فروشگاه VIP و کانال اخبار
# ══════════════════════════════════════════════════════════════════

# ───── ابزارهای مشترک ─────

def get_admins():
    return {r["user_id"] for r in db.fetchall("SELECT user_id FROM admins")} | set(ADMIN_IDS)

def notify_admins(text, inline=None):
    for aid in get_admins():
        api.send_message(aid, text, inline)

def channel_news(text):
    """ارسال خودکار خبر به کانال (اگر تنظیم شده باشد)"""
    ch = get_setting("channel", CHANNEL_DEFAULT)
    if not ch:
        return False
    res = api.call("sendMessage", chat_id=ch, text=f"📡 «Life Simulator AI»\n\n{text}")
    if not res:
        log.warning(f"📡 ارسال به کانال ناموفق بود ({ch}) — آیا ربات ادمین کانال است؟")
    return bool(res)

def add_gems(uid, amount):
    db.execute("UPDATE profiles SET gems=MAX(0, COALESCE(gems,0)+?) WHERE user_id=?", (amount, uid))

def is_shielded(p):
    return bool(p.get("shield_until")) and datetime.fromisoformat(p["shield_until"]) > datetime.now()

def battle_power(uid):
    p = profile(uid)
    if not p:
        return 0
    power = p["level"] * 10 + sum(get_skills(uid).values()) * 4
    bonus_items = {"ماشین": 8, "لپ‌تاپ": 4, "کنسول بازی": 6, "ویلای لوکس": 10}
    for (name,) in db.fetchall("""SELECT i.name FROM inventory inv JOIN items i ON i.id=inv.item_id
                                   WHERE inv.user_id=?""", (uid,)):
        power += bonus_items.get(name, 0)
    if p.get("vip"):
        power += 10
    r = ensure_resources(uid)          # ارتش هم به قدرت جنگ کمک می‌کند
    power += int(r["soldiers"] * 0.5) + r["wall"] * 3
    pet = pet_of(uid)                  # پت هم قدرت می‌دهد (اگر گرسنه نیست)
    if pet:
        sp = next((x for x in PETS if x[0] == pet["species"]), None)
        if sp:
            base = sp[4] + pet["level"]
            power += base if pet["hunger"] < 80 else base // 2
    return power


# ══════════════════════════════════════════════════════════════════
# [7.8] 🆕 v3: امپراتوری (منابع/ساختمان/ارتش) و هک (حمله/دفاع/دوئل)
# ══════════════════════════════════════════════════════════════════

# ───── 🏰 منابع و ساختمان‌ها ─────

def ensure_resources(uid):
    r = db.fetchone("SELECT * FROM resources WHERE user_id=?", (uid,))
    if not r:
        db.execute("INSERT INTO resources(user_id,last_tick) VALUES(?,?)", (uid, now_iso()))
        r = db.fetchone("SELECT * FROM resources WHERE user_id=?", (uid,))
    return dict(r)

def tick_base(uid):
    """
    تیک‌های تنبل امپراتوری: هر ۶ ساعت
    مزرعه/معدن تولید می‌کنند، سربازها غذا می‌خورند، بیمارستان مجروح‌ها را درمان می‌کند.
    اگر غذا تمام شود، سربازها می‌میرند!
    """
    r = ensure_resources(uid)
    if not r["last_tick"]:
        db.execute("UPDATE resources SET last_tick=? WHERE user_id=?", (now_iso(), uid))
        return []
    try:
        elapsed = (datetime.now() - datetime.fromisoformat(r["last_tick"])).total_seconds()
    except Exception:
        elapsed = 0
    ticks = int(elapsed // TICK_SEC)
    if ticks <= 0:
        return []
    ticks = min(ticks, 16)  # سقف ضدتقلب (حداکثر ۴ روز آفلاین)
    news = []
    food  = r["food"] + ticks * r["farm"] * 5
    iron  = r["iron"] + ticks * r["mine"] * 3
    if ticks * r["farm"] * 5 or ticks * r["mine"] * 3:
        news.append(f"🚜 تولید: +{fn(ticks*r['farm']*5)} غذا | ⛏ +{fn(ticks*r['mine']*3)} آهن")
    soldiers, wounded, med = r["soldiers"], r["wounded"], r["medicine"]
    need = soldiers * 0.4 * ticks
    if food >= need:
        food -= need
    else:
        shortage = need - food
        food = 0
        deaths = min(soldiers, int(shortage / 2) + 1)
        soldiers -= deaths
        news.append(f"☠️ قحطی! {fn(deaths)} سرباز از قحطی مردند — به ارتشت غذا برسان!")
    heals = min(wounded, r["hospital"] * ticks, int(med))
    if heals > 0:
        cap = r["barracks"] * 10
        heals = min(heals, max(0, cap - soldiers))
        wounded -= heals; med -= heals; soldiers += heals
        news.append(f"🏥 بیمارستان {fn(heals)} مجروح را درمان کرد")
    db.execute("""UPDATE resources SET food=?, iron=?, medicine=?, soldiers=?, wounded=?, last_tick=?
                  WHERE user_id=?""",
               (round(food, 2), round(iron, 2), round(med, 2), soldiers, wounded, now_iso(), uid))
    return news


def panel_empire(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    ensure_resources(uid)
    news = tick_base(uid)
    r = ensure_resources(uid)
    p = profile(uid)
    cap = r["barracks"] * 10
    lines = ["🏰 امپراتوری تو\n━━━━━━━━━━━\n"]
    if news:
        lines.extend(news); lines.append("━━━━━━━━━━━")
    lines += [
        f"🌾 غذا: {fn(round(r['food'],1))}  ⚒️ آهن: {fn(round(r['iron'],1))}  💊 دارو: {fn(int(r['medicine']))}",
        f"🪖 ارتش: {fn(r['soldiers'])}/{fn(cap)} سرباز (🤕 مجروح: {fn(r['wounded'])})",
        f"🍽 مصرف ارتش: {fn(round(r['soldiers']*0.4,1))} غذا / هر ۶ ساعت",
        "━━━━━━━━━━━",
        "🏗 ساختمان‌ها:",
    ]
    rows = []
    for b, (name, desc) in BUILDINGS.items():
        lvl = r[b]
        cost_m, cost_i = lvl * 400, lvl * 2
        lines.append(f"{name}: سطح {fn(lvl)} — {desc}")
        rows.append([(f"🔺 {name} → سطح {fn(lvl+1)} ({fmt_money(cost_m)}💰+{fn(cost_i)}⚒️)", f"emp:up:{b}")])
    rows.append([("🌾 خرید مواد", "emp:shop"), ("🪖 استخدام سرباز (۵۰💰+۱غذا)", "emp:recruit")])
    rows.append([("⚔️ حمله‌ی ارتشی (غارت منابع دشمن!)", "emp:raid")])
    lines.append(f"\n💰 موجودی: {fmt_money(p['money'])}")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def panel_emp_shop(chat_id, uid):
    rows = [[(f"{v[0]} — {fmt_money(v[2])}💰", f"emp:buy:{k}")] for k, v in RES_SHOP.items()]
    api.send_message(chat_id, "🌾 بازار مواد اولیه — برای زنده نگه داشتن ارتشت:", inline_keyboard(rows))


def empire_buy_res(chat_id, uid, kind):
    v = RES_SHOP.get(kind)
    if not v:
        return "❌"
    p = profile(uid)
    if p["money"] < v[2]:
        return f"💸 {fmt_money(v[2])} تومان لازم است."
    col = {"food": "food", "med": "medicine", "iron": "iron"}[kind]
    change_money(uid, -v[2], "resource", f"خرید {v[0]}")
    db.execute(f"UPDATE resources SET {col}={col}+? WHERE user_id=?", (v[1], uid))
    log_action(uid, "emp_buy", kind)
    return f"✅ {v[0]} خریدی! انبارت شارژ شد. ({fmt_money(v[2])} تومان)"


def empire_upgrade(chat_id, uid, b):
    if b not in BUILDINGS:
        return "❌"
    r = ensure_resources(uid)
    lvl = r[b]
    if lvl >= 10:
        return "👑 این ساختمان در حداکثر سطح است!"
    cost_m, cost_i = lvl * 400, lvl * 2
    p = profile(uid)
    if p["money"] < cost_m:
        return f"💸 {fmt_money(cost_m)} تومان لازم است."
    if r["iron"] < cost_i:
        return f"⚒️ {fn(cost_i)} آهن لازم است (داری: {fn(round(r['iron'],1))}) — از فروش مواد بخر یا معدنت را ارتقا بده."
    change_money(uid, -cost_m, "build", f"ارتقای {BUILDINGS[b][0]}")
    db.execute(f"UPDATE resources SET {b}={b}+1, iron=iron-? WHERE user_id=?", (cost_i, uid))
    log_action(uid, "emp_upgrade", f"{b}->{lvl+1}")
    return f"🔺 {BUILDINGS[b][0]} به سطح {fn(lvl+1)} رسید! 🎉"


def empire_recruit(chat_id, uid):
    r = ensure_resources(uid)
    p = profile(uid)
    if r["soldiers"] >= r["barracks"] * 10:
        return "🏟 سربازخانه پر است! اول ارتقاش بده."
    if p["money"] < 50:
        return "💸 هر سرباز ۵۰ تومان + ۱ غذا است."
    if r["food"] < 1:
        return "🌾 غذا نداری! از فروش مواد بخر."
    change_money(uid, -50, "army", "استخدام سرباز")
    db.execute("UPDATE resources SET soldiers=soldiers+1, food=food-1 WHERE user_id=?", (uid,))
    return f"🪖 یک سرباز جدید استخدام شد! ارتش: {fn(r['soldiers']+1)} — حواست به غذاشان باشد!"


def empire_raid_targets(chat_id, uid):
    rows = []
    for t in db.fetchall("""SELECT p.user_id, p.name, r.soldiers FROM profiles p
                            JOIN users u ON u.user_id=p.user_id
                            LEFT JOIN resources r ON r.user_id=p.user_id
                            WHERE p.user_id!=? AND u.is_banned=0
                            ORDER BY u.last_seen DESC LIMIT 8""", (uid,)):
        rows.append([(f"⚔️ غارت {t['name']} (🪖 {fn(t['soldiers'] or 0)})", f"emp:atk:{t['user_id']}")])
    api.send_message(chat_id, "⚔️ قلمروی دشمن را برای غارت انتخاب کن:", inline_keyboard(rows))


def empire_raid(chat_id, uid, target_id):
    if target_id == uid:
        return "😂 به خودت حمله نکن!"
    a, d = ensure_resources(uid), ensure_resources(target_id)
    p = profile(uid)
    if not cooldown_ok_raid(uid, RAID_COOLDOWN):
        return f"⏳ ارتشت خسته است! هر {fn(RAID_COOLDOWN//60)} دقیقه یک غارت."
    if a["soldiers"] < 2:
        return "🪖 حداقل ۲ سرباز برای غارت لازم است؛ استخدام کن!"
    if p["energy"] < 20:
        return "🔋 انرژی کم است."
    db.execute("UPDATE profiles SET energy=MAX(0,energy-20) WHERE user_id=?", (uid,))
    db.execute("UPDATE resources SET last_raid=? WHERE user_id=?", (now_iso(), uid))
    mission_progress(uid, "war")
    ap = a["soldiers"] * random.uniform(0.9, 1.2) + battle_power(uid) * 0.1
    dp = d["soldiers"] * random.uniform(0.9, 1.2) + d["wall"] * 3
    tname = (profile(target_id) or {}).get("name", "دشمن")

    def lose_soldiers(rs, pct):
        dead = int(rs["soldiers"] * pct)
        wnd = int(dead * 0.35)
        return dead - wnd, wnd

    if ap > dp:  # پیروزی غارتگر
        stolen = {}
        for col in ("food", "iron", "medicine"):
            amt = int(d[col] * random.uniform(0.10, 0.20))
            if amt > 0:
                db.execute(f"UPDATE resources SET {col}={col}-? WHERE user_id=?", (amt, target_id))
                db.execute(f"UPDATE resources SET {col}={col}+? WHERE user_id=?", (amt, uid))
                stolen[col] = amt
        money_loot = min(int(profile(target_id)["money"] * 0.04), 3000)
        if money_loot > 0:
            change_money(target_id, -money_loot, "raid", f"غارت ارتشی توسط {p['name']}")
            change_money(uid, money_loot, "raid", f"غارت قلمروی {tname}")
        ad, aw = lose_soldiers(a, random.uniform(0.03, 0.10))
        dd, dw = lose_soldiers(d, random.uniform(0.15, 0.30))
        db.execute("UPDATE resources SET soldiers=MAX(0,soldiers-?),wounded=wounded+? WHERE user_id=?", (ad, aw, uid))
        db.execute("UPDATE resources SET soldiers=MAX(0,soldiers-?),wounded=wounded+? WHERE user_id=?", (dd, dw, target_id))
        gain_xp(uid, 30)
        st_txt = "، ".join(f"{v} {'🌾' if k=='food' else '⚒️' if k=='iron' else '💊'}" for k, v in stolen.items()) or "هیچی"
        res = f"🏰⚔️ ارتش {p['name']} قلمروی {tname} را غارت کرد! ({st_txt} + {fmt_money(money_loot)} 💰)"
        api.send_message(target_id, f"🚨 قلمرویت غارت شد!\n{res}\n🏥 مجروحانت را درمان کن و انتقام بگیر!")
        if (a["soldiers"] + d["soldiers"]) >= 30:
            channel_news(f"🏰 جنگ ارتش‌ها!\n\n{res}")
        log_action(uid, "raid_win", f"vs {target_id} {stolen} money={money_loot}")
        return (f"🏆 غارت موفق!\n🎁 منابع ربوده‌شده: {st_txt}\n💰 +{fmt_money(money_loot)} تومان\n"
                f"🪖 تلفات تو: {fn(ad)} کشته، {fn(aw)} مجروح | ⭐ +۳۰ XP")
    # شکست غارتگر
    ad, aw = lose_soldiers(a, random.uniform(0.15, 0.30))
    dd, dw = lose_soldiers(d, random.uniform(0.03, 0.08))
    db.execute("UPDATE resources SET soldiers=MAX(0,soldiers-?),wounded=wounded+? WHERE user_id=?", (ad, aw, uid))
    db.execute("UPDATE resources SET soldiers=MAX(0,soldiers-?),wounded=wounded+? WHERE user_id=?", (dd, dw, target_id))
    gain_xp(uid, 10)
    res = f"🛡 ارتش {tname} غارت {p['name']} را دفع کرد!"
    api.send_message(target_id, f"🛡 دفاع موفق! {res}")
    log_action(uid, "raid_lose", f"vs {target_id}")
    return (f"❌ غارت شکست خورد! دیوار و ارتش {tname} محکم بود.\n"
            f"🪖 تلفات سنگین تو: {fn(ad)} کشته، {fn(aw)} مجروح — از بیمارستانت استفاده کن! 🏥")


def cooldown_ok_raid(uid, seconds):
    r = db.fetchone("SELECT last_raid FROM resources WHERE user_id=?", (uid,))
    last = r["last_raid"] if r else None
    return (not last) or ((datetime.now() - datetime.fromisoformat(last)).total_seconds() >= seconds)


# ───── 🕶 هک و امنیت سایبری ─────

def hack_stats(uid):
    atk = def_ = 0
    for (tid,) in db.fetchall("SELECT tool_id FROM hack_gear WHERE user_id=?", (uid,)):
        tool = HACK_ALL.get(tid)
        if not tool:
            continue
        if any(t[0] == tid for t in HACK_ATK):
            atk += tool[2]
        else:
            def_ += tool[2]
    sk = get_skills(uid).get("hack", 0)
    return atk + sk * 2, def_ + sk


def panel_hack(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    atk, dfn = hack_stats(uid)
    p = profile(uid)
    lines = (f"🕶 مرکز عملیات سایبری\n━━━━━━━━━━━\n"
             f"🔓 قدرت نفوذ: {fn(atk)} | 🛡 قدرت دفاع: {fn(dfn)}\n"
             f"⚡ هر هک: -{fn(HACK_ENERGY_COST)} انرژی | 🕐 کول‌داون {fn(HACK_COOLDOWN//60)} دقیقه\n\n"
             "🎯 هک = دزدیدن پول و منابع قربانی!\n"
             "⚔️ دوئل = نبرد با شرط نقدی، برنده همه را می‌برد!")
    rows = [[("🛒 فروشگاه تجهیزات هک", "hk:shop")],
            [("🎯 هک کردن و دزدی منابع", "hk:targets")],
            [("⚔️ دوئلِ هک با شرط نقدی", "hk:dueltg")]]
    my_duels = db.fetchall("""SELECT * FROM duels WHERE opponent=? AND status='pending'""", (uid,))
    if my_duels:
        lines += ["\n📩 درخواست‌های دوئل:"]
        for d in my_duels:
            cn = (profile(d["challenger"]) or {}).get("name", "?")
            rows.append([(f"⚔️ قبول دوئل {cn} — شرط {fmt_money(d['stake'])}", f"hk:acc:{d['id']}"),
                         ("❌ رد", f"hk:dec:{d['id']}")])
    api.send_message(chat_id, lines, inline_keyboard(rows))


def panel_hack_shop(chat_id, uid):
    owned = {r["tool_id"] for r in db.fetchall("SELECT tool_id FROM hack_gear WHERE user_id=?", (uid,))}
    lines = ["🛒 بازار سیاه سایبری — دیر جنس بدن، نقره دعا\n"]
    rows = []
    lines.append("🔓 تجهیزات حمله:")
    for t in HACK_ATK:
        mark = "✅ داری" if t[0] in owned else f"💵 {fmt_money(t[3])}"
        lines.append(f"{t[1]} — قدرت +{fn(t[2])} نفوذ ({mark})")
        if t[0] not in owned:
            rows.append([(f"خرید {t[1]}", f"hk:buy:{t[0]}")])
    lines.append("🛡 تجهیزات دفاع:")
    for t in HACK_DEF:
        mark = "✅ داری" if t[0] in owned else f"💵 {fmt_money(t[3])}"
        lines.append(f"{t[1]} — قدرت +{fn(t[2])} دفاع ({mark})")
        if t[0] not in owned:
            rows.append([(f"خرید {t[1]}", f"hk:buy:{t[0]}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def hack_buy(chat_id, uid, tool_id):
    tool = HACK_ALL.get(tool_id)
    if not tool:
        return "❌"
    if db.fetchone("SELECT 1 FROM hack_gear WHERE user_id=? AND tool_id=?", (uid, tool_id)):
        return "⚠️ این ابزار را داری!"
    p = profile(uid)
    if p["money"] < tool[3]:
        return f"💸 {fmt_money(tool[3])} تومان لازم است."
    change_money(uid, -tool[3], "hackgear", f"خرید {tool[1]}")
    db.execute("INSERT INTO hack_gear(user_id,tool_id) VALUES(?,?)", (uid, tool_id))
    log_action(uid, "hack_buy", tool_id)
    return f"🕶 {tool[1]} خریدی! هکر واقعی شدی. حالا برو شکار کن 😈"


def hack_targets(chat_id, uid, for_duel=False):
    rows = []
    for t in db.fetchall("""SELECT p.user_id, p.name, p.level FROM profiles p
                            JOIN users u ON u.user_id=p.user_id
                            WHERE p.user_id!=? AND u.is_banned=0
                            ORDER BY u.last_seen DESC LIMIT 8""", (uid,)):
        if for_duel:
            rows.append([(f"⚔️ دوئل با {t['name']}", f"hk:dstk:{t['user_id']}")])
        else:
            rows.append([(f"🎯 هک {t['name']} (لول {fn(t['level'])})", f"hk:atk:{t['user_id']}")])
    api.send_message(chat_id, "🎯 هدفت را انتخاب کن:" if not for_duel else "⚔️ با کی دوئل می‌دی؟",
                     inline_keyboard(rows))


def hack_cooldown_ok(uid):
    r = db.fetchone("SELECT last_hack FROM resources WHERE user_id=?", (uid,))
    last = r["last_hack"] if r else None
    return (not last) or ((datetime.now() - datetime.fromisoformat(last)).total_seconds() >= HACK_COOLDOWN)


def hack_attack(chat_id, uid, target_id):
    if target_id == uid:
        return "😂 خودت را هک نکن!"
    tp = profile(target_id)
    if not tp:
        return "❌ هدف کاراکتر ندارد!"
    p = profile(uid)
    ensure_resources(uid); ensure_resources(target_id)
    if not hack_cooldown_ok(uid):
        return f"⏳ ردت را پاک کرده‌اند؟ صبر کن! هر {fn(HACK_COOLDOWN//60)} دقیقه یک هک."
    if p["energy"] < HACK_ENERGY_COST:
        return "🔋 انرژی کمی داری."
    db.execute("UPDATE profiles SET energy=MAX(0,energy-?) WHERE user_id=?", (HACK_ENERGY_COST, uid))
    db.execute("UPDATE resources SET last_hack=? WHERE user_id=?", (now_iso(), uid))
    atk, _ = hack_stats(uid)
    _, dfn = hack_stats(target_id)
    a = atk * random.uniform(0.8, 1.3)
    d = dfn * random.uniform(0.8, 1.3)

    if a > d:  # نفوذ موفق — منابع از قربانی دزدیده می‌شود و به هکر داده می‌شود
        money_steal = min(int(tp["money"] * random.uniform(0.03, 0.07)), 4000)
        if money_steal > 0:
            change_money(target_id, -money_steal, "hack", f"هک توسط {p['name']}")
            change_money(uid, money_steal, "hack", f"هک {tp['name']}")
        stolen = []
        tr = ensure_resources(target_id)
        for col, emo in (("food", "🌾"), ("iron", "⚒️"), ("medicine", "💊")):
            amt = int(tr[col] * random.uniform(0.10, 0.20))
            if amt > 0:
                db.execute(f"UPDATE resources SET {col}={col}-? WHERE user_id=?", (amt, target_id))
                db.execute(f"UPDATE resources SET {col}={col}+? WHERE user_id=?", (amt, uid))
                stolen.append(f"{fn(amt)} {emo}")
        gain_xp(uid, 30)
        if random.random() < 0.4:
            nv = gain_skill(uid, "hack")
            stolen.append(f"🕶 مهارت هک → لول {fn(nv)}")
        api.send_message(target_id,
                         f"🚨 هک شدی!\n{p['name']} به سیستم‌ات نفوذ کرد و {fmt_money(money_steal)} تومان "
                         f"و {('، '.join(stolen[:-1])) or 'چیزی'} ازت دزدید!\n🛡 فایروال بخر تا نشود قربانی!")
        if money_steal >= 2000:
            channel_news(f"🕶 نفوذ بزرگ سایبری!\n{p['name']} سیستم {tp['name']} را هک کرد و غنائمی ربود!")
        log_action(uid, "hack_win", f"vs {target_id} money={money_steal}")
        return (f"💾 نفوذ موفق! سیستم {tp['name']} کرکره شد...\n"
                f"💰 غنیمت نقدی: +{fmt_money(money_steal)} تومان\n"
                f"📦 منابع ربوده‌شده: {('، '.join(stolen)) if stolen else 'هیچی'}\n⭐ +۳۰ XP")
    # نفوذ ناموفق — ردیابی!
    fine = min(300 + p["level"] * 20, p["money"])
    if fine > 0:
        change_money(uid, -fine, "hack_fine", f"جریمه ردیابی هک ناموفق ({tp['name']})")
    gain_xp(uid, 8)
    honey = " هانی‌پاتش ردت را لو داد! 🕸" if db.fetchone("SELECT 1 FROM hack_gear WHERE user_id=? AND tool_id='honeypot'", (target_id,)) else ""
    api.send_message(target_id, f"🛡 یک تلاش برای هک‌کردنت بود (از طرف {p['name']}) و دفعه شد!{honey}")
    log_action(uid, "hack_fail", f"vs {target_id} fine={fine}")
    return (f"❌ نفوذ ناموفق! فایروال {tp['name']} قوی‌تر بود.{honey}\n"
            f"💸 جریمه ردیابی: -{fmt_money(fine)} تومان\n"
            "🕶 تجهیزاتت را از فروشگاه هک آپگرید کن!")


# ───── ⚔️ دوئل هک (با شرط نقدی) ─────

def panel_duel_stake(chat_id, uid, target_id):
    t = profile(target_id)
    if not t:
        api.send_message(chat_id, "❌ هدف نیست."); return
    rows = [[(f"شرط {fmt_money(s)} 💰", f"hk:new:{target_id}:{s}")] for s in DUEL_STAKES]
    api.send_message(chat_id, f"⚔️ دوئل با {t['name']}\nشرط را انتخاب کن (هر دو شرط می‌بندند، برنده همه را می‌برد):",
                     inline_keyboard(rows))


def duel_create(chat_id, uid, target_id, stake):
    p, t = profile(uid), profile(target_id)
    if not t:
        return "❌ هدف نیست."
    if uid == target_id:
        return "😂 با خودت؟"
    if p["money"] < stake:
        return f"💸 برای بستن شرط {fmt_money(stake)} تومان لازم است."
    if db.fetchone("SELECT 1 FROM duels WHERE challenger=? AND status='pending'", (uid,)):
        return "⚠️ یک دوئل باز داری؛ صبر کن تا جواب بدهند."
    change_money(uid, -stake, "duel", f"وثیقه دوئل با {t['name']}")
    cur = db.execute("INSERT INTO duels(challenger,opponent,stake,status,created_at) VALUES(?,?,?,'pending',?)",
                     (uid, target_id, stake, now_iso()))
    did = cur.lastrowid
    api.send_message(target_id,
                     f"⚔️ چالش دوئل هک!\n{p['name']} تو را به دوئل سایبری با شرط {fmt_money(stake)} تومان دعوت کرده!\n"
                     f"اگر ببری {fmt_money(stake*2)} تا می‌گیری 😈\n\nاز پنل «🕶 هک» قبول یا رد کن.",
                     inline_keyboard([[("✅ قبول دوئل", f"hk:acc:{did}"), ("❌ رد", f"hk:dec:{did}")]]))
    log_action(uid, "duel_create", f"#{did} vs {target_id} stake={stake}")
    return (f"⚔️ مو자ویه ثبت شد! شرط {fmt_money(stake)} به امانت افتاد.\n"
            f"به {t['name']} خبر دادیم؛ اگه قبول کنه جنگ شروع می‌شه!")


def duel_accept(chat_id, uid, did):
    d = db.fetchone("SELECT * FROM duels WHERE id=?", (did,))
    if not d or d["opponent"] != uid or d["status"] != "pending":
        return "⚠️ دوئل معتبر نیست."
    p = profile(uid)
    if p["money"] < d["stake"]:
        return f"💸 برای قبول شرط، {fmt_money(d['stake'])} تومان لازم است."
    change_money(uid, -d["stake"], "duel", f"وثیقه دوئل #{did}")
    a, b = d["challenger"], uid
    pa, pb = profile(a), profile(b)
    atk_a, def_a = hack_stats(a)
    atk_b, def_b = hack_stats(b)
    wins_a = wins_b = 0
    rounds = []
    for i in range(3):
        sa = (atk_a + def_a * 0.5) * random.uniform(0.7, 1.3)
        sb = (atk_b + def_b * 0.5) * random.uniform(0.7, 1.3)
        if sa >= sb:
            wins_a += 1; rounds.append(f"راند {fn(i+1)}: {pa['name']} ⚡")
        else:
            wins_b += 1; rounds.append(f"راند {fn(i+1)}: {pb['name']} ⚡")
    winner, loser = (a, b) if wins_a > wins_b else (b, a)
    wp = profile(winner)
    prize = d["stake"] * 2
    change_money(winner, prize, "duel", f"برد دوئل #{did}")
    gain_xp(winner, 50); gain_xp(loser, 20)
    db.execute("UPDATE profiles SET reputation=MIN(100,reputation+3) WHERE user_id=?", (winner,))
    res = f"⚔️ دوئل: {pa['name']} {fn(wins_a)} — {fn(wins_b)} {pb['name']} | 🏆 {wp['name']}"
    db.execute("UPDATE duels SET status='done', result=?, finished_at=? WHERE id=?", (res, now_iso(), did))
    txt = ("\n".join(rounds) + f"\n━━━━━━━━━━━\n🏆 برنده نهایی: {wp['name']}!"
           f"\n💰 جایزه: {fmt_money(prize)} تومان | ⭐ +۵۰ XP")
    if prize >= 5000:
        channel_news(f"⚔️ دوئل تاریخی سایبری!\n\n{res}\n💰 {fmt_money(prize)} تومان جیب به جیب شد!")
    api.send_message(loser, f"😵 دوئل #{fn(did)} را باختی!\n{txt}")
    api.send_message(winner, f"🏆 در دوئل #{fn(did)} پیروز شدی!\n{txt}")
    log_action(uid, "duel_done", res)
    return txt


def duel_decline(chat_id, uid, did):
    d = db.fetchone("SELECT * FROM duels WHERE id=?", (did,))
    if not d or d["opponent"] != uid or d["status"] != "pending":
        return "⚠️ معتبر نیست."
    db.execute("UPDATE duels SET status='declined', finished_at=? WHERE id=?", (now_iso(), did))
    change_money(d["challenger"], d["stake"], "duel", f"برگشت وثیقه (رد دوئل #{did})")
    api.send_message(d["challenger"], f"🐔 {(profile(uid) or {})['name']} دوئلت را رد کرد! وثیقه برگشت.")
    return "رد شد؛ وثیقه‌اش برگشت."


# ───── 🏪 بازار بورس (قیمت‌های زنده) ─────

def update_market(force=False):
    """رندوم‌واک قیمت‌ها — هر MARKET_INTERVAL ثانیه + خبر خودکار در کانال"""
    rows = [dict(r) for r in db.fetchall("SELECT * FROM markets")]
    if not rows:
        return
    last = rows[0]["updated_at"]
    if not force and last and (datetime.now() - datetime.fromisoformat(last)).total_seconds() < MARKET_INTERVAL:
        return
    big_news = []
    for r in rows:
        base = MARKET_BASE.get(r["symbol"], r["price"])
        chg = random.uniform(-0.07, 0.07) + (r["trend"] or 0) * 0.02
        new_price = int(r["price"] * (1 + chg))
        new_price = max(int(base * 0.3), min(int(base * 4), new_price))   # کف/سقف ضدتقلب
        real_chg = new_price / r["price"] - 1 if r["price"] else 0
        db.execute("UPDATE markets SET prev_price=?, price=?, trend=?, updated_at=? WHERE symbol=?",
                   (r["price"], new_price, (r["trend"] or 0) + chg * 0.2, now_iso(), r["symbol"]))
        if abs(real_chg) >= 0.055:
            emo = "🚀" if real_chg > 0 else "🔻"
            pct = fn(f"{abs(real_chg)*100:.1f}") + "٪"
            big_news.append(f"{emo} {r['name']} {'پمپ' if real_chg > 0 else 'ریزش'} شد! ({pct})")
    if big_news:
        channel_news("🚨 خبر فوری از بازار!\n\n" + "\n".join(big_news) +
                     "\n\n🏪 توی بازار ربات خرید و فروش کن، از موج سواری سود ببر!")


def panel_market(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    update_market()
    p = profile(uid)
    lines = ["🏪 بازار سهام و دارایی\n━━━━━━━━━━━\n"]
    rows = []
    for r in db.fetchall("SELECT * FROM markets"):
        price, prev = r["price"], r["prev_price"] or r["price"]
        arrow = "📈" if price >= prev else "📉"
        pct = (price / prev - 1) * 100 if prev else 0
        lines.append(f"{r['name']}: {fmt_money(price)} تومان {arrow} {fn(f'{abs(pct):.1f}')}٪")
        held = db.fetchone("SELECT amount, avg_price FROM portfolio WHERE user_id=? AND symbol=?",
                           (uid, r["symbol"]))
        if held and held["amount"] > 0:
            val = held["amount"] * price
            pnl = (price / held["avg_price"] - 1) * 100 if held["avg_price"] else 0
            lines.append(f"   └ داراییت: {fn(round(held['amount'],2))} واحد (≈{fmt_money(val)}) | سود/زیان: {fn(f'{pnl:+.1f}')}٪")
        rows.append([(f"معامله {r['name']}", f"mrko:{r['symbol']}")])
    lines.append(f"\n💰 موجودی: {fmt_money(p['money'])} تومان | کارمزد: ۲٪")
    lines.append("⏱ قیمت‌ها هر ۲۰ دقیقه به‌روز می‌شوند")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def panel_market_trade(chat_id, uid, symbol):
    r = db.fetchone("SELECT * FROM markets WHERE symbol=?", (symbol,))
    if not r:
        api.send_message(chat_id, "❌ دارایی پیدا نشد."); return
    held = db.fetchone("SELECT amount FROM portfolio WHERE user_id=? AND symbol=?", (uid, symbol))
    held_txt = fn(round(held["amount"], 2)) if held and held["amount"] > 0 else "۰"
    rows = [
        [("۱ هزار", f"mrkb:{symbol}:1000"), ("۵ هزار", f"mrkb:{symbol}:5000"), ("۲۰ هزار", f"mrkb:{symbol}:20000")],
        [("💰 خرید با کل موجودی", f"mrkb:{symbol}:all"), (f"فروش همه ({held_txt} واحد)", f"mrks:{symbol}")],
    ]
    api.send_message(chat_id,
                     f"{r['name']} — قیمت لحظه‌ای: {fmt_money(r['price'])} تومان\nمبلغ خرید را انتخاب کن:",
                     inline_keyboard(rows))


def market_buy(chat_id, uid, symbol, amount_mode):
    r = db.fetchone("SELECT * FROM markets WHERE symbol=?", (symbol,))
    if not r:
        return "❌ دارایی پیدا نشد!"
    p = profile(uid)
    amount = p["money"] if amount_mode == "all" else int(amount_mode)
    if amount < 100:
        return "💸 حداقل خرید ۱۰۰ تومانه!"
    if amount > p["money"]:
        return f"💸 فقط {fmt_money(p['money'])} تومان داری!"
    fee = int(amount * TRADE_FEE)
    units = (amount - fee) / r["price"]
    held = db.fetchone("SELECT amount, avg_price FROM portfolio WHERE user_id=? AND symbol=?", (uid, symbol))
    if held and held["amount"] > 0:
        new_amt = held["amount"] + units
        new_avg = (held["amount"] * held["avg_price"] + units * r["price"]) / new_amt
        db.execute("UPDATE portfolio SET amount=?, avg_price=? WHERE user_id=? AND symbol=?",
                   (new_amt, new_avg, uid, symbol))
    else:
        db.execute("INSERT INTO portfolio(user_id,symbol,amount,avg_price) VALUES(?,?,?,?)",
                   (uid, symbol, units, r["price"]))
    change_money(uid, -amount, "trade", f"خرید {r['name']}")
    db.execute("UPDATE profiles SET energy=MAX(0,energy-3) WHERE user_id=?", (uid,))
    log_action(uid, "market_buy", f"{symbol} {amount}")
    if amount >= 50000:
        channel_news(f"🐋 معامله‌ی نهنگ! {p['name']} به ارزش {fmt_money(amount)} تومان {r['name']} خرید!")
    return (f"✅ خرید {r['name']} انجام شد!\n"
            f"📦 واحد: +{fn(round(units,3))} | قیمت: {fmt_money(r['price'])}\n"
            f"💸 پرداخت: {fmt_money(amount)} (کارمزد {fmt_money(fee)})")


def market_sell(chat_id, uid, symbol):
    r = db.fetchone("SELECT * FROM markets WHERE symbol=?", (symbol,))
    held = db.fetchone("SELECT amount, avg_price FROM portfolio WHERE user_id=? AND symbol=?", (uid, symbol))
    if not r or not held or held["amount"] <= 0:
        return "📭 چیزی برای فروش نداری!"
    gross = int(held["amount"] * r["price"])
    fee = int(gross * TRADE_FEE)
    net = gross - fee
    pnl = (r["price"] / held["avg_price"] - 1) * 100 if held["avg_price"] else 0
    db.execute("DELETE FROM portfolio WHERE user_id=? AND symbol=?", (uid, symbol))
    change_money(uid, net, "trade", f"فروش {r['name']}")
    db.execute("UPDATE profiles SET energy=MAX(0,energy-3) WHERE user_id=?", (uid,))
    log_action(uid, "market_sell", f"{symbol} +{net} pnl={pnl:.1f}%")
    return (f"✅ فروش {r['name']} انجام شد!\n"
            f"💰 دریافت: {fmt_money(net)} تومان (کارمزد {fmt_money(fee)})\n"
            f"{'🟢 سود' if pnl >= 0 else '🔴 زیان'}: {fn(f'{pnl:+.1f}')}٪")


# ───── ⚔️ جنگ: حمله به بازیکن + باس روزانه ─────

def panel_war(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    p = profile(uid)
    shield = f"🛡 سپر فعال تا {p['shield_until'][5:16]}" if is_shielded(p) else "🛡 بدون سپر!"
    lines = [f"⚔️ ارتش تو\n━━━━━━━━━━━\n"
             f"💪 قدرت جنگ: {fn(battle_power(uid))} | {shield}\n"
             f"🎯 هر حمله: -{fn(ATTACK_ENERGY_COST)}⚡ | غنیمت: تا ۸٪ پول حریف\n"]
    logs = db.fetchall("""SELECT * FROM war_log WHERE attacker=? OR defender=?
                          ORDER BY id DESC LIMIT 3""", (uid, uid))
    if logs:
        lines.append("📜 آخرین نبردها:")
        for w in logs:
            lines.append(f"• {w['result']}")
    rows = [[("🎯 انتخاب هدف برای حمله", "war:targets"), ("🐲 باس روزانه", "war:boss")],
            [("🛡 خرید سپر (۳۰ 💎)", "gem:shield"), ("💎 فروشگاه VIP", "vip:panel")]]
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def war_targets(chat_id, uid):
    rows = []
    for t in db.fetchall("""SELECT p.user_id, p.name, p.level, p.money FROM profiles p
                            JOIN users u ON u.user_id=p.user_id
                            WHERE p.user_id!=? AND u.is_banned=0
                            ORDER BY u.last_seen DESC LIMIT 8""", (uid,)):
        rows.append([(f"⚔️ حمله به {t['name']} (لول {fn(t['level'])})", f"war:atk:{t['user_id']}")])
    if not rows:
        api.send_message(chat_id, "🏜 هدفی پیدا نشد؛ باید بقیه بازی کنند!")
        return
    api.send_message(chat_id, "🎯 هدفت را انتخاب کن:", inline_keyboard(rows))


def war_attack(chat_id, uid, target_id):
    if target_id == uid:
        return "😂 با خودت نمی‌تونی بجنگی!"
    p, t = profile(uid), profile(target_id)
    if not t:
        return "❌ حریف کاراکتر ندارد!"
    if not cooldown_ok(uid, "last_attack", ATTACK_COOLDOWN):
        return f"⏳ خسته‌ای! هر {fn(ATTACK_COOLDOWN//60)} دقیقه یک حمله."
    if p["energy"] < ATTACK_ENERGY_COST:
        return "🔋 برای جنگ انرژی نداری؛ استراحت کن."
    today_att = db.fetchone("""SELECT COUNT(*) c FROM war_log
                               WHERE attacker=? AND defender=? AND created_at LIKE ?""",
                            (uid, target_id, today() + "%"))["c"]
    if today_att >= 1:
        return f"⚖️ امروز یک‌بار به {t['name']} حمله کردی؛ بذار نفس بکشه!"
    db.execute("UPDATE profiles SET energy=MAX(0,energy-?) WHERE user_id=?", (ATTACK_ENERGY_COST, uid))
    touch_cooldown(uid, "last_attack")
    mission_progress(uid, "war")

    if is_shielded(t):
        log_action(uid, "war_shielded", f"{uid}->{target_id}")
        api.send_message(target_id, f"🛡 سپرت تو را از حمله‌ی {p['name']} نجات داد!")
        return f"🛡 {t['name']} سپر فعال داشت؛ حمله بی‌اثر شد! (⚡ انرژی‌ات رفت)"

    pa = battle_power(uid) * random.uniform(0.8, 1.2)
    pd = battle_power(target_id) * random.uniform(0.8, 1.2)

    if pa >= pd:  # 🏆 پیروزی حمله‌کننده
        loot = min(int(t["money"] * 0.08), 5000 + p["level"] * 200, t["money"])
        if loot > 0:
            change_money(target_id, -loot, "war", f"غارت توسط {p['name']}")
            change_money(uid, loot, "war", f"غنیمت از {t['name']}")
        db.execute("UPDATE profiles SET health=MAX(0,health-15), happiness=MAX(0,happiness-5) WHERE user_id=?", (target_id,))
        lines = gain_xp(uid, 25)
        db.execute("UPDATE profiles SET reputation=MIN(100,reputation+3) WHERE user_id=?", (uid,))
        res = f"⚔️ {p['name']} به {t['name']} حمله کرد و {fmt_money(loot)} تومان غارت کرد!"
        db.execute("INSERT INTO war_log(attacker,defender,result,loot,created_at) VALUES(?,?,?,?,?)",
                   (uid, target_id, res, loot, now_iso()))
        api.send_message(target_id,
                         f"💥 بهت حمله شد! {p['name']} {fmt_money(loot)} تومان ازت غارت کرد!\n"
                         f"❤️ -۱۵ سلامتی — قوی شو و انتقام بگیر! ⚔️")
        if loot >= 3000:
            channel_news(f"⚔️ جنگ بزرگ در شهر!\n\n{res}")
        log_action(uid, "war_win", f"vs {target_id} loot={loot}")
        return (f"🏆 برنده شدی!\n💰 غنیمت: +{fmt_money(loot)} تومان | 🏆 +۳ اعتبار | ⭐ +۲۵ XP"
                + ("\n" + "\n".join(lines) if lines else ""))
    # ❌ شکست حمله‌کننده
    cost = min(int(p["money"] * 0.05), 2000, p["money"])
    if cost > 0:
        change_money(uid, -cost, "war", f"جریمه شکست جنگ با {t['name']}")
    db.execute("UPDATE profiles SET health=MAX(0,health-12) WHERE user_id=?", (uid,))
    db.execute("UPDATE profiles SET reputation=MIN(100,reputation+2) WHERE user_id=?", (target_id,))
    gain_xp(target_id, 15)
    res = f"🛡 {t['name']} حمله‌ی {p['name']} را دفع کرد!"
    db.execute("INSERT INTO war_log(attacker,defender,result,loot,created_at) VALUES(?,?,?,?,?)",
               (uid, target_id, res, 0, now_iso()))
    api.send_message(target_id, f"🛡 قهرمان! حمله‌ی {p['name']} را دفع کردی! (+۲ اعتبار)")
    log_action(uid, "war_lose", f"vs {target_id}")
    return (f"❌ شکست خوردی! {t['name']} قوی‌تر بود.\n"
            f"💸 -{fmt_money(cost)} تومان | ❤️ -۱۲ سلامتی\n"
            "💪 مهارت و لولت را بالا ببر و برگرد!")


def boss_fight(chat_id, uid):
    p = profile(uid)
    if p.get("last_boss") == today():
        return "🐲 باس امروز شکار شده! فردا برگرد."
    if p["energy"] < 20:
        return "🔋 برای نبرد با باس ۲۰ انرژی لازم است."
    boss = pick([("🐲 اژدهای دزدان", 0.45), ("🦾 ماشین جنگی آهنی", 0.40),
                 ("👹 پادشاه سایه‌ها", 0.35), ("🦑 هیولای بندر", 0.50)])
    db.execute("UPDATE profiles SET energy=MAX(0,energy-20) WHERE user_id=?", (uid,))
    set_profile(uid, last_boss=today())
    chance = min(0.85, 0.35 + battle_power(uid) / 400)
    if random.random() < chance:
        money = 200 * p["level"] + random.randint(100, 400)
        change_money(uid, money, "boss", f"شکار {boss[0]}")
        add_gems(uid, BOSS_GEMS_REWARD)
        lines = gain_xp(uid, 60)
        db.execute("UPDATE profiles SET reputation=MIN(100,reputation+5) WHERE user_id=?", (uid,))
        channel_news(f"🐲 خبر داغ! {p['name']} باس «{boss[0]}» را شکست داد و {fmt_money(money)} تومان + 💎 {fn(BOSS_GEMS_REWARD)} سکه برداشت!")
        log_action(uid, "boss_win", boss[0])
        return (f"🎉 «{boss[0]}» نابود شد!\n💰 +{fmt_money(money)} تومان | 💎 +{fn(BOSS_GEMS_REWARD)} سکه طلا\n"
                f"🏆 +۵ اعتبار | ⭐ +۶۰ XP" + ("\n" + "\n".join(lines) if lines else ""))
    db.execute("UPDATE profiles SET health=MAX(0,health-20) WHERE user_id=?", (uid,))
    gain_xp(uid, 20)
    log_action(uid, "boss_lose", boss[0])
    return (f"💀 باس «{boss[0]}» غول‌پیکرتر از آن بود که فکرش را می‌کردی!\n"
            f"❤️ -۲۰ سلامتی | ⭐ +۲۰ XP (تجربه تلخ)\nفردا قوی‌تر برگرد! ⚔️")


# ───── 💎 فروشگاه VIP — سکه طلا (درآمد واقعی برای صاحب ربات) ─────

def panel_vip(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    p = profile(uid)
    card = get_setting("owner_card", OWNER_CARD_NUM)
    rows = [[(pack[1] + f" — {fmt_money(pack[3])} تومان", f"ord:new:{pack[0]}")] for pack in GEM_PACKS]
    rows.append([("🎁 خرج سکه‌ها (قدرت‌ها)", "vip:spend")])
    api.send_message(chat_id,
                     f"💎 فروشگاه VIP\n━━━━━━━━━━━\n"
                     f"💎 موجودی سکه: {fn(p.get('gems') or 0)}{' | 👑 شما VIP هستید' if p.get('vip') else ''}\n\n"
                     "با سکه طلا می‌تونی سپر جنگی، شارژ انرژی، تاج VIP و جایزه‌های ویژه بگیری!\n"
                     "👇 یک بسته انتخاب کن:", inline_keyboard(rows))


def panel_vip_spend(chat_id, uid):
    p = profile(uid)
    rows = [
        [("🛡 سپر ۲۴ ساعته (۳۰ 💎)", "gem:shield"), ("⚡ شارژ کامل انرژی (۲۰ 💎)", "gem:charge")],
        [("👑 لقب VIP همیشگی (۱۰۰ 💎)", "gem:vip"), ("🎰 چرخ شانس طلایی (۲۵ 💎)", "gem:spin")],
    ]
    api.send_message(chat_id,
                     f"🎁 خرج سکه‌ها — 💎 موجودی: {fn(p.get('gems') or 0)}\n\n"
                     "🛡 سپر: ۲۴ ساعت مصونیت از حمله\n⚡ شارژ: انرژی فول + ۳۰ سلامتی\n"
                     "👑 VIP: +۱۰ قدرت جنگ دائم + تاج کنار نامت\n🎰 چرخ شانس: سکه، پول، XP!",
                     inline_keyboard(rows))


def gem_buy_shield(chat_id, uid):
    p = profile(uid)
    if (p.get("gems") or 0) < 30:
        return "💎 ۳۰ سکه لازم است؛ از فروشگاه VIP بگیر."
    add_gems(uid, -30)
    from datetime import timedelta
    until = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")
    set_profile(uid, shield_until=until)
    log_action(uid, "gem_shield")
    return "🛡 سپر ۲۴ ساعته فعال شد! هیچ‌کس نمی‌تونه بهت حمله کنه."

def gem_charge(chat_id, uid):
    p = profile(uid)
    if (p.get("gems") or 0) < 20:
        return "💎 ۲۰ سکه لازم است."
    add_gems(uid, -20)
    db.execute("UPDATE profiles SET energy=100, health=MIN(100,health+30) WHERE user_id=?", (uid,))
    log_action(uid, "gem_charge")
    return "⚡ شارژ کامل! انرژی ۱۰۰ و سلامتی +۳۰. برو دنیا رو فتح کن! 🌍"

def gem_vip(chat_id, uid):
    p = profile(uid)
    if p.get("vip"):
        return "👑 تو همین‌الان هم VIP هستی!"
    if (p.get("gems") or 0) < 100:
        return "💎 ۱۰۰ سکه لازم است."
    add_gems(uid, -100)
    set_profile(uid, vip=1)
    channel_news(f"👑 {p['name']} به باشگاه VIP پیوست! تاج زد و قدرتش دوچندان حس می‌شود!")
    log_action(uid, "gem_vip")
    return "👑 تبریک، VIP شدی! +۱۰ قدرت جنگ دائم و تاج کنار اسم. افسانه‌ای!"

def gem_spin(chat_id, uid):
    p = profile(uid)
    if (p.get("gems") or 0) < 25:
        return "💎 ۲۵ سکه لازم است."
    add_gems(uid, -25)
    roll = random.random()
    if roll < 0.10:
        add_gems(uid, 50); res = "💰 جکپات! ۵۰ سکه طلا بردی! (+۲۵ نتیجه)"
    elif roll < 0.30:
        add_gems(uid, 35); res = "🎉 ۳۵ سکه بردی! (+۱۰ نتیجه)"
    elif roll < 0.55:
        change_money(uid, 1500, "spin", "چرخ شانس"); res = f"💵 {fmt_money(1500)} تومان نقد بردی!"
    elif roll < 0.80:
        lines = gain_xp(uid, 80)
        res = "⭐ +۸۰ XP بردی!" + (f"\n{lines[0]}" if lines else "")
    else:
        res = "🍀 این دور هیچی! (اما سرگرم کننده بود، نه؟ 😄)"
    log_action(uid, "gem_spin", res[:40])
    return "🎰 چرخ شانس چرخید...\n" + res


# ───── 💳 سیستم سفارش سکه (کارت‌به‌کارت + تایید ادمین) ─────

def order_new(chat_id, uid, pack_id):
    pack = next((p for p in GEM_PACKS if p[0] == pack_id), None)
    if not pack:
        return "❌ بسته پیدا نشد!"
    old = db.fetchone("SELECT id FROM orders WHERE user_id=? AND status='pending'", (uid,))
    if old:
        db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (old["id"],))
    cur = db.execute(
        "INSERT INTO orders(user_id,pack,gems,price_toman,status,created_at) VALUES(?,?,?,?,'pending',?)",
        (uid, pack[0], pack[2], pack[3], now_iso()))
    oid = cur.lastrowid
    card = get_setting("owner_card", OWNER_CARD_NUM)
    log_action(uid, "order_new", f"#{oid} {pack[0]}")
    api.send_message(chat_id,
                     f"🧾 فاکتور خرید #{fn(oid)}\n━━━━━━━━━━━\n"
                     f"📦 {pack[1]}\n💵 مبلغ: {fmt_money(pack[3])} تومان\n\n"
                     f"۱️⃣ مبلغ را به کارت زیر واریز کن:\n💳 {card}\n"
                     f"۲️⃣ بعد از واریز، «پرداخت کردم» را بزن تا فیشت بررسی و سکه‌ها شارژ شود.",
                     inline_keyboard([[("✅ پرداخت کردم", f"ord:paid:{oid}")],
                                      [("❌ انصراف", f"ord:cancel:{oid}")]]))
    return None

def order_paid(chat_id, uid, oid):
    o = db.fetchone("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, uid))
    if not o or o["status"] != "pending":
        return "⚠️ سفارش معتبر نیست."
    db.execute("UPDATE orders SET status='awaiting' WHERE id=?", (oid,))
    pack = next((p for p in GEM_PACKS if p[0] == o["pack"]), (None, o["pack"]))
    notify_admins(
        f"💰 سفارش سکه جدید!\n━━━━━━━━━━━\n🆔 فاکتور: #{oid}\n👤 خریدار: {profile(uid)['name']} ({uid})\n"
        f"📦 {pack[1]} | 💵 {fmt_money(o['price_toman'])} تومان\n"
        f"⚠️ لطفاً واریز را چک و تأیید/رد کن:",
        inline_keyboard([[("✅ تایید واریز", f"ord:ok:{oid}"), ("❌ رد سفارش", f"ord:no:{oid}")]]))
    log_action(uid, "order_paid", f"#{oid}")
    return "✅ ثبت شد! بعد از تأیید واریز توسط مدیریت، سکه‌ها به حسابت میاد. 💎"

def order_cancel(chat_id, uid, oid):
    o = db.fetchone("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, uid))
    if o and o["status"] == "pending":
        db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (oid,))
    return "❌ سفارش کنسل شد."

def admin_order_decide(chat_id, admin_id, oid, approve):
    o = db.fetchone("SELECT * FROM orders WHERE id=?", (oid,))
    if not o or o["status"] != "awaiting":
        return "⚠️ این سفارش قبلاً رسیدگی شده."
    if approve:
        db.execute("UPDATE orders SET status='ok', processed_by=?, processed_at=? WHERE id=?",
                   (admin_id, now_iso(), oid))
        add_gems(o["user_id"], o["gems"])
        p = profile(o["user_id"])
        api.send_message(o["user_id"],
                         f"🎉 واریزت تأیید شد! 💎 {fn(o['gems'])} سکه طلا به حسابت اضافه شد.\n"
                         f"💎 موجودی: {fn(p.get('gems') or 0)} سکه — از پنل «💎 VIP» خرجشان کن!")
        channel_news(f"💎 {p['name']} بسته‌ی {fn(o['gems'])} سکه طلا خرید! از حمایتت ممنونیم 🙏")
        log_action(admin_id, "order_approve", f"#{oid} user={o['user_id']} price={o['price_toman']}")
        return f"✅ سفارش #{oid} تأیید و {fn(o['gems'])} سکه شارژ شد."
    db.execute("UPDATE orders SET status='rejected', processed_by=?, processed_at=? WHERE id=?",
               (admin_id, now_iso(), oid))
    api.send_message(o["user_id"],
                     f"⚠️ متأسفانه واریز سفارش #{fn(oid)} تأیید نشد. اگر اشکالی رخ داده به مدیریت پیام بده.")
    log_action(admin_id, "order_reject", f"#{oid}")
    return f"❌ سفارش #{oid} رد شد."


# ───── پنل‌های ادمین جدید ─────

def panel_admin_revenue(chat_id):
    pending = db.fetchall("SELECT * FROM orders WHERE status='awaiting' ORDER BY id")
    ok_rows = db.fetchall("SELECT pack, COUNT(*) c, SUM(price_toman) t FROM orders WHERE status='ok' GROUP BY pack")
    total = db.fetchone("SELECT COALESCE(SUM(price_toman),0) t, COUNT(*) c FROM orders WHERE status='ok'")
    lines = [f"💎 سفارش‌ها و درآمد\n━━━━━━━━━━━\n"
             f"💰 درآمد کل: {fmt_money(total['t'])} تومان ({fn(total['c'])} فروش موفق)\n"]
    if ok_rows:
        lines.append("📦 به تفکیک بسته:")
        for r in ok_rows:
            lines.append(f"• {r['pack']}: {fn(r['c'])} فروش — {fmt_money(r['t'])} تومان")
    lines.append(f"\n⏳ سفارش‌های در انتظار تأیید: {fn(len(pending))}")
    lines.append(f"\n💳 کارت دریافت فعلی: {get_setting('owner_card', OWNER_CARD_NUM)}")
    rows = [[("💳 تغییر شماره کارت دریافت", "card:set")]]
    for o in pending[:8]:
        rows.append([(f"⏳ #{o['id']} — {fmt_money(o['price_toman'])} ({o['pack']})", f"ord:view:{o['id']}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def admin_order_view(chat_id, oid):
    o = db.fetchone("SELECT * FROM orders WHERE id=?", (oid,))
    if not o:
        api.send_message(chat_id, "❌ سفارش نیست."); return
    p = profile(o["user_id"])
    api.send_message(chat_id,
                     f"🧾 سفارش #{oid}\n👤 {p['name'] if p else o['user_id']} (ID: {o['user_id']})\n"
                     f"📦 {o['pack']} | 💎 {fn(o['gems'])} | 💵 {fmt_money(o['price_toman'])} تومان\n"
                     f"🗓 {o['created_at']} | وضعیت: {o['status']}",
                     inline_keyboard([[("✅ تایید واریز", f"ord:ok:{oid}"), ("❌ رد", f"ord:no:{oid}")]])
                     if o["status"] == "awaiting" else None)


def panel_admin_channel(chat_id):
    ch = get_setting("channel", CHANNEL_DEFAULT) or "— تنظیم نشده —"
    rows = [[("✏️ تنظیم/تغییر کانال", "chn:set"), ("🧪 تست ارسال", "chn:test")],
            [("🏆 ارسال جدول برترها", "chn:top"), ("🚨 فیک خبر بازار", "chn:mkt")]]
    api.send_message(chat_id,
                     f"🛰 تنظیمات کانال اخبار\n━━━━━━━━━━━\nکانال فعلی: {ch}\n\n"
                     "⚠️ ربات باید در کانال ادمین باشد.\n"
                     "اخبار جنگ‌های بزرگ، بازار و خریدهای VIP خودکار پست می‌شود.",
                     inline_keyboard(rows))


def panel_admin_marketctl(chat_id):
    rows = []
    lines = ["🎛 کنترل بازار (دست‌کاری قیمت‌ها!) 😈\n"]
    for r in db.fetchall("SELECT * FROM markets"):
        lines.append(f"{r['name']}: {fmt_money(r['price'])}")
        rows.append([(f"📈 پمپ +۱۵٪", f"mktctl:pump:{r['symbol']}"),
                     (f"📉 دامپ -۱۵٪", f"mktctl:dump:{r['symbol']}")])
    rows.append([("🔄 به‌روزرسانی دستی قیمت‌ها", "mktctl:tick")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def admin_market_move(symbol, direction):
    r = db.fetchone("SELECT * FROM markets WHERE symbol=?", (symbol,))
    if not r:
        return "❌"
    mult = 1.15 if direction == "pump" else 0.85
    new = int(r["price"] * mult)
    db.execute("UPDATE markets SET prev_price=?, price=?, trend=?, updated_at=? WHERE symbol=?",
               (r["price"], new, (r["trend"] or 0) + (0.1 if direction == "pump" else -0.1),
                now_iso(), symbol))
    emo = "🚀" if direction == "pump" else "🔻"
    channel_news(f"{emo} تحلیلگران می‌گویند {r['name']} {'جهش' if direction=='pump' else 'سقوط'} کرده!\n"
                 f"قیمت جدید: {fmt_money(new)} تومان")
    return f"{emo} {r['name']} → {fmt_money(new)}"


def post_leaderboard_channel():
    top = db.fetchall("SELECT name, money, level FROM profiles ORDER BY money DESC LIMIT 5")
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = ["🏆 جدول قدرت شهر!\n"]
    for i, r in enumerate(top):
        lines.append(f"{medals[i]} {r['name']} — {fmt_money(r['money'])} تومان (لول {fn(r['level'])})")
    lines.append("\n🎮 تو هم بیا توی Life Simulator AI و اسمتو بالا ببر!")
    return channel_news("\n".join(lines))


# ══════════════════════════════════════════════════════════════════
# [7.9] 🆕 v4: خانواده و ازدواج، اتحاد (گیلد)، پت، بانک، رویداد جهانی
# ══════════════════════════════════════════════════════════════════

# ───── 🌍 موتور رویداد جهانی ─────

def world_event():
    ev = jl(get_setting("world_event", ""), None)
    if ev and ev.get("until"):
        try:
            if datetime.fromisoformat(ev["until"]) > datetime.now():
                return ev
        except Exception:
            pass
    return None

def income_mult():
    ev = world_event()
    if ev and ev["key"] == "festival":
        return 2.0
    if ev and ev["key"] == "recession":
        return 0.7
    return 1.0

def world_engine():
    """هر ۴ ساعت یک‌بار: اگر رویدادی فعال نیست، ۲۰٪ شانس رویداد جدید"""
    last = get_setting("world_last_roll")
    if last and (datetime.now() - datetime.fromisoformat(last)).total_seconds() < 4 * 3600:
        return
    set_setting("world_last_roll", now_iso())
    if world_event():
        return
    if random.random() < 0.25:
        trigger_world_event(random.choice(list(WORLD_EVENTS.keys())), actor="سرور")

def trigger_world_event(key, actor="سرور"):
    from datetime import timedelta
    title, desc = WORLD_EVENTS[key]
    until = (datetime.now() + timedelta(hours=4)).isoformat(timespec="seconds")
    set_setting("world_event", jd({"key": key, "title": title, "until": until}))
    extra = ""
    if key == "quake":
        db.execute("UPDATE resources SET soldiers=MAX(0, soldiers - CAST(soldiers*0.05 AS INTEGER))")
        db.execute("UPDATE profiles SET health=MAX(0, health-5)")
        extra = "\n🏥 بیمارستان‌های شلوغ! منابعت را چک کن."
    elif key == "epidemic":
        db.execute("UPDATE profiles SET health=MAX(0, health-8)")
    elif key == "rally":
        db.execute("UPDATE markets SET prev_price=price, price=CAST(price*1.10 AS INTEGER), updated_at=?", (now_iso(),))
    elif key == "festival":
        db.execute("UPDATE profiles SET happiness=MIN(100, happiness+8)")
    msg = f"🌍 رویداد جهانی: {title}\n\n{desc}{extra}\n\n⏱ ۴ ساعت فعال است!"
    channel_news(msg)
    db.execute("INSERT INTO announcements(text,created_at) VALUES(?,?)", (f"{title}: {desc}", now_iso()))
    log_action(0, "world_event", f"{key} by {actor}")
    return msg

def panel_admin_world(chat_id):
    ev = world_event()
    cur = f"✅ فعال: {ev['title']} (تا {ev['until'][5:16]})" if ev else "❌ رویداد فعالی نیست (خودسرور هر ۴ ساعت ۲۵٪ شانس دارد)"
    rows = [[(v[0], f"wev:{k}")] for k, v in WORLD_EVENTS.items()]
    rows.append([("🛑 پایان رویداد", "wev:clear")])
    api.send_message(chat_id, f"🌍 کنترل رویداد جهانی\n━━━━━━━━━━━\n{cur}", inline_keyboard(rows))


# ───── 👨‍👩‍👧 خانواده و ازدواج ─────

def family_of(uid):
    r = db.fetchone("SELECT * FROM family WHERE user_id=?", (uid,))
    return dict(r) if r else None

def panel_family(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    fam = family_of(uid)
    rows = []
    if fam and fam["spouse_id"]:
        sp = profile(fam["spouse_id"]) or {}
        days = max(1, (datetime.now() - datetime.fromisoformat(fam["married_at"])).days) if fam["married_at"] else 1
        tier = ("💍 تازه‌عروس‌وداماد" if days < 3 else "💑 زن‌وشوهر" if days < 10 else "🏆 زوج افسانه‌ای")
        txt = (f"👨‍👩‍👧 خانواده‌ی تو\n━━━━━━━━━━━\n"
               f"💑 همسر: {sp.get('name','?')} — {tier} ({fn(days)} روز)\n"
               f"👶 فرزندان: {fn(fam['children'])} نفر\n\n"
               f"🎁 پاداش روزانه‌ی خانواده: +۱۵۰💰 و شادی (بچه‌ها شادی بیشتر و هزینه بیشتر می‌سازند!)")
        rows = [[("🎁 دریافت پاداش روزانه", "fam:bonus")],
                [(f"👶 بچه‌دار شدن ({fmt_money(CHILD_COST)}💰)", "fam:child")],
                [("💔 طلاق", "fam:divorce")]]
    else:
        txt = ("👨‍👩‍👧 خانواده\n━━━━━━━━━━━\nمجردی! 💃\n\n"
               f"💍 با خرید حلقه ({fmt_money(MARRIAGE_RING_COST)} تومان) به یک بازیکن پیشنهاد ازدواج بده!\n"
               "ازدواج: پاداش روزانه، بچه، شادی و اعتبار!")
        rows = [[("💍 خرید حلقه و انتخاب همسر", "fam:propose")]]
    api.send_message(chat_id, txt, inline_keyboard(rows))


def family_propose_list(chat_id, uid):
    p = profile(uid)
    if p["money"] < MARRIAGE_RING_COST:
        api.send_message(chat_id, f"💸 حلقه {fmt_money(MARRIAGE_RING_COST)} تومانه؛ پولت کم است.")
        return
    rows = []
    for t in db.fetchall("""SELECT p.user_id, p.name FROM profiles p
                            JOIN users u ON u.user_id=p.user_id
                            LEFT JOIN family f ON f.user_id=p.user_id
                            WHERE p.user_id!=? AND u.is_banned=0 AND f.spouse_id IS NULL
                            ORDER BY u.last_seen DESC LIMIT 8""", (uid,)):
        rows.append([(f"💍 پیشنهاد به {t['name']}", f"fam:prop:{t['user_id']}")])
    if not rows:
        api.send_message(chat_id, "🥲 فعلاً کسی برای ازدواج نیست!")
        return
    api.send_message(chat_id, "💍 حلقه خریدی می‌شود و پیشنهادت فرستاده می‌شود. با کی؟", inline_keyboard(rows))


def family_propose(chat_id, uid, target_id):
    if family_of(uid) and family_of(uid)["spouse_id"]:
        return "⚠️ تو که متأهلی!"
    p, t = profile(uid), profile(target_id)
    if not t or family_of(target_id) and family_of(target_id)["spouse_id"]:
        return "❌ هدف معتبر نیست."
    if p["money"] < MARRIAGE_RING_COST:
        return f"💸 حلقه {fmt_money(MARRIAGE_RING_COST)} تومانه!"
    change_money(uid, -MARRIAGE_RING_COST, "marriage", f"حلقه برای {t['name']}")
    api.send_message(target_id,
                     f"💍 پیشنهاد ازدواج!\n{p['name']} با یک حلقه‌ی زیبا به تو پیشنهاد ازدواج داده! 💐\nقبول می‌کنی؟",
                     inline_keyboard([[("💖 قبول می‌کنم", f"fam:acc:{uid}"), ("🙅 رد", f"fam:dec:{uid}")]]))
    log_action(uid, "marriage_propose", str(target_id))
    return f"💌 پیشنهادت به {t['name']} فرستاده شد! حلقه خریدی شد ({fmt_money(MARRIAGE_RING_COST)}💰). منتظر جواب باش..."


def family_accept(chat_id, uid, proposer_id):
    if family_of(uid) and family_of(uid)["spouse_id"]:
        return "⚠️ تو متأهلی!"
    if not profile(proposer_id) or (family_of(proposer_id) and family_of(proposer_id)["spouse_id"]):
        return "😅 دیگر دیر شده؛ طرف ازدواج کرده!"
    p, t = profile(uid), profile(proposer_id)
    for a, b in ((uid, proposer_id), (proposer_id, uid)):
        db.execute("INSERT INTO family(user_id,spouse_id,married_at,children,last_bonus) VALUES(?,?,?,0,NULL) "
                   "ON CONFLICT(user_id) DO UPDATE SET spouse_id=?, married_at=?, children=0",
                   (a, b, now_iso(), b, now_iso()))
    for u in (uid, proposer_id):
        db.execute("UPDATE profiles SET happiness=MIN(100,happiness+15), reputation=MIN(100,reputation+5) WHERE user_id=?", (u,))
        gain_xp(u, 50)
    channel_news(f"💒 خبر شیرین!\n{t['name']} و {p['name']} با هم ازدواج کردند! 🎉 بهشون تبریک بگید!")
    api.send_message(proposer_id, f"💖 تبریک! {p['name']} قبول کرد! 💒 شما ازدواج کردید! (+۱۵ شادی، +۵ اعتبار)")
    log_action(uid, "married", str(proposer_id))
    return f"💒 مبارکتون باشه! تو و {t['name']} حالا زن‌وشوهر یکدیگرید! 🎊"


def family_decline(chat_id, uid, proposer_id):
    api.send_message(proposer_id, f"💔 {(profile(uid) or {})['name']} پیشنهادت را رد کرد... حلقه را بفروش و سر راهت برو 😅")
    return "پیشنهاد رد شد."


def family_child(chat_id, uid):
    fam = family_of(uid)
    if not fam or not fam["spouse_id"]:
        return "⚠️ اول ازدواج کن!"
    if fam["children"] >= MAX_CHILDREN:
        return f"👶 سقف {fn(MAX_CHILDREN)} فرزند است!"
    p = profile(uid)
    if p["money"] < CHILD_COST:
        return f"💸 خرج بچه {fmt_money(CHILD_COST)} تومانه!"
    change_money(uid, -CHILD_COST, "family", "فرزند جدید")
    db.execute("UPDATE family SET children=children+1 WHERE user_id=?", (uid,))
    db.execute("UPDATE family SET children=children+1 WHERE user_id=?", (fam["spouse_id"],))
    db.execute("UPDATE profiles SET happiness=MIN(100,happiness+10) WHERE user_id=?", (uid,))
    kid_names = ["نیلو", "آرتین", "ترانه", "پارسا", "درسا", "کیانوش", "باران"]
    log_action(uid, "child", str(fam['children']+1))
    return (f"👶 مبارک! فرزندت به دنیا آمد و اسمش را «{pick(kid_names)}» گذاشتید! 👨‍👩‍👧\n"
            f"😊 +۱۰ شادی | تعداد فرزندان: {fn(fam['children']+1)}")


def family_bonus(chat_id, uid):
    fam = family_of(uid)
    if not fam or not fam["spouse_id"]:
        return "⚠️ متأهل نیستی!"
    if fam["last_bonus"] == today():
        return "⏳ پاداش امروز را گرفتی؛ فردا برگرد!"
    sp_active = profile(fam["spouse_id"])
    bonus = 150
    lines = gain_xp(uid, 15)
    change_money(uid, bonus, "family_daily", "پاداش خانواده")
    db.execute("UPDATE profiles SET happiness=MIN(100,happiness+5) WHERE user_id=?", (uid,))
    if fam["children"]:
        cost = fam["children"] * 40
        change_money(uid, -min(cost, profile(uid)["money"]), "family_daily", "خرج بچه‌ها 🍼")
        db.execute("UPDATE profiles SET happiness=MIN(100,happiness+?) WHERE user_id=?", (fam["children"] * 4, uid))
    db.execute("UPDATE family SET last_bonus=? WHERE user_id=?", (today(), uid))
    kid_txt = f"\n👶 بچه‌ها: -{fmt_money(fam['children']*40)}💰 هزینه ولی +{fn(fam['children']*4)} شادی!" if fam["children"] else ""
    return (f"🎁 پاداش روزانه خانواده: +{fmt_money(bonus)}💰 | 😊 +۵ شادی | ⭐ +۱۵ XP{kid_txt}"
            + ("\n" + "\n".join(lines) if lines else ""))


def family_divorce(chat_id, uid):
    fam = family_of(uid)
    if not fam or not fam["spouse_id"]:
        return "⚠️ متأهل نیستی!"
    api.send_message(chat_id, "💔 مطمئنی می‌خواهی طلاق بگیری؟ (شادی دو طرف کم می‌شود)",
                     inline_keyboard([[("💔 بله", "fam:divok"), ("❌ نه", "fam:no")]]))
    return None


def family_divorce_ok(chat_id, uid):
    fam = family_of(uid)
    if not fam or not fam["spouse_id"]:
        return "⚠️"
    sid = fam["spouse_id"]
    db.execute("DELETE FROM family WHERE user_id IN (?,?)", (uid, sid))
    for u in (uid, sid):
        db.execute("UPDATE profiles SET happiness=MAX(0,happiness-15) WHERE user_id=?", (u,))
    api.send_message(sid, f"💔 {(profile(uid) or {})['name']} از تو طلاق گرفت... (-۱۵ شادی)")
    log_action(uid, "divorced", str(sid))
    return "💔 طلاق انجام شد... (-۱۵ شادی) زندگی ادامه دارد!"


# ───── 🤝 اتحاد (گیلد) ─────

def guild_of(uid):
    g = db.fetchone("""SELECT g.*, m.role FROM guilds g JOIN guild_members m ON m.guild_id=g.id
                       WHERE m.user_id=?""", (uid,))
    return dict(g) if g else None

def guild_level(g):
    return 1 + (g["donations"] or 0) // 5000

def guild_member_count(gid):
    return db.fetchone("SELECT COUNT(*) c FROM guild_members WHERE guild_id=?", (gid,))["c"]

def salary_mult(uid):
    """نرخ درآمد سرور × رویداد جهانی × پاداش اتحاد"""
    mult = float(get_setting("income_rate", "1")) * income_mult()
    g = guild_of(uid)
    if g:
        mult *= 1 + min(guild_level(g), 10) * 0.01
    return mult


def panel_guild(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    g = guild_of(uid)
    if not g:
        rows = [[("➕ ساخت اتحاد (۵٬۰۰۰💰)", "gld:create")], [("📜 لیست اتحادها", "gld:list")]]
        api.send_message(chat_id,
                         "🤝 اتحادها\n━━━━━━━━━━━\nدر اتحادی نیستی!\n\n"
                         "پاداش اتحاد: هر سطح، +۱٪ حقوق همه اعضا (تا ۱۰٪)!\n"
                         "⚔️ جنگ اتحاد: غارت خزانه اتحاد دشمن توسط لیدر!",
                         inline_keyboard(rows))
        return
    lvl = guild_level(g)
    members = db.fetchall("""SELECT m.user_id, m.role, p.name FROM guild_members m
                             LEFT JOIN profiles p ON p.user_id=m.user_id WHERE m.guild_id=?""", (g["id"],))
    cap = 10 + lvl * 2
    lines = [f"🤝 اتحاد «{g['name']}» — سطح {fn(lvl)}\n━━━━━━━━━━━\n"
             f"💰 خزانه: {fmt_money(g['bank'])} | 🎁 مجموع کمک‌ها: {fmt_money(g['donations'])}\n"
             f"👥 اعضا: {fn(len(members))}/{fn(cap)} | پاداش حقوق: +{fn(min(lvl,10))}٪\n"]
    for mem in members:
        role = "👑" if mem["role"] == "leader" else "•"
        lines.append(f"{role} {mem['name'] or mem['user_id']}")
    rows = [[("💰 کمک ۵۰۰", "gld:donate:500"), ("💰 کمک ۲٬۰۰۰", "gld:donate:2000"),
             ("💰 کمک ۵٬۰۰۰", "gld:donate:5000")],
            [("🚪 ترک اتحاد", "gld:leave")]]
    if g["role"] == "leader":
        rows.insert(0, [("⚔️ جنگ اتحاد (غارت خزانه دشمن)", "gld:war"),
                        ("🗑 انحلال", "gld:disband")])
        rows.append([(f"👢 بیرون کردن عضو", "gld:kicklist")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def guild_create_done(chat_id, uid, name):
    if guild_of(uid):
        set_state(uid); return
    p = profile(uid)
    if p["money"] < GUILD_CREATE_COST:
        api.send_message(chat_id, f"💸 ساخت اتحاد {fmt_money(GUILD_CREATE_COST)} تومانه!"); return
    change_money(uid, -GUILD_CREATE_COST, "guild", f"ساخت اتحاد {name}")
    cur = db.execute("INSERT INTO guilds(name,leader_id,bank,donations,created_at) VALUES(?,?,0,0,?)",
                     (name, uid, now_iso()))
    db.execute("INSERT INTO guild_members(user_id,guild_id,role,joined_at) VALUES(?,?,'leader',?)",
               (uid, cur.lastrowid, now_iso()))
    set_state(uid)
    channel_news(f"🤝 اتحاد «{name}» تأسیس شد! لیدر: {p['name']}")
    log_action(uid, "guild_create", name)
    api.send_message(chat_id,
                     f"🎉 اتحاد «{name}» ساخته شد! تو لیدری 👑\n"
                     f"اعضا جمع کن، به خزانه کمک کن و سطح ببر بالا!", MAIN_KB)


def guild_list(chat_id, uid, for_war=False):
    rows = []
    my = guild_of(uid)
    for g in db.fetchall("SELECT * FROM guilds ORDER BY donations DESC LIMIT 10"):
        if for_war and my and g["id"] == my["id"]:
            continue
        cnt = guild_member_count(g["id"])
        if for_war:
            rows.append([(f"⚔️ جنگ با «{g['name']}» (خزانه {fmt_money(g['bank'])})", f"gld:dowar:{g['id']}")])
        else:
            lvl = guild_level(dict(g))
            rows.append([(f"➕ عضویت «{g['name']}» — سطح {fn(lvl)} (👥 {fn(cnt)})", f"gld:join:{g['id']}")])
    if not rows:
        api.send_message(chat_id, "🏜 هنوز اتحادی ساخته نشده!" if not for_war else "🏜 دشمنی نیست!")
        return
    api.send_message(chat_id, "📜 اتحادها:" if not for_war else "⚔️ با کدام اتحاد می‌جنگی؟",
                     inline_keyboard(rows))


def guild_join(chat_id, uid, gid):
    if guild_of(uid):
        return "⚠️ همین حالا هم عضو یک اتحادی!"
    g = db.fetchone("SELECT * FROM guilds WHERE id=?", (gid,))
    if not g:
        return "❌ اتحاد نیست."
    if guild_member_count(gid) >= 10 + guild_level(dict(g)) * 2:
        return "🚪 ظرفیت اتحاد پر است!"
    db.execute("INSERT INTO guild_members(user_id,guild_id,role,joined_at) VALUES(?,?,'member',?)",
               (uid, gid, now_iso()))
    leader = profile(g["leader_id"])
    if leader:
        api.send_message(g["leader_id"], f"🤝 {(profile(uid) or {})['name']} به اتحاد «{g['name']}» پیوست!")
    log_action(uid, "guild_join", g["name"])
    return f"🎉 به اتحاد «{g['name']}» پیوستی! پاداش حقوقت فعال شد."


def guild_donate(chat_id, uid, amount):
    g = guild_of(uid)
    if not g:
        return "⚠️ اتحادی نداری!"
    p = profile(uid)
    if p["money"] < amount:
        return "💸 پولت کم است."
    old_lvl = guild_level(g)
    change_money(uid, -amount, "guild", f"کمک به {g['name']}")
    db.execute("UPDATE guilds SET bank=bank+?, donations=donations+? WHERE id=?", (amount, amount, g["id"]))
    new = dict(db.fetchone("""SELECT g.*, m.role FROM guilds g JOIN guild_members m ON m.guild_id=g.id
                              WHERE m.user_id=?""", (uid,)))
    new_lvl = guild_level(new)
    extra = f"\n🆙 اتحاد به سطح {fn(new_lvl)} رسید! پاداش حقوق بیشتر شد! 🎉" if new_lvl > old_lvl else ""
    log_action(uid, "guild_donate", f"{g['name']} {amount}")
    return f"💰 {fmt_money(amount)} تومان به خزانه «{g['name']}» رفت!{extra}"


def guild_leave(chat_id, uid):
    g = guild_of(uid)
    if not g:
        return "⚠️"
    db.execute("DELETE FROM guild_members WHERE user_id=?", (uid,))
    if g["role"] == "leader":
        other = db.fetchone("SELECT user_id FROM guild_members WHERE guild_id=? LIMIT 1", (g["id"],))
        if other:
            db.execute("UPDATE guild_members SET role='leader' WHERE user_id=?", (other["user_id"],))
            db.execute("UPDATE guilds SET leader_id=? WHERE id=?", (other["user_id"], g["id"]))
            api.send_message(other["user_id"], f"👑 تو لیدر جدید اتحاد «{g['name']}» شدی!")
        else:
            db.execute("DELETE FROM guilds WHERE id=?", (g["id"],))
    log_action(uid, "guild_leave", g["name"])
    return f"🚪 از اتحاد «{g['name']}» خارج شدی."


def guild_kick_list(chat_id, uid):
    g = guild_of(uid)
    if not g or g["role"] != "leader":
        return "⚠️ فقط لیدر!"
    rows = []
    for mem in db.fetchall("""SELECT m.user_id, p.name FROM guild_members m
                              LEFT JOIN profiles p ON p.user_id=m.user_id
                              WHERE m.guild_id=? AND m.user_id!=?""", (g["id"], uid)):
        rows.append([(f"👢 اخراج {mem['name'] or mem['user_id']}", f"gld:kick:{mem['user_id']}")])
    if not rows:
        return "👥 عضوی برای اخراج نیست."
    api.send_message(chat_id, "👢 کدام عضو اخراج شود؟", inline_keyboard(rows))
    return None


def guild_kick(chat_id, uid, target_id):
    g = guild_of(uid)
    if not g or g["role"] != "leader":
        return "⚠️ فقط لیدر!"
    db.execute("DELETE FROM guild_members WHERE user_id=? AND guild_id=?", (target_id, g["id"]))
    api.send_message(target_id, f"👢 از اتحاد «{g['name']}» اخراج شدی!")
    log_action(uid, "guild_kick", str(target_id))
    return "👢 اخراج شد."


def guild_disband(chat_id, uid):
    g = guild_of(uid)
    if not g or g["role"] != "leader":
        return "⚠️ فقط لیدر!"
    db.execute("DELETE FROM guild_members WHERE guild_id=?", (g["id"],))
    db.execute("DELETE FROM guilds WHERE id=?", (g["id"],))
    log_action(uid, "guild_disband", g["name"])
    return f"🗑 اتحاد «{g['name']}» منحل شد."


def guild_war(chat_id, uid, enemy_gid):
    g = guild_of(uid)
    if not g or g["role"] != "leader":
        return "⚠️ فقط لیدر می‌تواند اعلام جنگ کند!"
    e = db.fetchone("SELECT * FROM guilds WHERE id=?", (enemy_gid,))
    if not e or e["id"] == g["id"]:
        return "❌ دشمن معتبر نیست."
    last = g["last_war"]
    if last and (datetime.now() - datetime.fromisoformat(last)).total_seconds() < 3600:
        return "⏳ اتحادت خسته است؛ ساعتی دیگر جنگ کن!"
    mem_a = [r["user_id"] for r in db.fetchall("SELECT user_id FROM guild_members WHERE guild_id=?", (g["id"],))]
    mem_b = [r["user_id"] for r in db.fetchall("SELECT user_id FROM guild_members WHERE guild_id=?", (enemy_gid,))]
    if not mem_b:
        return "❌ آن اتحاد عضوی ندارد!"
    pa = sum(battle_power(m) for m in mem_a) * random.uniform(0.9, 1.1) + (g["bank"] or 0) / 500
    pb = sum(battle_power(m) for m in mem_b) * random.uniform(0.9, 1.1) + (e["bank"] or 0) / 500
    db.execute("UPDATE guilds SET last_war=? WHERE id=?", (now_iso(), g["id"]))
    if pa >= pb:
        loot = int((e["bank"] or 0) * 0.25)
        db.execute("UPDATE guilds SET bank=bank-? WHERE id=?", (loot, enemy_gid))
        db.execute("UPDATE guilds SET bank=bank+? WHERE id=?", (loot, g["id"]))
        res = f"🏆 اتحاد «{g['name']}» خزانه «{e['name']}» را غارت کرد! ({fmt_money(loot)}💰)"
        won, lost_team = g, e
    else:
        loot = int((g["bank"] or 0) * 0.25)
        db.execute("UPDATE guilds SET bank=bank-? WHERE id=?", (loot, g["id"]))
        db.execute("UPDATE guilds SET bank=bank+? WHERE id=?", (loot, enemy_gid))
        res = f"🛡 اتحاد «{e['name']}» حمله «{g['name']}» را دفع و {fmt_money(loot)}💰 غارت کرد!"
        won, lost_team = e, g
    channel_news(f"⚔️⚔️ جنگ اتحادها!\n\n{res}")
    for m_ in mem_a + mem_b:
        api.send_message(m_, f"📢 نتیجه جنگ اتحاد:\n{res}")
    log_action(uid, "guild_war", res)
    return res


# ───── 🐾 پت (حیوان خانگی) ─────

def pet_of(uid):
    r = db.fetchone("SELECT * FROM pets WHERE user_id=?", (uid,))
    return dict(r) if r else None

def pet_tick(uid):
    """گرسنگی با زمان می‌گذرد؛ اگر خیلی گرسنه شود، پت فرار می‌کند!"""
    pet = pet_of(uid)
    if not pet or not pet["last_tick"]:
        return pet
    hours = (datetime.now() - datetime.fromisoformat(pet["last_tick"])).total_seconds() / 3600
    if hours < 1:
        return pet
    hunger = min(100, pet["hunger"] + int(hours * 5))
    happy = pet["happy"] - (int(hours * 3) if hunger > 70 else 0)
    if hunger >= 100:
        db.execute("DELETE FROM pets WHERE user_id=?", (uid,))
        api.send_message(uid, f"😢 پتت «{pet['name']}» از گرسنگی فرار کرد! دفعه بعد بهش غذا برسان...")
        return None
    db.execute("UPDATE pets SET hunger=?, happy=MAX(0,?), last_tick=? WHERE user_id=?",
               (hunger, happy, now_iso(), uid))
    return pet


def panel_pet(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    pet = pet_tick(uid)
    if not pet:
        rows = [[(f"{pt[1]} — {'💎 '+fn(pt[3]) if pt[3] else fmt_money(pt[2])+'💰'}", f"pet:buy:{pt[0]}")] for pt in PETS]
        api.send_message(chat_id,
                         "🐾 فروشگاه پت\n━━━━━━━━━━━\nهنوز پتی نداری!\n"
                         "پت به قدرت جنگت اضافه می‌کند — اما باید بهش غذا (🌾 امپراتوری) برسانی وگرنه فرار می‌کند!",
                         inline_keyboard(rows))
        return
    sp = next((p for p in PETS if p[0] == pet["species"]), PETS[0])
    power = sp[4] + pet["level"]
    rows = [[("🍖 غذا (۳ 🌾)", "pet:feed"), ("🎾 بازی (-۳⚡)", "pet:play")],
            [("🕊 آزاد کردن", "pet:free")]]
    api.send_message(chat_id,
                     f"🐾 «{pet['name']}» ({sp[1]}) — لول {fn(pet['level'])}\n━━━━━━━━━━━\n"
                     f"🍖 گرسنگی: {bar(pet['hunger'])} {fn(pet['hunger'])}\n"
                     f"😊 شادی: {bar(pet['happy'])} {fn(pet['happy'])}\n"
                     f"⚔️ بونس جنگ: +{fn(power)}{' (فعال ✅)' if pet['hunger'] < 80 else ' (گرسنه‌است، نصف ⚠️)'}",
                     inline_keyboard(rows))


def pet_buy(chat_id, uid, species):
    pt = next((p for p in PETS if p[0] == species), None)
    if not pt:
        return "❌"
    if pet_of(uid):
        return "⚠️ یک پت داری!"
    p = profile(uid)
    if pt[3]:  # خرید با سکه
        if (p.get("gems") or 0) < pt[3]:
            return f"💎 {fn(pt[3])} سکه لازم است."
        add_gems(uid, -pt[3])
    else:
        if p["money"] < pt[2]:
            return f"💸 {fmt_money(pt[2])} تومان لازم است."
        change_money(uid, -pt[2], "pet", f"خرید {pt[1]}")
    db.execute("""INSERT INTO pets(user_id,species,name,hunger,happy,level,adopted_at,last_tick)
                  VALUES(?,?,?,30,70,1,?,?)""",
               (uid, species, pt[1].split(" ")[1] if " " in pt[1] else pt[1], now_iso(), now_iso()))
    set_state(uid, "pet_name", {"species": species})
    log_action(uid, "pet_buy", species)
    return None


def pet_feed(chat_id, uid):
    pet = pet_tick(uid)
    if not pet:
        return "🐾 پتی نداری!"
    r = ensure_resources(uid)
    if r["food"] < 3:
        return "🌾 غذای امپراتوری کمه! از بخش امپراتوری بخر (۳ 🌾 لازم است)."
    db.execute("UPDATE resources SET food=food-3 WHERE user_id=?", (uid,))
    happy = min(100, pet["happy"] + 10)
    lvl_msg = ""
    if random.random() < 0.35 and pet["level"] < 10:
        db.execute("UPDATE pets SET level=level+1 WHERE user_id=?", (uid,))
        lvl_msg = "\n🆙 پتت یک لول رشد کرد!"
    db.execute("UPDATE pets SET hunger=MAX(0,hunger-45), happy=?, last_tick=? WHERE user_id=?",
               (happy, now_iso(), uid))
    return f"🍖 «{pet['name']}» را خوبی غذا دادی! (-۳ 🌾 | 😊 +۱۰){lvl_msg}"


def pet_play(chat_id, uid):
    pet = pet_tick(uid)
    if not pet:
        return "🐾 پتی نداری!"
    p = profile(uid)
    if p["energy"] < 3:
        return "🔋 انرژی نداری."
    db.execute("UPDATE profiles SET energy=MAX(0,energy-3), happiness=MIN(100,happiness+4) WHERE user_id=?", (uid,))
    db.execute("UPDATE pets SET happy=MIN(100,happy+15), last_tick=? WHERE user_id=?", (now_iso(), uid))
    return f"🎾 با «{pet['name']}» بازی کردی! پت خوشحال شد و تو هم حال کردی 😊"


def pet_free(chat_id, uid):
    pet = pet_of(uid)
    if not pet:
        return "🐾 پتی نداری!"
    db.execute("DELETE FROM pets WHERE user_id=?", (uid,))
    return f"🕊 «{pet['name']}» را آزاد کردی... روزهای خوبش در طبیعت! 🌿"


# ───── 🏦 بانک و وام ─────

def bank_interest(uid):
    """تیک بانکی روزانه: سود ۱٪ سپرده + جریمه دیرکرد وام (روزی ۲٪ بعد از سررسید)"""
    p = profile(uid)
    if p.get("bank_last_int") == today():
        return
    if (p.get("bank_balance") or 0) > 0:
        interest = int(p["bank_balance"] * 0.01)
        db.execute("UPDATE profiles SET bank_balance=bank_balance+? WHERE user_id=?", (interest, uid))
        if interest > 0:
            db.execute("INSERT INTO transactions(user_id,amount,type,description,created_at) VALUES(?,?,?,?,?)",
                       (uid, interest, "bank", "سود سپرده", now_iso()))
    if (p.get("loan_debt") or 0) > 0 and p.get("loan_due"):
        try:
            days_late = (datetime.now() - datetime.fromisoformat(p["loan_due"])).days
            if days_late > 0:
                penalty = int(p["loan_debt"] * 0.02 * days_late)
                db.execute("UPDATE profiles SET loan_debt=loan_debt+? WHERE user_id=?", (penalty, uid))
        except Exception:
            pass
    db.execute("UPDATE profiles SET bank_last_int=? WHERE user_id=?", (today(), uid))


def panel_bank(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    bank_interest(uid)
    p = profile(uid)
    max_loan = 5000 + p["level"] * 2000
    debt = p.get("loan_debt") or 0
    due_txt = ""
    if debt > 0 and p.get("loan_due"):
        due_dt = datetime.fromisoformat(p["loan_due"])
        days_left = (due_dt - datetime.now()).days
        due_txt = f"⏰ سررسید: {p['loan_due'][:10]} ({fn(max(0,days_left))} روز مونده)" if days_left >= 0 else "🚨 سررسید گذشته! روزی ۲٪ جریمه اضافه می‌شود!"
    rows = [
        [("➕ سپرده ۵٬۰۰۰", "bnk:dep:5000"), ("➕ سپرده ۲۰٬۰۰۰", "bnk:dep:20000")],
        [("➕ سپرده کل موجودی", "bnk:dep:all"), ("➖ برداشت کل سپرده", "bnk:wd:all")],
    ]
    if debt > 0:
        rows.append([(f"💳 بازپرداخت وام ({fmt_money(debt)}💰)", "bnk:repay")])
    else:
        rows.append([(f"🏧 وام {fmt_money(min(5000, max_loan))}", "bnk:loan:5000"),
                     (f"🏧 وام {fmt_money(min(20000, max_loan))}" if max_loan >= 20000 else "🏧 وام بیشتر (لولت کم است)", "bnk:loan:20000")])
    api.send_message(chat_id,
                     f"🏦 بانک شهر\n━━━━━━━━━━━\n"
                     f"💰 موجودی نقد: {fmt_money(p['money'])}\n"
                     f"🏦 سپرده: {fmt_money(p.get('bank_balance') or 0)} (سود روزانه ۱٪)\n"
                     f"💳 بدهی وام: {fmt_money(debt)}\n"
                     f"🏧 سقف وام تو: {fmt_money(max_loan)} (لول × ۲٬۰۰۰ + ۵٬۰۰۰)\n"
                     f"{due_txt}", inline_keyboard(rows))


def bank_deposit(chat_id, uid, mode):
    p = profile(uid)
    amount = p["money"] if mode == "all" else int(mode)
    if amount < 100:
        return "💸 حداقل ۱۰۰ تومان."
    if amount > p["money"]:
        return f"💸 فقط {fmt_money(p['money'])} داری!"
    change_money(uid, -amount, "bank", "سپرده‌گذاری")
    db.execute("UPDATE profiles SET bank_balance=bank_balance+? WHERE user_id=?", (amount, uid))
    log_action(uid, "bank_deposit", str(amount))
    return f"🏦 {fmt_money(amount)} تومان به سپرده رفت! فردا سود ۱٪ می‌گیری 📈"


def bank_withdraw(chat_id, uid):
    p = profile(uid)
    bal = p.get("bank_balance") or 0
    if bal <= 0:
        return "🏦 سپرده‌ای نداری!"
    db.execute("UPDATE profiles SET bank_balance=0 WHERE user_id=?", (uid,))
    change_money(uid, bal, "bank", "برداشت سپرده")
    return f"💵 {fmt_money(bal)} تومان از بانک برداشتی."


def bank_loan(chat_id, uid, amount):
    p = profile(uid)
    max_loan = 5000 + p["level"] * 2000
    amount = min(int(amount), max_loan)
    if (p.get("loan_debt") or 0) > 0:
        return "⚠️ تا وام فعلی را ندهی، وام جدید نمی‌گیری!"
    if amount < 500:
        return "❌ سقف وامت کم است؛ لولت را بالا ببر!"
    debt = int(amount * LOAN_INTEREST)
    from datetime import timedelta
    due = (datetime.now() + timedelta(days=LOAN_DAYS)).isoformat(timespec="seconds")
    change_money(uid, amount, "bank", f"دریافت وام {amount}")
    db.execute("UPDATE profiles SET loan_debt=?, loan_due=? WHERE user_id=?", (debt, due, uid))
    log_action(uid, "bank_loan", f"{amount} debt={debt}")
    return (f"🏧 وام {fmt_money(amount)} تومان گرفتی!\n"
            f"💳 بدهی با سود: {fmt_money(debt)}\n"
            f"⏰ سررسید: {fn(LOAN_DAYS)} روز دیگر — دیرکرد = روزی ۲٪ جریمه!")


def bank_repay(chat_id, uid):
    p = profile(uid)
    debt = p.get("loan_debt") or 0
    if debt <= 0:
        return "✅ بدهی نداری!"
    if p["money"] < debt:
        return f"💸 برای تسویه {fmt_money(debt)} تومان لازم است (داری {fmt_money(p['money'])})."
    change_money(uid, -debt, "bank", "تسویه وام")
    db.execute("UPDATE profiles SET loan_debt=0, loan_due=NULL, reputation=MIN(100,reputation+2) WHERE user_id=?", (uid,))
    log_action(uid, "bank_repay", str(debt))
    return f"✅ وامت کامل تسویه شد! اعتبار بانکی‌ات قوی شد (+۲ اعتبار) 🏦"


# ══════════════════════════════════════════════════════════════════
# [8] پنل ادمین
# ══════════════════════════════════════════════════════════════════

def cmd_admin(chat_id, uid):
    if not is_admin(uid):
        log_action(uid, "admin_denied")
        api.send_message(chat_id, "⛔ دسترسی نداری.")
        return
    api.send_message(chat_id, "🔐 پنل مدیریت Life Simulator AI\nیک بخش را انتخاب کن:", ADMIN_KB)


def admin_router(chat_id, uid, text):
    if not is_admin(uid):
        return False
    if text == "🚪 خروج از پنل ادمین":
        api.send_message(chat_id, "👋 از پنل خارج شدی.", MAIN_KB)
        return True
    if text == "👥 مدیریت کاربران":
        panel_admin_users(chat_id)
        return True
    if text == "📊 آمار ربات":
        panel_admin_stats(chat_id)
        return True
    if text == "🏪 مدیریت اقتصاد":
        panel_admin_economy(chat_id)
        return True
    if text == "🎲 مدیریت رویدادها":
        panel_admin_events(chat_id)
        return True
    if text == "💎 سفارش‌ها و درآمد":
        panel_admin_revenue(chat_id)
        return True
    if text == "🎛 کنترل بازار":
        panel_admin_marketctl(chat_id)
        return True
    if text == "🛰 تنظیمات کانال":
        panel_admin_channel(chat_id)
        return True
    if text == "🌍 رویداد جهانی":
        panel_admin_world(chat_id)
        return True
    if text == "📢 پیام همگانی":
        set_state(uid, "adm_broadcast")
        api.send_message(chat_id, "📢 متن پیام همگانی را بنویس (لغو: /cancel):", reply_keyboard([["لغو ❌"]]))
        return True
    if text == "📨 پیام به کاربر":
        set_state(uid, "adm_dm_id")
        api.send_message(chat_id, "📨 آیدی عددی کاربر را بفرست:", reply_keyboard([["لغو ❌"]]))
        return True
    if text == "📣 اطلاعیه همگانی":
        set_state(uid, "adm_announce")
        api.send_message(chat_id, "📣 متن اطلاعیه را بنویس:", reply_keyboard([["لغو ❌"]]))
        return True
    return False


# ── مدیریت کاربران ──

def panel_admin_users(chat_id, page=0):
    total = db.fetchone("SELECT COUNT(*) c FROM users")["c"]
    rows = db.fetchall("""SELECT u.user_id,u.is_banned,p.name,p.money,p.level FROM users u
                          LEFT JOIN profiles p ON p.user_id=u.user_id
                          ORDER BY u.last_seen DESC LIMIT 10 OFFSET ?""", (page*10,))
    lines = [f"👥 مدیریت کاربران — کل: {fn(total)} (صفحه {fn(page+1)})\n"]
    btns = []
    for r in rows:
        name = r["name"] or "بدون کاراکتر"
        ban = "🚫" if r["is_banned"] else ""
        lines.append(f"{ban} {name} | ID: {r['user_id']} | 💰 {fmt_money(r['money'] or 0)}")
        btns.append([(f"🔎 {name} ({r['user_id']})", f"adm:user:{r['user_id']}")])
    nav = []
    if page > 0:
        nav.append(("⬅️ قبلی", f"adm:upage:{page-1}"))
    if total > (page+1)*10:
        nav.append(("➡️ بعدی", f"adm:upage:{page+1}"))
    if nav:
        btns.append(nav)
    btns.append([("🔍 جستجوی کاربر", "adm:usearch")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(btns))


def admin_user_card(chat_id, target_id):
    u = db.fetchone("SELECT * FROM users WHERE user_id=?", (target_id,))
    if not u:
        api.send_message(chat_id, "❌ کاربر پیدا نشد!")
        return
    p = profile(target_id)
    status = "🚫 مسدود" if u["is_banned"] else "✅ فعال"
    info = f"👤 کارت کاربر\n──────────\n🆔 {target_id}\n@{u['username'] or '-'}\nوضعیت: {status}\n"
    if p:
        info += (f"نام: {p['name']} | شهر: {p['city']}\n💰 {fmt_money(p['money'])} | ⭐ لول {fn(p['level'])}"
                 f"\n⚡ {fn(p['energy'])} ❤️ {fn(p['health'])} 😊 {fn(p['happiness'])}\n"
                 f"🗓 عضویت: {u['created_at'][:10]}")
    else:
        info += "⚠️ کاراکتری ندارد."
    rows = [
        [("💰 تغییر پول", f"adm:money:{target_id}"), ("⭐ تغییر لول", f"adm:lvl:{target_id}")],
        [("🔁 بن/آنبن", f"adm:ban:{target_id}"), ("🗑 حذف کاربر", f"adm:del:{target_id}")],
    ]
    api.send_message(chat_id, info, inline_keyboard(rows))


def admin_toggle_ban(chat_id, actor, target_id):
    u = db.fetchone("SELECT * FROM users WHERE user_id=?", (target_id,))
    if not u:
        return
    new = 0 if u["is_banned"] else 1
    db.execute("UPDATE users SET is_banned=? WHERE user_id=?", (new, target_id))
    log_action(actor, "ban" if new else "unban", str(target_id))
    admin_user_card(chat_id, target_id)


def admin_delete_user(chat_id, actor, target_id):
    db.execute("DELETE FROM profiles WHERE user_id=?", (target_id,))
    db.execute("DELETE FROM users WHERE user_id=?", (target_id,))
    db.execute("DELETE FROM npcs WHERE user_id=?", (target_id,))
    db.execute("DELETE FROM missions WHERE user_id=?", (target_id,))
    db.execute("DELETE FROM inventory WHERE user_id=?", (target_id,))
    log_action(actor, "delete_user", str(target_id))
    api.send_message(chat_id, f"🗑 کاربر {fn(target_id)} به‌طور کامل حذف شد.", ADMIN_KB)


# ── آمار ──

def panel_admin_stats(chat_id):
    total   = db.fetchone("SELECT COUNT(*) c FROM users")["c"]
    banned  = db.fetchone("SELECT COUNT(*) c FROM users WHERE is_banned=1")["c"]
    chars   = db.fetchone("SELECT COUNT(*) c FROM profiles")["c"]
    online  = len([r for r in db.fetchall("SELECT last_seen FROM users")
                   if r["last_seen"] and (datetime.now() - datetime.fromisoformat(r["last_seen"])).total_seconds() < 300])
    games   = db.fetchone("SELECT COALESCE(SUM(games_played),0) s FROM profiles")["s"]
    money   = db.fetchone("SELECT COALESCE(SUM(money),0) s FROM profiles")["s"]
    popjob  = db.fetchone("""SELECT j.title, COUNT(*) c FROM profiles p JOIN jobs j ON j.id=p.job_id
                             GROUP BY p.job_id ORDER BY c DESC LIMIT 1""")
    txs     = db.fetchone("SELECT COALESCE(SUM(amount),0) s FROM transactions WHERE type='invest'")["s"]
    text = (f"📊 آمار ربات\n──────────\n"
            f"👥 کل کاربران: {fn(total)} (🚫 {fn(banned)})\n"
            f"🟢 آنلاین (۵ دقیقه اخیر): {fn(online)}\n"
            f"🎭 کاراکترهای ساخته‌شده: {fn(chars)}\n"
            f"🎲 مجموع رویدادهای زندگی: {fn(games)}\n"
            f"💰 پول کل کاربران: {fmt_money(money)} تومان\n"
            f"📉 نقدشوندگی سرمایه‌گذاری: {fmt_money(txs)}\n"
            f"💼 محبوب‌ترین شغل: {popjob['title'] + f' ({fn(popjob[chr(99)])})' if popjob else '—'}")
    api.send_message(chat_id, text, ADMIN_KB)


# ── مدیریت اقتصاد ──

def panel_admin_economy(chat_id):
    rows = [
        [("🏷 تغییر قیمت آیتم", "adm:ecoprice"), ("💼 تغییر حقوق شغل", "adm:ecosalary")],
        [("➕ افزودن آیتم جدید", "adm:ecoadditem"), ("📊 تنظیم نرخ درآمد", "adm:ecorate")],
    ]
    api.send_message(chat_id,
                     f"🏪 مدیریت اقتصاد\nنرخ درآمد فعلی: ×{get_setting('income_rate','1')}",
                     inline_keyboard(rows))


def admin_items_list(chat_id, prefix):
    items = db.fetchall("SELECT * FROM items WHERE is_active=1")
    rows = [[(f"{it['emoji']} {it['name']} — {fmt_money(it['price'])}", f"{prefix}:{it['id']}")] for it in items]
    api.send_message(chat_id, "🏷 یک آیتم را انتخاب کن:", inline_keyboard(rows))


def admin_jobs_list(chat_id, prefix):
    jobs = db.fetchall("SELECT * FROM jobs")
    rows = [[(f"{j['title']} — {fmt_money(j['base_salary'])}", f"{prefix}:{j['id']}")] for j in jobs]
    api.send_message(chat_id, "💼 یک شغل را انتخاب کن:", inline_keyboard(rows))


# ── مدیریت رویدادها ──

def panel_admin_events(chat_id):
    evs = db.fetchall("SELECT * FROM events WHERE is_active=1 ORDER BY id DESC LIMIT 15")
    lines = ["🎲 رویدادهای سفارشی:\n"]
    rows = [[("➕ ساخت رویداد جدید", "adm:evadd")]]
    for e in evs:
        lines.append(f"#{fn(e['id'])} {e['title']} | احتمال: {fn(e['probability'])}٪")
        rows.append([(f"🗑 حذف #{e['id']} — {e['title'][:12]}", f"adm:evdel:{e['id']}")])
    if not evs:
        lines.append("هنوز رویدادی نساختی.")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


# ── فرم‌های متنی ادمین (state machine) ──

def handle_admin_state(chat_id, uid, text, state, data):
    if not is_admin(uid):
        set_state(uid)
        return True

    if state == "adm_broadcast":
        data["text"] = text
        set_state(uid, "adm_broadcast_ok", data)
        api.send_message(chat_id, f"📢 پیش‌نمایش پیام همگانی:\n────────\n{text}\n────────\nارسال شود؟",
                         inline_keyboard([[("✅ ارسال", "adm:bc_yes"), ("❌ لغو", "adm:bc_no")]]))
        return True

    if state == "adm_dm_id":
        if not text.isdigit() or not db.fetchone("SELECT user_id FROM users WHERE user_id=?", (int(text),)):
            api.send_message(chat_id, "❌ آیدی عددی معتبرِ یک کاربر را بفرست:")
            return True
        set_state(uid, "adm_dm_text", {"to": int(text)})
        api.send_message(chat_id, "📝 متن پیام را بنویس:")
        return True

    if state == "adm_dm_text":
        to = data["to"]
        ok = api.send_message(to, f"📨 پیام از مدیریت:\n\n{text}")
        log_action(uid, "admin_dm", f"to={to}")
        set_state(uid)
        api.send_message(chat_id, "✅ ارسال شد." if ok else "⚠️ ارسال نشد (شاید کاربر ربات را بلاک کرده).", ADMIN_KB)
        return True

    if state == "adm_announce":
        db.execute("INSERT INTO announcements(text,created_at) VALUES(?,?)", (text, now_iso()))
        log_action(uid, "announcement", text[:60])
        set_state(uid)
        api.send_message(chat_id, "📣 اطلاعیه ثبت شد و برای همه نمایش داده می‌شود.", ADMIN_KB)
        return True

    if state == "adm_setcard":
        set_setting("owner_card", text.strip())
        log_action(uid, "admin_set_card", text[:20])
        set_state(uid)
        api.send_message(chat_id,
                         f"✅ کارت دریافت تنظیم شد:\n💳 {text.strip()}\n\n"
                         "از این به بعد سفارش‌های سکه به این کارت واریز می‌شود.", ADMIN_KB)
        return True

    if state == "adm_setchannel":
        ch = text.strip()
        if ch.startswith("https://t.me/"):
            ch = "@" + ch.split("/")[-1]
        set_setting("channel", ch)
        log_action(uid, "admin_set_channel", ch)
        set_state(uid)
        ok = channel_news("🛰 کانال اخبار «Life Simulator AI» متصل شد! از اینجا خبرهای جنگ، بازار و VIP رو دنبال کنید. 🎮")
        api.send_message(chat_id,
                         ("✅ کانال تنظیم شد و پست تست هم رفت!" if ok else
                          "⚠️ ذخیره شد ولی ارسال تست ناموفق بود — مطمئن شو ربات ادمین کانال است و آیدی درست است (@username یا -100...)"),
                         ADMIN_KB)
        return True

    if state == "adm_search":
        if text.isdigit():
            target = int(text)
            if db.fetchone("SELECT user_id FROM users WHERE user_id=?", (target,)):
                set_state(uid)
                admin_user_card(chat_id, target)
                return True
        rows = db.fetchall("""SELECT u.user_id, p.name FROM users u LEFT JOIN profiles p ON p.user_id=u.user_id
                              WHERE p.name LIKE ? OR u.username LIKE ? LIMIT 8""", (f"%{text}%", f"%{text}%"))
        if rows:
            set_state(uid)
            btns = [[(f"{r['name'] or 'بدون کاراکتر'} ({r['user_id']})", f"adm:user:{r['user_id']}")] for r in rows]
            api.send_message(chat_id, "🔍 نتایج جستجو:", inline_keyboard(btns))
        else:
            api.send_message(chat_id, "🔍 چیزی پیدا نشد. دوباره جستجو کن:")
        return True

    if state == "adm_money":
        target = data["target"]
        try:
            amount = int(text.replace(",", "").replace("−", "-").strip())
        except ValueError:
            api.send_message(chat_id, "⚠️ یک عدد معتبر بفرست (مثل +500 یا -200 یا 5000):")
            return True
        if text.strip().startswith(("+", "-", "−")):
            change_money(target, amount, "admin", "تغییر پول توسط ادمین")
        else:
            cur = profile(target)["money"]
            change_money(target, amount - cur, "admin", "ست پول توسط ادمین")
        log_action(uid, "admin_set_money", f"{target} -> {text}")
        set_state(uid)
        admin_user_card(chat_id, target)
        return True

    if state == "adm_level":
        target = data["target"]
        if not text.isdigit() or not (1 <= int(text) <= 100):
            api.send_message(chat_id, "⚠️ لول بین ۱ تا ۱۰۰:")
            return True
        db.execute("UPDATE profiles SET level=?, xp=0 WHERE user_id=?", (int(text), target))
        log_action(uid, "admin_set_level", f"{target} -> {text}")
        set_state(uid)
        admin_user_card(chat_id, target)
        return True

    if state == "adm_setprice":
        if not text.isdigit() or int(text) < 0:
            api.send_message(chat_id, "⚠️ قیمت معتبر (عدد):")
            return True
        db.execute("UPDATE items SET price=? WHERE id=?", (int(text), data["item_id"]))
        log_action(uid, "admin_set_price", f"item={data['item_id']} price={text}")
        set_state(uid)
        api.send_message(chat_id, f"✅ قیمت تغییر کرد به {fmt_money(int(text))} تومان.", ADMIN_KB)
        return True

    if state == "adm_setsalary":
        if not text.isdigit() or int(text) < 0:
            api.send_message(chat_id, "⚠️ حقوق معتبر (عدد):")
            return True
        db.execute("UPDATE jobs SET base_salary=? WHERE id=?", (int(text), data["job_id"]))
        log_action(uid, "admin_set_salary", f"job={data['job_id']} salary={text}")
        set_state(uid)
        api.send_message(chat_id, f"✅ حقوق تغییر کرد به {fmt_money(int(text))} تومان/شیفت.", ADMIN_KB)
        return True

    if state == "adm_ecorate":
        try:
            rate = float(text.replace(",", "."))
        except ValueError:
            rate = -1
        if not (0.1 <= rate <= 10):
            api.send_message(chat_id, "⚠️ نرخ بین ۰٫۱ تا ۱۰ (مثلا 1.5):")
            return True
        set_setting("income_rate", str(rate))
        log_action(uid, "admin_income_rate", str(rate))
        set_state(uid)
        api.send_message(chat_id, f"✅ نرخ درآمد سرور: ×{text}", ADMIN_KB)
        return True

    # افزودن آیتم: چند مرحله‌ای
    if state == "adm_item_name":
        set_state(uid, "adm_item_emoji", {"name": text})
        api.send_message(chat_id, "🏷 ایموجی آیتم را بفرست (مثلا 🎩):")
        return True
    if state == "adm_item_emoji":
        data["emoji"] = text[:4]
        set_state(uid, "adm_item_price", data)
        api.send_message(chat_id, "💵 قیمت آیتم (تومان):")
        return True
    if state == "adm_item_price":
        if not text.isdigit() or int(text) < 0:
            api.send_message(chat_id, "⚠️ قیمت معتبر:")
            return True
        data["price"] = int(text)
        set_state(uid, "adm_item_effect", data)
        effect_rows = [
            [("+۱۰ شادی 😊", "fx:h10"), ("+۱۰ سلامتی ❤️", "fx:he10"), ("+۱۰ انرژی ⚡", "fx:e10")],
            [("+۱ برنامه‌نویسی 👨‍💻", "fx:prog1"), ("+۱ هوش 🧠", "fx:int1"), ("+۱ ارتباطات 🗣", "fx:comm1")],
            [("+۵ اعتبار 🏆", "fx:rep5"), ("+۵۰ XP ⭐", "fx:xp50")],
        ]
        api.send_message(chat_id, "✨ اثر آیتم را انتخاب کن:", inline_keyboard(effect_rows))
        return True

    # ساخت رویداد
    if state == "adm_ev_title":
        set_state(uid, "adm_ev_text", {"title": text})
        api.send_message(chat_id, "📝 متن رویداد:")
        return True
    if state == "adm_ev_text":
        data["text"] = text
        set_state(uid, "adm_ev_prob", data)
        api.send_message(chat_id, "🎲 احتمال رخداد (درصد ۱ تا ۱۰۰):")
        return True
    if state == "adm_ev_prob":
        if not text.isdigit() or not (1 <= int(text) <= 100):
            api.send_message(chat_id, "⚠️ درصد بین ۱ تا ۱۰۰:")
            return True
        data["probability"] = int(text)
        set_state(uid, "adm_ev_reward", data)
        reward_rows = [
            [("+۵۰۰ 💰", "rw:m500"), ("+۱۰۰۰ 💰", "rw:m1000"), ("+۵۰ XP ⭐", "rw:xp50")],
            [("+۱۰ 😊", "rw:h10"), ("+۵ اعتبار 🏆", "rw:rep5"), ("ترکیبی 💰+⭐", "rw:combo")],
        ]
        api.send_message(chat_id, "🎁 پاداش رویداد:", inline_keyboard(reward_rows))
        return True

    return False


def admin_callback(chat_id, uid, data, cb_id, message_id):
    """کلیلک‌های اینلاین ادمین"""
    def ans(t=None):
        api.answer_callback(cb_id, t)

    if data == "adm:usearch":
        set_state(uid, "adm_search")
        api.send_message(chat_id, "🔍 نام یا آیدی کاربر را بنویس:")
        ans(); return True
    if data.startswith("adm:upage:"):
        panel_admin_users(chat_id, int(data.split(":")[2])); ans(); return True
    if data.startswith("adm:user:"):
        admin_user_card(chat_id, int(data.split(":")[2])); ans(); return True
    if data.startswith("adm:ban:"):
        admin_toggle_ban(chat_id, uid, int(data.split(":")[2])); ans("✅ انجام شد"); return True
    if data.startswith("adm:del:"):
        target = int(data.split(":")[2])
        api.send_message(chat_id, f"⚠️ مطمئنی کاربر {fn(target)} حذف شود؟",
                         inline_keyboard([[("🗑 بله، حذف کن", f"adm:delok:{target}"), ("❌ نه", "adm:cancel")]]))
        ans(); return True
    if data.startswith("adm:delok:"):
        admin_delete_user(chat_id, uid, int(data.split(":")[2])); ans("🗑 حذف شد"); return True
    if data.startswith("adm:money:"):
        target = int(data.split(":")[2])
        set_state(uid, "adm_money", {"target": target})
        api.send_message(chat_id, f"💰 مقدار را بفرست برای {fn(target)}:\n(+۵۰۰ اضافه | -۲۰۰ کم | ۵۰۰۰ ست مستقیم)")
        ans(); return True
    if data.startswith("adm:lvl:"):
        target = int(data.split(":")[2])
        set_state(uid, "adm_level", {"target": target})
        api.send_message(chat_id, "⭐ لول جدید (۱ تا ۱۰۰):")
        ans(); return True
    if data == "adm:bc_yes":
        st, sd = get_state(uid)
        text = sd.get("text", "")
        set_state(uid)
        users = db.fetchall("SELECT user_id FROM users WHERE is_banned=0")
        ok_c = fail_c = 0
        for r in users:
            res = api.send_message(r["user_id"], f"📢 اطلاعیه مدیریت:\n\n{text}")
            ok_c, fail_c = ok_c + (1 if res else 0), fail_c + (0 if res else 1)
        log_action(uid, "broadcast", f"sent={ok_c}")
        api.send_message(chat_id, f"📢 پیام همگانی: ✅ {fn(ok_c)} موفق | ❌ {fn(fail_c)} ناموفق", ADMIN_KB)
        ans("📢 ارسال شد"); return True
    if data == "adm:bc_no":
        set_state(uid)
        api.send_message(chat_id, "❌ لغو شد.", ADMIN_KB); ans(); return True
    if data == "adm:ecoprice":
        admin_items_list(chat_id, "adm:price"); ans(); return True
    if data.startswith("adm:price:"):
        set_state(uid, "adm_setprice", {"item_id": int(data.split(":")[2])})
        api.send_message(chat_id, "🏷 قیمت جدید (تومان):"); ans(); return True
    if data == "adm:ecosalary":
        admin_jobs_list(chat_id, "adm:salary"); ans(); return True
    if data.startswith("adm:salary:"):
        set_state(uid, "adm_setsalary", {"job_id": data.split(":")[2]})
        api.send_message(chat_id, "💼 حقوق جدید (تومان/شیفت):"); ans(); return True
    if data == "adm:ecoadditem":
        set_state(uid, "adm_item_name")
        api.send_message(chat_id, "➕ نام آیتم جدید:"); ans(); return True
    if data == "adm:ecorate":
        set_state(uid, "adm_ecorate")
        api.send_message(chat_id, "📊 نرخ درآمد جدید (مثل 1.5):"); ans(); return True
    if data.startswith("fx:"):
        st, sd = get_state(uid)
        if st != "adm_item_effect":
            ans("⚠️ منقضی شد"); return True
        fx_map = {"fx:h10": ({"happiness": 10}, "+۱۰ شادی 😊"), "fx:he10": ({"health": 10}, "+۱۰ سلامتی ❤️"),
                  "fx:e10": ({"energy": 10}, "+۱۰ انرژی ⚡"), "fx:prog1": ({"skill:prog": 1}, "+۱ برنامه‌نویسی 👨‍💻"),
                  "fx:int1": ({"skill:int": 1}, "+۱ هوش 🧠"), "fx:comm1": ({"skill:comm": 1}, "+۱ ارتباطات 🗣"),
                  "fx:rep5": ({"reputation": 5}, "+۵ اعتبار 🏆"), "fx:xp50": ({"xp": 50}, "+۵۰ XP ⭐")}
        effects, e_txt = fx_map[data]
        db.execute("INSERT INTO items(emoji,name,category,price,effect_text,effect_json) VALUES(?,?,?,?,?,?)",
                   (sd["emoji"], sd["name"], "shop", sd["price"], e_txt, jd(effects)))
        log_action(uid, "admin_add_item", sd["name"])
        set_state(uid)
        api.send_message(chat_id, f"✅ آیتم «{sd['emoji']} {sd['name']}» با قیمت {fmt_money(sd['price'])} اضافه شد!", ADMIN_KB)
        ans("✅ ذخیره شد"); return True
    if data == "adm:evadd":
        set_state(uid, "adm_ev_title")
        api.send_message(chat_id, "🎲 عنوان رویداد جدید:"); ans(); return True
    if data.startswith("rw:"):
        st, sd = get_state(uid)
        if st != "adm_ev_reward":
            ans("⚠️ منقضی شد"); return True
        rw_map = {"rw:m500": {"money": 500}, "rw:m1000": {"money": 1000}, "rw:xp50": {"xp": 50},
                  "rw:h10": {"happiness": 10}, "rw:rep5": {"reputation": 5},
                  "rw:combo": {"money": 500, "xp": 30}}
        sd["reward"] = rw_map[data]
        set_state(uid, "adm_ev_penalty", sd)
        pen_rows = [[("-۲۰۰ 💰", "pn:m200"), ("-۱۰ ❤️", "pn:he10"), ("-۱۰ 😊", "pn:h10")],
                    [("-۵ اعتبار 🏆", "pn:rep5"), ("بدون جریمه", "pn:none")]]
        api.send_message(chat_id, "⚠️ جریمه (برای ریسک ناموفق):", inline_keyboard(pen_rows))
        ans(); return True
    if data.startswith("pn:"):
        st, sd = get_state(uid)
        if st != "adm_ev_penalty":
            ans("⚠️ منقضی شد"); return True
        pn_map = {"pn:m200": {"money": -200}, "pn:he10": {"health": -10}, "pn:h10": {"happiness": -10},
                  "pn:rep5": {"reputation": -5}, "pn:none": {}}
        db.execute("INSERT INTO events(title,text,probability,reward_json,penalty_json,created_by) VALUES(?,?,?,?,?,?)",
                   (sd["title"], sd["text"], sd["probability"], jd(sd["reward"]), jd(pn_map[data]), uid))
        log_action(uid, "admin_add_event", sd["title"])
        set_state(uid)
        api.send_message(chat_id, f"✅ رویداد «{sd['title']}» با احتمال {fn(sd['probability'])}٪ ساخته شد و در چرخه‌ی رویدادها فعال است!", ADMIN_KB)
        ans("✅ ذخیره شد"); return True
    if data.startswith("adm:evdel:"):
        eid = int(data.split(":")[2])
        db.execute("UPDATE events SET is_active=0 WHERE id=?", (eid,))
        log_action(uid, "admin_del_event", str(eid))
        panel_admin_events(chat_id); ans("🗑 حذف شد"); return True
    if data == "adm:cancel":
        ans("اوکی"); return True
    return False


# ══════════════════════════════════════════════════════════════════
# [9] دیسپچر آپدیت‌ها
# ══════════════════════════════════════════════════════════════════

MENU_ROUTES = {
    "🎮 بازی": panel_game,
    "👤 پروفایل": panel_profile,
    "💼 شغل": panel_job,
    "🏠 خانه": lambda c, u: panel_shop(c, u, "house"),
    "🏪 بازار": panel_market,
    "⚔️ جنگ": panel_war,
    "🏰 امپراتوری": panel_empire,
    "🕶 هک": panel_hack,
    "👨‍👩‍👧 خانواده": panel_family,
    "🤝 اتحاد": panel_guild,
    "🐾 پت": panel_pet,
    "🏦 بانک": panel_bank,
    "💎 VIP": panel_vip,
    "💰 اقتصاد": panel_economy,
    "📚 مهارت‌ها": panel_skills,
    "👥 روابط": panel_relations,
    "🎯 ماموریت‌ها": panel_missions,
    "🏆 رتبه‌بندی": panel_leaderboard,
    "⚙ تنظیمات": panel_settings,
}


def handle_message(msg):
    tg_user = msg.get("from") or {}
    if not tg_user:
        return
    chat_id = msg["chat"]["id"]
    uid = ensure_user(tg_user)

    if is_banned(uid):
        api.send_message(chat_id, "🚫 حساب شما توسط مدیریت مسدود شده است.")
        return
    if not rate_limit_ok(uid):
        api.send_message(chat_id, "⏳ یه کم آروم‌تر! درخواست‌هات زیاد شد.")
        log_action(uid, "rate_limited")
        return

    text = (msg.get("text") or "").strip()

    # دستورات
    if text.startswith("/start"):
        ensure_missions(uid) if has_character(uid) else None
        cmd_start(chat_id, uid)
        return
    if text.startswith("/admin"):
        cmd_admin(chat_id, uid)
        return
    if text in ("/menu", "/بازگشت"):
        api.send_message(chat_id, "🏠 منوی اصلی:", MAIN_KB)
        return
    if text.startswith("/help"):
        panel_help(chat_id)
        return
    if text == "/cancel":
        set_state(uid)
        api.send_message(chat_id, "❌ عملیات لغو شد.", MAIN_KB)
        return

    # ورودی state-based (فرم‌ها)
    state, data = get_state(uid)
    if state:
        if handle_state_text(chat_id, uid, text, state, data):
            return

    # مسیرهای پنل ادمین (reply keyboard)
    if admin_router(chat_id, uid, text):
        return

    # منوی اصلی کاربر
    handler = MENU_ROUTES.get(text)
    if handler:
        handler(chat_id, uid)
        return

    # پیش‌فرض
    hints = [
        "از منوی پایین استفاده کن 👇",
        "روی یکی از دکمه‌های منو بزن! 🎮",
        "منوی بازی پایینه؛ «🎮 بازی» رو امتحان کن!",
    ]
    api.send_message(chat_id, pick(hints), MAIN_KB)


def handle_callback(cb):
    tg_user = cb.get("from") or {}
    uid = tg_user.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data") or ""
    cb_id = cb.get("id")
    if not (uid and chat_id and data):
        return

    if is_banned(uid):
        api.answer_callback(cb_id, "🚫 حساب مسدود است.")
        return
    if not rate_limit_ok(uid):
        api.answer_callback(cb_id, "⏳ آروم‌تر!")
        return

    # ── ساخت کاراکتر ──
    if data.startswith("crt:city:"):
        st, sd = get_state(uid)
        key = data.split(":")[2]
        if key == "custom":
            set_state(uid, "create_city_custom", sd)
            api.answer_callback(cb_id)
            api.send_message(chat_id, "✍️ نام شهرت رو بنویس:")
        else:
            sd["city"] = CITIES[int(key)]
            set_state(uid, "create_trait", sd)
            api.answer_callback(cb_id, f"🏙 {sd['city']}")
            send_trait_picker(chat_id)
        return
    if data.startswith("crt:trait:"):
        st, sd = get_state(uid)
        sd["trait"] = data.split(":")[2]
        api.answer_callback(cb_id, "🌟 عالی!")
        finish_character_creation(chat_id, uid, sd)
        return

    # ── ادمین ──
    if data.startswith("adm:") or data.startswith("fx:") or data.startswith("rw:") or data.startswith("pn:"):
        if not is_admin(uid):
            api.answer_callback(cb_id, "⛔ دسترسی نداری!")
            return
        if admin_callback(chat_id, uid, data, cb_id, message_id):
            return

    # ── ادمین: سفارش‌ها، بازار، کانال، رویداد جهانی (نیاز به دسترسی ادمین) ──
    if data.startswith(("ord:ok:", "ord:no:", "ord:view:", "card:", "chn:", "mktctl:", "wev:")):
        if not is_admin(uid):
            api.answer_callback(cb_id, "⛔ دسترسی نداری!")
            return
        if data.startswith("wev:"):
            if data == "wev:clear":
                set_setting("world_event", "")
                api.answer_callback(cb_id, "🛑 رویداد پایان یافت")
            else:
                msg_ = trigger_world_event(data.split(":")[1], actor=profile(uid)["name"] if profile(uid) else "ادمین")
                api.answer_callback(cb_id, "🌍 فعال شد!")
                api.send_message(chat_id, msg_)
            panel_admin_world(chat_id)
            return
        if not is_admin(uid):
            api.answer_callback(cb_id, "⛔ دسترسی نداری!")
            return
        if data.startswith("ord:ok:"):
            api.answer_callback(cb_id, "✅")
            api.send_message(chat_id, admin_order_decide(chat_id, uid, int(data.split(":")[2]), True))
        elif data.startswith("ord:no:"):
            api.answer_callback(cb_id, "❌")
            api.send_message(chat_id, admin_order_decide(chat_id, uid, int(data.split(":")[2]), False))
        elif data.startswith("ord:view:"):
            api.answer_callback(cb_id)
            admin_order_view(chat_id, int(data.split(":")[2]))
        elif data == "card:set":
            api.answer_callback(cb_id)
            set_state(uid, "adm_setcard")
            api.send_message(chat_id, "💳 شماره کارت جدید برای دریافت پول سکه‌ها را بنویس:")
        elif data == "chn:set":
            api.answer_callback(cb_id)
            set_state(uid, "adm_setchannel")
            api.send_message(chat_id, "🛰 آیدی کانال را بنویس (مثل @mychannel یا -1001234567890):")
        elif data == "chn:test":
            ok = channel_news("🧪 تست ارسال از پنل ادمین — ربات درست کار می‌کند! 🎮")
            api.answer_callback(cb_id, "✅ ارسال شد" if ok else "⚠️ ناموفق — ربات ادمین کانال است؟")
        elif data == "chn:top":
            ok = post_leaderboard_channel()
            api.answer_callback(cb_id, "🏆 ارسال شد" if ok else "⚠️ ناموفق")
        elif data == "chn:mkt":
            api.answer_callback(cb_id)
            admin_market_move(pick([s for s, _, _ in SEED_MARKETS]), pick(["pump", "dump"]))
        elif data.startswith("mktctl:"):
            parts = data.split(":")
            if parts[1] == "tick":
                update_market(force=True)
                api.answer_callback(cb_id, "🔄 قیمت‌ها تازه شد")
                panel_admin_marketctl(chat_id)
            else:
                api.answer_callback(cb_id, admin_market_move(parts[2], parts[1]))
        return

    # ── بازار بورس ──
    if data.startswith("mrko:"):
        api.answer_callback(cb_id)
        panel_market_trade(chat_id, uid, data.split(":")[2] if ":" in data[5:] else data.split(":")[1])
        return
    if data.startswith("mrkb:"):
        _, sym, amt = data.split(":")
        api.answer_callback(cb_id, "🛒")
        api.send_message(chat_id, market_buy(chat_id, uid, sym, amt))
        return
    if data.startswith("mrks:"):
        api.answer_callback(cb_id, "💰")
        api.send_message(chat_id, market_sell(chat_id, uid, data.split(":")[1]))
        return

    # ── جنگ ──
    if data == "war:targets":
        api.answer_callback(cb_id)
        war_targets(chat_id, uid)
        return
    if data.startswith("war:atk:"):
        api.answer_callback(cb_id, "⚔️")
        api.send_message(chat_id, war_attack(chat_id, uid, int(data.split(":")[2])))
        return
    if data == "war:boss":
        api.answer_callback(cb_id, "🐲")
        api.send_message(chat_id, boss_fight(chat_id, uid))
        return

    # ── VIP و سکه طلا ──
    if data == "vip:panel":
        api.answer_callback(cb_id)
        panel_vip(chat_id, uid)
        return
    if data == "vip:spend":
        api.answer_callback(cb_id)
        panel_vip_spend(chat_id, uid)
        return
    if data == "gem:shield":
        api.answer_callback(cb_id, "🛡")
        api.send_message(chat_id, gem_buy_shield(chat_id, uid))
        return
    if data == "gem:charge":
        api.answer_callback(cb_id, "⚡")
        api.send_message(chat_id, gem_charge(chat_id, uid))
        return
    if data == "gem:vip":
        api.answer_callback(cb_id, "👑")
        api.send_message(chat_id, gem_vip(chat_id, uid))
        return
    if data == "gem:spin":
        api.answer_callback(cb_id, "🎰")
        api.send_message(chat_id, gem_spin(chat_id, uid))
        return
    if data.startswith("ord:new:"):
        api.answer_callback(cb_id)
        order_new(chat_id, uid, data.split(":")[2])
        return
    if data.startswith("ord:paid:"):
        res = order_paid(chat_id, uid, int(data.split(":")[2]))
        api.answer_callback(cb_id, "✅")
        api.send_message(chat_id, res)
        return
    if data.startswith("ord:cancel:"):
        res = order_cancel(chat_id, uid, int(data.split(":")[2]))
        api.answer_callback(cb_id, "❌")
        api.send_message(chat_id, res)
        return

    # ── امپراتوری (منبع/ساختمان/ارتش) ──
    if data == "emp:shop":
        api.answer_callback(cb_id); panel_emp_shop(chat_id, uid); return
    if data.startswith("emp:buy:"):
        api.answer_callback(cb_id, "🌾")
        api.send_message(chat_id, empire_buy_res(chat_id, uid, data.split(":")[2])); return
    if data.startswith("emp:up:"):
        api.answer_callback(cb_id, "🔺")
        api.send_message(chat_id, empire_upgrade(chat_id, uid, data.split(":")[2])); return
    if data == "emp:recruit":
        api.answer_callback(cb_id, "🪖")
        api.send_message(chat_id, empire_recruit(chat_id, uid)); return
    if data == "emp:raid":
        api.answer_callback(cb_id); empire_raid_targets(chat_id, uid); return
    if data.startswith("emp:atk:"):
        api.answer_callback(cb_id, "⚔️")
        api.send_message(chat_id, empire_raid(chat_id, uid, int(data.split(":")[2]))); return

    # ── هک و دوئل ──
    if data == "hk:shop":
        api.answer_callback(cb_id); panel_hack_shop(chat_id, uid); return
    if data.startswith("hk:buy:"):
        api.answer_callback(cb_id, "🕶")
        api.send_message(chat_id, hack_buy(chat_id, uid, data.split(":")[2])); return
    if data == "hk:targets":
        api.answer_callback(cb_id); hack_targets(chat_id, uid); return
    if data == "hk:dueltg":
        api.answer_callback(cb_id); hack_targets(chat_id, uid, for_duel=True); return
    if data.startswith("hk:dstk:"):
        api.answer_callback(cb_id); panel_duel_stake(chat_id, uid, int(data.split(":")[2])); return
    if data.startswith("hk:new:"):
        _, _, tgt, stk = data.split(":")
        api.answer_callback(cb_id, "⚔️")
        api.send_message(chat_id, duel_create(chat_id, uid, int(tgt), int(stk))); return
    if data.startswith("hk:acc:"):
        api.answer_callback(cb_id, "⚔️ نبرد!")
        api.send_message(chat_id, duel_accept(chat_id, uid, int(data.split(":")[2]))); return
    if data.startswith("hk:dec:"):
        api.answer_callback(cb_id, "🐔")
        api.send_message(chat_id, duel_decline(chat_id, uid, int(data.split(":")[2]))); return
    if data.startswith("hk:atk:"):
        api.answer_callback(cb_id, "🕶")
        api.send_message(chat_id, hack_attack(chat_id, uid, int(data.split(":")[2]))); return

    # ── خانواده ──
    if data == "fam:propose":
        api.answer_callback(cb_id); family_propose_list(chat_id, uid); return
    if data.startswith("fam:prop:"):
        api.answer_callback(cb_id, "💍")
        api.send_message(chat_id, family_propose(chat_id, uid, int(data.split(":")[2]))); return
    if data.startswith("fam:acc:"):
        api.answer_callback(cb_id, "💒")
        api.send_message(chat_id, family_accept(chat_id, uid, int(data.split(":")[2]))); return
    if data.startswith("fam:dec:"):
        api.answer_callback(cb_id, "💔")
        api.send_message(chat_id, family_decline(chat_id, uid, int(data.split(":")[2]))); return
    if data == "fam:child":
        api.answer_callback(cb_id, "👶")
        api.send_message(chat_id, family_child(chat_id, uid)); return
    if data == "fam:bonus":
        api.answer_callback(cb_id, "🎁")
        api.send_message(chat_id, family_bonus(chat_id, uid)); return
    if data == "fam:divorce":
        api.answer_callback(cb_id); family_divorce(chat_id, uid); return
    if data == "fam:divok":
        api.answer_callback(cb_id, "💔")
        api.send_message(chat_id, family_divorce_ok(chat_id, uid)); return
    if data == "fam:no":
        api.answer_callback(cb_id, "❤️ خوب شد!"); return

    # ── اتحاد ──
    if data == "gld:create":
        api.answer_callback(cb_id)
        set_state(uid, "guild_create")
        api.send_message(chat_id, "🤝 نام اتحادت را بنویس:"); return
    if data == "gld:list":
        api.answer_callback(cb_id); guild_list(chat_id, uid); return
    if data == "gld:war":
        api.answer_callback(cb_id); guild_list(chat_id, uid, for_war=True); return
    if data.startswith("gld:join:"):
        api.answer_callback(cb_id, "🤝")
        api.send_message(chat_id, guild_join(chat_id, uid, int(data.split(":")[2]))); return
    if data.startswith("gld:donate:"):
        api.answer_callback(cb_id, "💰")
        api.send_message(chat_id, guild_donate(chat_id, uid, int(data.split(":")[2]))); return
    if data == "gld:leave":
        api.answer_callback(cb_id)
        api.send_message(chat_id, guild_leave(chat_id, uid)); return
    if data == "gld:kicklist":
        api.answer_callback(cb_id)
        res = guild_kick_list(chat_id, uid)
        if res: api.send_message(chat_id, res)
        return
    if data.startswith("gld:kick:"):
        api.answer_callback(cb_id, "👢")
        api.send_message(chat_id, guild_kick(chat_id, uid, int(data.split(":")[2]))); return
    if data.startswith("gld:dowar:"):
        api.answer_callback(cb_id, "⚔️")
        api.send_message(chat_id, guild_war(chat_id, uid, int(data.split(":")[2]))); return
    if data == "gld:disband":
        api.answer_callback(cb_id)
        api.send_message(chat_id, guild_disband(chat_id, uid)); return

    # ── پت ──
    if data.startswith("pet:buy:"):
        res = pet_buy(chat_id, uid, data.split(":")[2])
        api.answer_callback(cb_id, "🐾")
        if res:
            api.send_message(chat_id, res)
        else:
            api.send_message(chat_id, "🐾 نام پت جدیدت را بنویس:"); return

    if data == "pet:feed":
        api.answer_callback(cb_id, "🍖")
        api.send_message(chat_id, pet_feed(chat_id, uid)); return
    if data == "pet:play":
        api.answer_callback(cb_id, "🎾")
        api.send_message(chat_id, pet_play(chat_id, uid)); return
    if data == "pet:free":
        api.answer_callback(cb_id)
        api.send_message(chat_id, pet_free(chat_id, uid)); return

    # ── بانک ──
    if data.startswith("bnk:dep:"):
        mode = data.split(":")[2]
        api.answer_callback(cb_id, "🏦")
        api.send_message(chat_id, bank_deposit(chat_id, uid, mode)); return
    if data == "bnk:wd:all":
        api.answer_callback(cb_id, "💵")
        api.send_message(chat_id, bank_withdraw(chat_id, uid)); return
    if data.startswith("bnk:loan:"):
        api.answer_callback(cb_id, "🏧")
        api.send_message(chat_id, bank_loan(chat_id, uid, data.split(":")[2])); return
    if data == "bnk:repay":
        api.answer_callback(cb_id, "✅")
        api.send_message(chat_id, bank_repay(chat_id, uid)); return

    # ── بازی ──
    def ans(t=None):
        api.answer_callback(cb_id, t)

    if data == "game:new":
        ans()
        new_life_event(chat_id, uid)
    elif data.startswith("ev:"):
        ans()
        resolve_event_choice(chat_id, uid, message_id, int(data.split(":")[1]))
    elif data == "game:rest":
        ans(); do_rest(chat_id, uid)
    elif data == "game:sport":
        ans(); do_sport(chat_id, uid)
    elif data == "game:fun":
        ans(); do_fun(chat_id, uid)

    elif data.startswith("job:apply:"):
        result = job_apply(chat_id, uid, data.split(":")[2])
        ans(result[:180])
        api.send_message(chat_id, result)
    elif data == "job:work":
        result = job_work(chat_id, uid)
        ans(); api.send_message(chat_id, result)
    elif data == "job:promo":
        result = job_promo(chat_id, uid)
        ans(); api.send_message(chat_id, result)
    elif data == "job:quit":
        result = job_quit(chat_id, uid)
        ans(); api.send_message(chat_id, result)

    elif data.startswith("shop:buy:"):
        result = buy_item(chat_id, uid, int(data.split(":")[2]))
        ans("🛍"); api.send_message(chat_id, result)

    elif data == "eco:shop":
        ans(); panel_shop(chat_id, uid)
    elif data == "eco:inv":
        ans(); panel_invest(chat_id, uid)
    elif data == "eco:tx":
        ans(); panel_transactions(chat_id, uid)
    elif data.startswith("inv:"):
        result = do_invest(chat_id, uid, data.split(":")[1])
        ans(); api.send_message(chat_id, result)

    elif data.startswith("sk:train:"):
        result = train_skill(chat_id, uid, data.split(":")[2])
        ans(); api.send_message(chat_id, result)

    elif data.startswith("npc:chat:"):
        result = npc_chat(chat_id, uid, data.split(":")[2])
        ans(); api.send_message(chat_id, result)
    elif data.startswith("npc:gift:"):
        result = npc_gift(chat_id, uid, data.split(":")[2])
        ans(); api.send_message(chat_id, result)

    elif data.startswith("ms:claim:"):
        result = claim_mission(chat_id, uid, int(data.split(":")[2]))
        ans("🎁"); api.send_message(chat_id, result)

    elif data == "set:rename":
        set_state(uid, "rename")
        ans(); api.send_message(chat_id, "✏️ نام جدیدت را بنویس:", reply_keyboard([["لغو ❌"]]))
    elif data == "set:news":
        ans()
        news = db.fetchall("SELECT * FROM announcements ORDER BY id DESC LIMIT 3")
        txt = "📣 اطلاعیه‌ها:\n\n" + "\n\n".join(f"• {n['text']}  ({n['created_at'][:10]})" for n in news)
        api.send_message(chat_id, txt if news else "📣 اطلاعیه‌ای نیست.")
    elif data == "set:help":
        ans(); panel_help(chat_id)
    elif data == "set:reset":
        ans()
        api.send_message(chat_id, "⚠️ مطمئنی؟ کل زندگی مجازیت پاک می‌شود!",
                         inline_keyboard([[("🔄 بله، از نو!", "set:resetok"), ("❌ نه", "set:no")]]))
    elif data == "set:resetok":
        db.execute("DELETE FROM profiles WHERE user_id=?", (uid,))
        db.execute("DELETE FROM npcs WHERE user_id=?", (uid,))
        db.execute("DELETE FROM inventory WHERE user_id=?", (uid,))
        db.execute("DELETE FROM missions WHERE user_id=?", (uid,))
        set_state(uid)
        log_action(uid, "character_reset")
        ans("🔄 ریست شد")
        cmd_start(chat_id, uid)
    elif data == "set:no":
        ans("اوکی 👍")
    else:
        ans()


def handle_update(update):
    try:
        world_engine()  # موتور رویداد جهانی (هر ۴ ساعت، تنبل)
        if "message" in update:
            handle_message(update["message"])
        elif "callback_query" in update:
            handle_callback(update["callback_query"])
    except Exception as e:
        log.exception(f"💥 خطا در پردازش آپدیت {update.get('update_id')}: {e}")


# ══════════════════════════════════════════════════════════════════
# [10] حلقه‌ی اجرای اصلی
# ══════════════════════════════════════════════════════════════════

BANNER = """
╔══════════════════════════════════════════╗
║   🤖  Life Simulator AI برای بله  🤖     ║
║   بازی متنی شبیه‌ساز زندگی — نسخه ۱.۰   ║
╚══════════════════════════════════════════╝
"""


def main():
    global api, db
    print(BANNER)

    if not BOT_TOKEN or BOT_TOKEN.startswith("PUT_YOUR"):
        print("❌ توکن ربات تنظیم نشده!\n\n"
              "   📱 روی گوشی: فایل main.py را توی ادیتور باز کن و در بخش تنظیمات (\n"
              "      خطوط اول فایل) جای PUT_YOUR_BALE_BOT_TOKEN_HERE توکن را بگذار.\n"
              "      مثل:  BOT_TOKEN = \"123456789:AAf3k...\"\n\n"
              "   💻 روی سرور:  export BALE_BOT_TOKEN=\"توکن\"\n"
              "                 export BALE_ADMIN_IDS=\"آیدی-عددی-ادمین\"")
        return

    db = Database(DB_PATH)
    log.info(f"💾 دیتابیس آماده شد: {DB_PATH}")

    api = BaleAPI(BOT_TOKEN)
    me = api.call("getMe")
    if not me:
        log.error("❌ اتصال به بله ناموفق بود! توکن را چک کن.")
        return
    log.info(f"✅ ربات متصل شد: @{me.get('username')} ({me.get('first_name')})")
    log.info(f"👑 ادمین‌ها: {sorted({*ADMIN_IDS, *[r['user_id'] for r in db.fetchall('SELECT user_id FROM admins')]})}")
    log.info("🚀 شروع دریافت پیام‌ها (Ctrl+C برای توقف)...")

    api.call("deleteWebhook")  # اطمینان از حالت polling
    while True:
        try:
            for update in api.poll():
                handle_update(update)
        except KeyboardInterrupt:
            print("\n👋 خداحافظ! ربات متوقف شد.")
            break
        except Exception as e:
            log.exception(f"💥 خطای اصلی حلقه: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
