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
BOT_TOKEN = "714361062:qA9tKgbV8RDWobS6ZCHi-khu5IYnPmhp4Bs"      # مثل: "1234567890:AAf3k..."

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

# ── v5: ۲۰ فیچر جدید ──
PAWNBROKER_RATE = 0.7     # پیشه‌فروشی: ۷۰٪ قیمت
INSURANCE_COST = 200      # بیمه روزانه
CRIME_COOLDOWN = 600
JAIL_HOURS = 2
BAIL_COST = 800
TRAVEL_COST = 800

# 🏙 شهرها و بونس سفر — (نام، توضیح بونس)
TRAVEL_CITIES = [
    ("تهران",   "💼 +۵٪ حقوق"),
    ("کیش",     "🏝 کارمزد بورس نصف"),
    ("مشهد",    "🕌 شادی خانواده +۵ بیشتر"),
    ("اصفهان",  "🏗 تولید امپراتوری +۱۰٪"),
    ("شیراز",   "🎨 XP رویدادها +۱۰٪ (خلاقیت)"),
]

# 🎓 تحصیلات — (آیدی، نام، قیمت، بونس حقوق تجمعی)
DEGREES = [
    ("school", "📜 دیپلم",        2000,  0.05),
    ("bsc",    "🎓 لیسانس",       8000,  0.10),
    ("msc",    "🎓 فوق‌لیسانس",   25000, 0.15),
]

# 📛 لقب‌ها — (آیدی، نام، قیمت)
TITLES = [
    ("trader",  "💼 بازرگان بزرگ",  20000),
    ("hacker",  "🕶 ارباب سایبر",   30000),
    ("legend",  "🌟 افسانه شهر",    50000),
    ("king",    "👑 پادشاه",        150000),
]

# 🏭 کسب‌وکارهای غیرفعال — (آیدی، نام، قیمت، درآمد هر ۶ ساعت)
BUSINESSES = [
    ("bakery",  "🥖 نانوایی",   1500,  80),
    ("resto",   "🍽 رستوران",   6000,  300),
    ("startup", "💻 استارتاپ",  20000, 1200),
    ("factory", "🏭 کارخانه",   50000, 3500),
]

# 🏅 دستاوردها — (کلید، نام، آستانه با تابع روی پروفایل، جایزه)
ACHIEVEMENTS = [
    ("ev10",   "🎲 رویدادچی (۱۰ رویداد)",      lambda uid, p: p["games_played"] >= 10,          {"money": 500}),
    ("rich",   "🤑 کلان‌دار (۱۰۰هزار💰)",       lambda uid, p: p["money"] >= 100000,             {"gems": 5}),
    ("lvl10",  "⭐ حرفه‌ای (لول ۱۰)",          lambda uid, p: p["level"] >= 10,                  {"money": 1000}),
    ("fight5", "⚔️ جنگجو (۵ برد)",             lambda uid, p: log_count(uid, "war_win") >= 5,     {"money": 1000}),
    ("hack3",  "🕶 هکر حرفه‌ای (۳ نفوذ)",       lambda uid, p: log_count(uid, "hack_win") >= 3,    {"money": 1500}),
    ("love",   "💒 عروس و داماد",              lambda uid, p: log_count(uid, "married") >= 1,     {"money": 800}),
    ("boss1",  "🐲 باس‌کش (۱ شکار)",           lambda uid, p: log_count(uid, "boss_win") >= 1,    {"money": 700}),
    ("tycoon", "🏭 مغناط (۲ کسب‌وکار)",        lambda uid, p: db.fetchone("SELECT COUNT(*) c FROM businesses WHERE user_id=?", (uid,))["c"] >= 2, {"gems": 10}),
]

FORTUNES = [("lucky",  "🌟 خوش‌اقبال! امروز بورس بدون کارمزد و حقوق +۱۰٪"),
            ("normal", "🙂 روز عادی؛ کارت را بکش و برو جلو!"),
            ("unlucky","🌧 بدشانسی! حقوق ۱۰٪ کمتر می‌شود — مراقب باش!")]

# ═══════════════ 🆕 v6/v7: قابلیت‌های جدید — تنظیمات ═══════════════
# ⚖️ سازگار با قوانین جمهوری اسلامی: هیچ‌گونه شرط‌بندی/قمار در بازی نیست؛
#    بازی‌ها مهارتی و پاداش‌ها از صندوق فرهنگی/خزانه شهر پرداخت می‌شود.

# 🎡 شهربازی مهارتی (بدون شرط‌بندی)
ARCADE_DAILY_LIMIT = 5     # سقف روزانه هر بازی مهارتی
MATH_REWARD  = 150         # جایزه چالش ریاضی (از صندوق فرهنگی)
WORD_REWARD  = 250         # جایزه حدس کلمه
MEM_REWARD   = 300         # جایزه بازی حافظه
PENALTY_GOAL_REWARD = 60   # جایزه گل فرهنگی پنالتی

# 🔤 بانک کلمات «حدس کلمه» — (کلمه، راهنمای فرهنگی)
WORD_BANK = [
    ("کتابخانه", "جایی که کتاب‌ها خانه دارند"),
    ("برنامه‌نویس", "کسی که با کد حرف می‌زند"),
    ("ربات", "بی‌خیال، خودمم! 🤖"),
    ("مدرسه", "اولین دانشگاه همه"),
    ("فناوری", "علم به‌کاررفته در زندگی روزمره"),
    ("فرهنگ", "آداب و رفتار یک جامعه"),
    ("سلامت", "گنجی که با ورزش و خواب حفظ می‌شود"),
    ("دوستی", "بهترین سرمایه آدمی"),
    ("خانواده", "گرم‌ترین جای دنیا"),
    ("تلاش", "کلید طلایی موفقیت"),
    ("کتاب", "پنجره‌ای به عالم دانایی"),
    ("خیابان", "شریان شهر"),
    ("دوچرخه", "وسیله نقلیه پاک و سالم"),
    ("دندانپزشک", "قهرمان لبخندها 😁"),
    ("گلستان", "کاخ معروف تهران"),
    ("قرآن", "کتاب نور 🌙"),
    ("دانشگاه", "قله نشینِ مدرسه"),
    ("بیهقی", "حکیم بزرگ ادب پارسی"),
    ("موسیقی", "غذای روح"),
    ("شهردار", "مسئول نظم و زیبایی شهر 👑"),
]

# 🏛 خزانه شهر — از جریمه پلیس، مالیات شهردار و درصد فروش‌ها تغذیه می‌شود
#    و صرف جایزه قرعه‌کشی رایگان، گنج‌های شهر و حقوق شهردار می‌گردد.
CITY_TAX_DEFAULT = 0       # درصد مالیات شهری (شهردار می‌تواند ۰/۵/۱۰ تنظیم کند)

# 🎟 قرعه‌کشی رایگان روزانه (جایگزین لاتاری ـ بدون خرید بلیت، کاملاً مشروع)
LOTTERY_FREE_POT = 2500    # جایزه ثابت روزانه از خزانه فرهنگی شهر

# ═══════════════ 🆕 v7: پانزده قابلیت جدید — تنظیمات ═══════════════

# 📜 پیمان کاری — پنجمین شیفت هر روز = بونس بزرگ
WORK_CONTRACT_TARGET = 5
WORK_CONTRACT_MULT   = 3     # بونس = ۳ برابر حقوق همان شیفت

# 🏦 سپرده بلندمدت بانک
LOCK_DEPOSIT_DAYS = 3
LOCK_DEPOSIT_RATE = 0.08     # ۸٪ سود کامل پس از ۳ روز

# 🎓 دوره‌های آموزشی — (آیدی، نام، مهارت، قیمت شهریه، سقف ثبت‌نام)
COURSES = [
    ("sec",   "🛡 امنیت سایبری",     "hack", 3000, 3),
    ("mkt",   "📣 بازاریابی",        "comm", 2500, 3),
    ("proj",  "📊 مدیریت پروژه",     "mgmt", 3000, 3),
    ("crea",  "🎨 کارگاه خلاقیت",    "crea", 2000, 3),
    ("ai",    "🤖 هوش مصنوعی",       "prog", 3200, 3),
]

# 🐕 مدرسه پت
PET_TRAIN_LIMIT  = 2      # تمرین روزانه
PET_TRAIN_LEVEL  = 4      # هر ۴ تمرین = +۱ لول
PET_TRAIN_FOOD   = 1      # هزینه هر تمرین (🌾)

# 🤝 ماموریت هفتگی اتحاد
GQUEST_TARGET = 15        # برد جنگی جمعی اعضا در هفته
GQUEST_GEMS   = 8         # جایزه: سکه به خزانه اتحاد

# 💑 سفر خانوادگی
FAMILY_TRIP_COST = 500
FAMILY_TRIP_GEM_EVERY = 7   # هر هفتمین سفر: +۳💎

# 🎖 درجه‌های افتخار بر اساس لول — (حداقل لول، عنوان، بونس حقوق)
HONOR_RANKS = [
    (20, "👑 افسانه‌ی شهر", 0.10),
    (12, "💎 نخبه",         0.07),
    (7,  "⭐ شهروند نمونه", 0.04),
    (3,  "🌱 تازه‌وارد",    0.02),
    (1,  "🐣 نوزاد شهر",    0.00),
]

# 🛡 گارد امنیتی شخصی
GUARD_COST = 600          # محافظ یک‌روزه: یک حمله/هک/غارت را دفع می‌کند

# 📦 سفارش‌های امپراتوری (NPC) — (نیازمندی‌ها، مبلغ پاداش)
EMPIRE_ORDERS = [
    ({"food": 15},                   500),
    ({"iron": 8},                    700),
    ({"medicine": 4},                650),
    ({"food": 10, "iron": 5},        900),
    ({"iron": 3,  "medicine": 2},    600),
    ({"food": 25},                   850),
]
EMPIRE_ORDERS_DAILY = 3

# 🛍 معامله طلایی روزانه بازار
DAILY_DEAL_DISCOUNT = 0.75  # ۲۵٪ تخفیف قلم روزانه
DAILY_DEAL_PUMP     = 1.08  # پامپ ۸٪ دارایی روزانه بورس

# 📻 رادیو شهر — هر ۶ ساعت یک برنامه زنده
RADIO_INTERVAL = 6 * 3600
RADIO_LINES = [
    "🎙 رادیو بله‌سیم: صبحتان به نانِ داغ تازه‌پخت! نانوایی امروز اول شد 😄",
    "🎙 خبر ورزشی: تمرین‌های صبحگاهی پارک شهر پرشور بود. باشگاه یادت نره! 💪",
    "🎙 حکمتِ روز: «علم در جوانی، قوت در پیری است.» — حکیم بیهقی",
    "🎙 اقتصادِ سبزِ: کوچک‌ترین پس‌انداز تو، پلی به آینده‌ی بزرگت است 🌱",
    "🎙 طنزِ شهر: پیرمردی آینه خرید؛ گفت می‌خواهم خودم را مدیر کنم 😂",
    "🎙 ترافیک: خیابان آزادی خلوت است؛ به مقصد عشق برسید! 🚗💨",
    "🎙 کتابِ روز: «مثنوی معنوی» —‌ نیم‌صفحه در روز، عمرِ بهار!",
    "🎙 بهداشت: یک لیوان آب سردِ صبحگاهی، قلبت تشکرت می‌کند ❤️",
]

# 🌾 مزرعه — (آیدی، نام، هزینه بذر، محصول {ستون منابع: مقدار}، ساعت آماده شدن)
FARM_CROPS = [
    ("wheat", "🌾 گندم",       100, {"food": 60},      3),
    ("corn",  "🌽 ذرت",        250, {"food": 180},     6),
    ("herb",  "🌿 گیاه دارویی", 400, {"medicine": 5},  8),
]
FARM_SLOTS = 2

# 🧰 گاوصندوق منابع — ظرفیت هر منبع = سطح × ۱۰ | ارتقا: سطح×۱۵۰۰💰 + سطح×۵⚒️
VAULT_CAP_PER_LVL = 10

# 🗳️ شهردار هفته
MAYOR_ENTRY  = 1000    # هزینه کاندید شدن
MAYOR_SALARY = 1500    # حقوق روزانه شهردار (claim دستی)

# 👮 مشاغل نخبه — نیازمند مدرک تحصیلی
ELITE_JOBS = {"doctor": 1, "lawyer": 2, "police": 1}   # job_id → حداقل سطح مدرک
POLICE_PATROL_LIMIT = 3   # گشت روزانه
POLICE_REWARD_RATE  = 0.5 # سهم پلیس از جریمه مجرم

# 💱 صرافی سکه
GEM_BUY_PRICE  = 5000  # خرید ۱💎 با پول بازی
GEM_SELL_PRICE = 4000  # فروش ۱💎 → پول بازی
ADS_FEE        = 0.05  # کارمزد بازار آگهی (۵٪)

# 🏠 اجاره خانه — درآمد هر ۶ ساعت به ازای هر ملک
RENT_RATES = {"اتاق اجاره‌ای": 60, "آپارتمان": 250, "ویلای لوکس": 900}
RENT_MAINT   = 0.10    # ۱۰٪ هزینه نگهداری

# 💪 باشگاه — باف موقت جنگ
GYM_COST = 300
GYM_HOURS = 2
GYM_BUFF  = 1.15       # +۱۵٪ قدرت جنگ

# 🎂 جایزه تولد
BDAY_MONEY = 5000
BDAY_GEMS  = 15

# 🎁 شکار گنج — هر ~۳ ساعت یک صندوق؛ اولین نفر برنده است
TREASURE_INTERVAL = 3 * 3600

# 📅 ماموریت‌های هفتگی — (کلید، عنوان، اکشن لاگ، هدف، جایزه)
WEEKLY_DEF = [
    ("wm_war",  "⚔️ ۳ برد جنگی در این هفته",      "war_win",  3, {"money": 5000, "gems": 3}),
    ("wm_hack", "🕶 ۲ نفوذ موفق هک در این هفته",   "hack_win",  2, {"money": 4000, "gems": 2}),
    ("wm_xpl",  "🗺️ ۳ ماجراجویی (کاوش) در این هفته", "explore",  3, {"money": 3000, "gems": 2}),
]

# 🧩 بانک سوالات کوییز روزانه — (سوال، ۴ گزینه، شماره جواب درست)
QUIZ_BANK = [
    ("پایتخت ژاپن کجاست؟", ["توکیو", "پکن", "سئول", "بانکوک"], 0),
    ("کدام سیاره به «سیاره سرخ» معروف است؟", ["زهره", "مریخ", "مشتری", "زحل"], 1),
    ("HTTP مخفف چیست؟", ["HyperText Transfer Protocol", "High Tech Program", "Home Tool Page", "Hyper Transfer Text"], 0),
    ("بزرگ‌ترین اقیانوس جهان؟", ["اطلس", "هند", "آرام", "منجمد شمال"], 2),
    ("کدام‌یک حیوان خزنده است؟", ["نسر", "مار", "طاووس", "کانگورو"], 1),
    ("عدد پی (π) تقریباً چقدر است؟", ["2.71", "3.14", "1.61", "4.20"], 1),
    ("کدام یک زبان برنامه‌نویسی نیست؟", ["Python", "Java", "HTML", "C++"], 2),
    ("چکاوک، بلبل و ...؟ (پرنده ملی ایران)", ["عقاب", "پلیکان", "قناری", "همه می‌توانند باشند 😄"], 3),
    ("نور با چه سرعتی حرکت می‌کند؟", ["۳۰۰ هزار km/s", "۱۵۰ هزار km/s", "۱۰۰۰ km/s", "سرعت صوت"], 0),
    ("کدام فلز در دمای اتاق مایع است؟", ["آهن", "جیوه", "طلا", "آلومینیوم"], 1),
    ("واحد پول ایران چیست؟", ["دینار", "درهم", "ریال", "لیر"], 2),
    ("بیت‌کوین در چه سالی معرفی شد؟", ["۲۰۱۵", "۱۹۹۹", "۲۰۰۹", "۲۰۲۰"], 2),
    ("کدام ویتامین با نور خورشید ساخته می‌شود؟", ["A", "B12", "C", "D"], 3),
    ("RAM در کامپیوتر یعنی چه؟", ["حافظه موقت", "پردازنده", "کارت گرافیک", "هارددیسک"], 0),
    ("بلندترین قله ایران؟", ["سبلان", "دماوند", "علم‌کوه", "زردکوه"], 1),
    ("گران‌ترین فلز رایج جهان؟", ["نقره", "طلا", "مس", "آهن"], 1),
    ("چند ثانیه در یک ساعت هست؟", ["360", "3600", "600", "6000"], 1),
    ("کدام حیوان سریع‌ترین است؟", ["شیر", "یوزپلنگ", "اسب", "روباه"], 1),
]
QUIZ_DAILY   = 5      # تعداد سؤال در روز
QUIZ_REWARD  = 250    # جایزه هر جواب درست (+XP)
QUIZ_ALL_BONUS = 500  # بونس اگر همه درست بود

# 🗺️ ماجراجویی — هزینه هر کاوش
EXPLORE_ENERGY = 20

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
    # 🆕 v6: مشاغل نخبه — علاوه بر مهارت و لول، به 🎓 مدرک هم نیاز دارند (بخش تحصیل)
    ("doctor",   "🩺 پزشک",        "int",  5, 5,  4500),
    ("lawyer",   "⚖️ وکیل",        "comm", 5, 7,  7000),
    ("police",   "👮 افسر پلیس",   "int",  3, 6,  5500),
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

class TokenError(Exception):
    """توکن اشتباه است — چرخه polling باید متوقف شود"""


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
            code = data.get("error_code")
            if code in (401, 403, 404):
                raise TokenError(f"خطای {code}: توکن نامعتبر است! از ربات‌ساز بله توکن درست را بگیر.")
            if code == 409:
                log.warning("⚠️ Conflict: یه نسخه دیگر از ربات هم دارد همزمان کار می‌کند! (Pydroid یا سرور دیگر) — صبر می‌کنم...")
                time.sleep(10)
            else:
                log.warning(f"⚠️ getUpdates: {data}")
        except TokenError:
            raise
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
    ["🎡 سرگرمی", "🏙 شهر"],
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
                donations INTEGER DEFAULT 0, last_war TEXT, created_at TEXT,
                gems INTEGER DEFAULT 0
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
            CREATE TABLE IF NOT EXISTS lottery(
                day TEXT PRIMARY KEY, pot INTEGER, winner_id INTEGER,
                winner_text TEXT
            );
            CREATE TABLE IF NOT EXISTS tickets(
                user_id INTEGER, day TEXT,
                PRIMARY KEY(user_id, day)
            );
            CREATE TABLE IF NOT EXISTS bounties(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target INTEGER, amount INTEGER, setter INTEGER, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS achievements(
                user_id INTEGER, akey TEXT, granted_at TEXT,
                PRIMARY KEY(user_id, akey)
            );
            CREATE TABLE IF NOT EXISTS businesses(
                user_id INTEGER, biz_id TEXT,
                PRIMARY KEY(user_id, biz_id)
            );
            -- 🆕 v6
            CREATE TABLE IF NOT EXISTS ads(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller INTEGER, item_id INTEGER, price INTEGER, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS farm(
                user_id INTEGER, slot INTEGER, crop TEXT, ready_at TEXT,
                PRIMARY KEY(user_id, slot)
            );
            CREATE TABLE IF NOT EXISTS rvault(
                user_id INTEGER PRIMARY KEY,
                food INTEGER DEFAULT 0, iron INTEGER DEFAULT 0, medicine INTEGER DEFAULT 0,
                lvl INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS elec(
                week TEXT, candidate INTEGER, votes INTEGER DEFAULT 0,
                PRIMARY KEY(week, candidate)
            );
            CREATE TABLE IF NOT EXISTS elec_votes(
                week TEXT, voter INTEGER, candidate INTEGER,
                PRIMARY KEY(week, voter)
            );
            CREATE TABLE IF NOT EXISTS quiz(
                user_id INTEGER PRIMARY KEY, day TEXT, qidx TEXT, score INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS bj_games(
                user_id INTEGER PRIMARY KEY, cards TEXT, bet INTEGER, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS crime_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                criminal INTEGER, target INTEGER, amount INTEGER, created_at TEXT,
                busted INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS wmissions(
                user_id INTEGER, week TEXT, mkey TEXT, done INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, week, mkey)
            );
            CREATE TABLE IF NOT EXISTS rent(
                user_id INTEGER PRIMARY KEY, last_collect TEXT
            );
            CREATE TABLE IF NOT EXISTS birthday(
                user_id INTEGER PRIMARY KEY, day INTEGER, month INTEGER,
                last_year INTEGER DEFAULT 0
            );
            -- 🆕 v7
            CREATE TABLE IF NOT EXISTS gquests(
                guild_id INTEGER, week TEXT,
                PRIMARY KEY(guild_id, week)
            );
            CREATE TABLE IF NOT EXISTS eorders(
                user_id INTEGER PRIMARY KEY, day TEXT, data TEXT
            );
            """)
            self.conn.commit()
        self._migrate()

    def _migrate(self):
        """افزودن ستون‌های جدید به دیتابیس‌های قدیمی بدون پاک شدن داده‌ها"""
        plan = {
            "profiles": {
                "gems": "INTEGER DEFAULT 0", "vip": "INTEGER DEFAULT 0",
                "shield_until": "TEXT", "last_attack": "TEXT", "last_boss": "TEXT",
                "bank_balance": "INTEGER DEFAULT 0", "loan_debt": "INTEGER DEFAULT 0",
                "loan_due": "TEXT", "bank_last_int": "TEXT",
                "title": "TEXT", "edu": "INTEGER DEFAULT 0", "insured_until": "TEXT",
                "jail_until": "TEXT", "last_crime": "TEXT",
                "fortune": "TEXT", "fortune_day": "TEXT",
                "streak": "INTEGER DEFAULT 0", "last_streak": "TEXT",
                "rebirth": "INTEGER DEFAULT 0", "tower_floor": "INTEGER DEFAULT 1",
                "ref_by": "INTEGER DEFAULT 0", "ref_count": "INTEGER DEFAULT 0",
                # 🆕 v6
                "gym_until": "TEXT", "mayor_last": "TEXT",
                # 🆕 v7
                "work_shifts_day": "TEXT", "work_shifts": "INTEGER DEFAULT 0",
                "dep_locked": "INTEGER DEFAULT 0", "dep_until": "TEXT",
                "guard_day": "TEXT",
            },
            # 🆕 v7: استعداد پت + گنجینه سکه اتحاد
            "pets": {"talent": "TEXT"},
            "guilds": {"gems": "INTEGER DEFAULT 0"},
            "resources": {"biz_tick": "TEXT"},
        }
        for table, cols_ddl in plan.items():
            cols = {r[1] for r in self.fetchall(f"PRAGMA table_info({table})")}
            for col, ddl in cols_ddl.items():
                if col not in cols:
                    self.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

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

def cmd_start(chat_id, uid, ref=None):
    if has_character(uid):
        api.send_message(chat_id,
                         f"🌞 دوباره سلام {profile(uid)['name']}!\nبه زندگیت در Life Simulator AI ادامه بده! 👇",
                         MAIN_KB)
        return
    invite_txt = "\n\n🔗 (با دعوت یک دوست اومدی — بهش جایزه می‌رسه! 🎁)" if ref else ""
    api.send_message(chat_id, (
        "🎮 به «Life Simulator AI» خوش اومدی!\n\n"
        "اینجا یک زندگی مجازی می‌سازی: کار می‌کنی، 🏠 خانه و 🚗 ماشین می‌خری، "
        "دوست و رقیب پیدا می‌کنی و با هر انتخاب، سرنوشتت عوض می‌شه!\n\n"
        "✍️ قدم اول: اسم کاراکترت رو بنویس (مثلا: آرمان)" + invite_txt
    ), reply_keyboard([["لغو ❌"]]))
    set_state(uid, "create_name", {"ref": ref} if ref else None)


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
        data["name"] = text                      # ref و داده‌های قبلی حفظ شوند
        set_state(uid, "create_age", data)
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

    # ─── 🆕 v6: قیمت آگهی بازار ───
    if state == "ads_price":
        return ads_price_done(chat_id, uid, text, data or {})

    # ─── 🆕 v6: ثبت تولد ───
    if state == "bday_set":
        return birthday_set_done(chat_id, uid, text)

    # ─── 🆕 v7: شهربازی مهارتی (تایپ جواب) ───
    if state == "arcade_word":
        return word_answer(chat_id, uid, text, data or {})
    if state == "arcade_mem":
        return mem_answer(chat_id, uid, text, data or {})

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
    if data.get("ref"):
        db.execute("UPDATE profiles SET ref_by=? WHERE user_id=?", (data["ref"], uid))
        referral_grant(data["ref"], uid)
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
        [("🎉 تفریح (+شادی)", "game:fun"), ("🔥 جایزه روزانه", "daily:claim")],
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
    api.send_message(chat_id, render_profile(uid) + f"\n\n🎒 دارایی‌ها: {inv_txt}",
                     inline_keyboard([[("🏅 دستاوردها و افتخارات", "achv:view")]]))


# ───────── 💼 شغل ─────────

def panel_job(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    p = profile(uid)
    if p["job_id"]:
        job = db.fetchone("SELECT * FROM jobs WHERE id=?", (p["job_id"],))
        rows = [[("🛠 کار کردن (-۲۰⚡)", "job:work")],
                [("📈 درخواست ارتقا", "job:promo"), ("🚪 استعفا", "job:quit")]]
        if p["job_id"] == "police":   # 🆕 v6: قدرت ویژه پلیس
            used = db.fetchone("SELECT COUNT(*) c FROM logs WHERE actor=? AND action='police_patrol' AND created_at LIKE ?",
                               (uid, today() + "%"))["c"]
            rows.insert(0, [(f"🚓 گشت شبانه ({fn(POLICE_PATROL_LIMIT - used)}/{fn(POLICE_PATROL_LIMIT)} باقی)", "plc:go")])
        api.send_message(chat_id,
                         f"💼 شغل فعلی: {job['title']} — سطح {fn(p['job_level'])}\n"
                         f"💵 حقوق هر شیفت: حدود {fmt_money(int(job['base_salary'] * p['job_level'] * salary_mult(uid)))} تومان"
                         + ("\n🚓 به‌عنوان پلیس می‌توانی مجرمان اخیر را دستگیر کنی و جایزه بگیری!" if p["job_id"] == "police" else ""),
                         inline_keyboard(rows))
    else:
        skills = get_skills(uid)
        rows = []
        lines = ["💼 بازار کار — یکی رو انتخاب کن:\n"]
        for j in db.fetchall("SELECT * FROM jobs"):
            ok = (not j["min_skill"] or skills.get(j["min_skill"], 0) >= j["min_skill_level"]) and \
                 p["level"] >= j["min_level"]
            edu_req = ELITE_JOBS.get(j["id"])   # 🆕 v6
            if edu_req and (p.get("edu") or 0) < edu_req:
                ok = False
            req = f"{SKILLS.get(j['min_skill'],'-')} {fn(j['min_skill_level'])}+ | لول {fn(j['min_level'])}+" if j["min_skill"] else "بدون شرط"
            if edu_req:
                req += f" | 🎓 مدرک {fn(edu_req)}"
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
    need_edu = ELITE_JOBS.get(job_id)          # 🆕 v6: مشاغل نخبه مدرک می‌خواهند
    if need_edu and (p.get("edu") or 0) < need_edu:
        return f"🎓 این شغل نخبه‌محور است! نیاز به مدرک سطح {fn(need_edu)} (از پنل 🏙 شهر → تحصیل بگیر)"
    set_profile(uid, job_id=job_id, job_level=1)
    log_action(uid, "job_apply", job_id)
    return f"🎉 تبریک! به‌عنوان {job['title']} استخدام شدی! از پنل «💼 شغل» کار کن."


def job_work(chat_id, uid):
    if is_jailed(uid):
        return f"⛓ تو در زندانی تا {is_jailed(uid)[5:16]}! کسی کار نمی‌دهد... از پنل 🏙 شهر وثیقه بده."
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
    contract_txt = work_contract_tick(uid, salary)   # 🆕 v7: پیمان کاری ۵ شیفتی
    return (f"🛠 یک شیفت {job['title']} کامل کردی!\n💵 درآمد: {fmt_money(salary)} تومان"
            f"\n⭐ +۱۵ XP | ⚡ -۲۰ انرژی{extra}{contract_txt}" + ("\n" + "\n".join(lines) if lines else ""))


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
    deal = deal_item_id() if category == "shop" else 0   # 🆕 v7: معامله طلایی روزانه
    for it in items:
        owned = db.fetchone("SELECT id FROM inventory WHERE user_id=? AND item_id=?", (uid, it["id"]))
        price = int(it["price"] * DAILY_DEAL_DISCOUNT) if it["id"] == deal else it["price"]
        tag = " 🔥 معامله طلایی!" if it["id"] == deal else ""
        mark = "✅ داری" if owned else f"💵 {fmt_money(price)}{tag}"
        lines.append(f"{it['emoji']} {it['name']} — {mark}\n   ↳ {it['effect_text']}")
        if not owned:
            rows.append([(f"خرید {it['emoji']} {it['name']}{' 🔥' if it['id'] == deal else ''}", f"shop:buy:{it['id']}")])
    if category == "house":   # 🆕 v6: اجاره‌نامه
        own_any = db.fetchone("""SELECT 1 FROM inventory inv JOIN items i ON i.id=inv.item_id
                                 WHERE inv.user_id=? AND i.name IN ('اتاق اجاره‌ای','آپارتمان','ویلای لوکس') LIMIT 1""", (uid,))
        if own_any:
            lines.append("\n🏠 املاکت برایت مستأجر دارند! هر ۶ ساعت اجاره جمع می‌شود (۱۰٪ نگهداری).")
            rows.append([("💵 جمع‌کردن اجاره‌های عقب‌افتاده", "rnt:collect")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def buy_item(chat_id, uid, item_id):
    it = db.fetchone("SELECT * FROM items WHERE id=? AND is_active=1", (item_id,))
    if not it:
        return "❌ آیتم پیدا نشد!"
    if db.fetchone("SELECT id FROM inventory WHERE user_id=? AND item_id=?", (uid, it["id"])):
        return "⚠️ این آیتم را از قبل داری!"
    price = it["price"]
    if it["id"] == deal_item_id():                    # 🆕 v7: معامله طلایی امروز = ۲۵٪ تخفیف
        price = int(price * DAILY_DEAL_DISCOUNT)
    p = profile(uid)
    if p["money"] < price:
        return f"💸 پولت کم است! نیاز: {fmt_money(price)} تومان"
    change_money(uid, -price, "purchase", f"خرید {it['name']}")
    db.execute("INSERT OR IGNORE INTO inventory(user_id,item_id,purchased_at) VALUES(?,?,?)",
               (uid, it["id"], now_iso()))
    lines = apply_effects(uid, jl(it["effect_json"], {}), f"خرید {it['name']}")
    if it["category"] == "house":
        set_profile(uid, home=f"{it['emoji']} {it['name']}")
    log_action(uid, "buy", f"{it['name']} @{price}")
    deal_txt = "\n🔥 معامله طلایی امروز بود — ۲۵٪ تخفیف!" if it["id"] == deal_item_id() else ""
    return (f"🛍 خرید موفق: {it['emoji']} {it['name']}\n"
            f"💸 پرداخت: {fmt_money(price)} تومان{deal_txt}\n\n📊 اثر:\n" + ("\n".join(lines) or "—"))


# ───────── 💰 اقتصاد ─────────

def panel_economy(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    p = profile(uid)
    rows = [
        [("🛒 فروشگاه", "eco:shop"), ("📈 سرمایه‌گذاری", "eco:inv")],
        [("📈 سیگنال بورس", "eco:signal"), ("📦 دارایی‌های من", "eco:pf")],
        [("🏪 فروش اقلام (۷۰٪)", "eco:pawn"), ("💸 انتقال پول", "eco:pay")],
        [("🛒 بازار آگهی (کاربران)", "ads:list"), ("💱 صرافی سکه 💎", "exc:menu")],
        [("⚗️ ترکیب و ذوب آیتم", "crf:menu"), ("📛 لقب‌ها و عناوین", "tit:list")],
        [("🧾 تراکنش‌ها", "eco:tx")],
    ]
    api.send_message(chat_id,
                     f"💰 دفترچه‌ی اقتصاد\n💳 موجودی: {fmt_money(p['money'])} تومان\n"
                     f"🏦 سپرده: {fmt_money(p.get('bank_balance') or 0)}\n"
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
    btns.append([("📅 ماموریت‌های هفتگی (جایزه 💎)", "wms:view")])        # 🆕 v6
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
    """🏆 رتبه‌بندی چندبعدی — تب‌های ثروت/جنگ/اتحاد/برج/پت"""
    if not guard_character(chat_id, uid):
        return
    panel_leaderboard_tabs(chat_id, uid, "money")


# ───────── ⚙ تنظیمات ─────────

def panel_settings(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    rows = [
        [("✏️ تغییر نام", "set:rename"), ("🔗 لینک دعوت (جایزه!)", "ref:show")],
        [("⭐ بازتولد (لول ۱۰+)", "reb:ask"), ("📛 لقب‌ها", "tit:list")],
        [("🎂 تولد (جایزه سالانه 💎)", "bdy:menu"), ("📣 اطلاعیه‌ها", "set:news")],
        [("❓ راهنما", "set:help")],
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
            base = sp[4] + pet["level"] + (2 if pet.get("talent") == "war" else 0)   # 🆕 v7: استعداد جنگجو
            power += base if pet["hunger"] < 80 else base // 2
    power = int(power * (1 + (p.get("rebirth") or 0) * 0.05))  # بازتولد = قدرت ابدی
    if p.get("gym_until"):                                     # 💪 باف باشگاه (v6)
        try:
            if datetime.fromisoformat(p["gym_until"]) > datetime.now():
                power = int(power * GYM_BUFF)
        except Exception:
            pass
    return power


def gym_active(uid):
    """آیا باف باشگاه فعال است؟"""
    p = profile(uid)
    if p and p.get("gym_until"):
        try:
            return p["gym_until"] if datetime.fromisoformat(p["gym_until"]) > datetime.now() else None
        except Exception:
            return None
    return None


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
    city_mult = 1.1 if (profile(uid) or {}).get("city") == "اصفهان" else 1.0  # بونس شهر اصفهان
    news = []
    food  = r["food"] + ticks * r["farm"] * 5 * city_mult
    iron  = r["iron"] + ticks * r["mine"] * 3 * city_mult
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
    business_tick(uid)
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
    rows.append([("⚔️ حمله‌ی ارتشی (غارت منابع دشمن!)", "emp:raid"), ("🏭 کسب‌وکارها", "emp:biz")])
    rows.append([("🌻 مزرعه (پرورش محصول)", "far:menu"), ("🧰 گاوصندوق منابع", "vlt:menu")])   # 🆕 v6
    rows.append([("📨 سفارش‌های تاجران (روزانه)", "ord2:menu")])                              # 🆕 v7
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
    if is_jailed(uid):
        return f"⛓ در زندان چطور غارت کنی؟ (تا {is_jailed(uid)[5:16]})"
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
    gb = guard_blocks(target_id, p["name"], "غارت ارتشی")   # 🆕 v7: گارد شخصی
    if gb:
        return gb
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
             "🛡️ دوئل = مسابقه افتخاری ۳ رانده (بدون شرط) — برنده اعتبار و XP!")
    rows = [[("🛒 فروشگاه تجهیزات هک", "hk:shop")],
            [("🎯 هک کردن و دزدی منابع", "hk:targets")],
            [("🛡️ دوئل افتخاری هک", "hk:dueltg")]]
    my_duels = db.fetchall("""SELECT * FROM duels WHERE opponent=? AND status='pending'""", (uid,))
    if my_duels:
        lines += ["\n📩 درخواست‌های دوئل:"]
        for d in my_duels:
            cn = (profile(d["challenger"]) or {}).get("name", "?")
            rows.append([(f"🛡️ قبول دوئل افتخاری {cn}", f"hk:acc:{d['id']}"),
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
    if is_jailed(uid):
        return f"⛓ در زندان که کامپیوتر نداری! (تا {is_jailed(uid)[5:16]})"
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
    gb = guard_blocks(target_id, p["name"], "هک")   # 🆕 v7: گارد شخصی
    if gb:
        return gb
    atk, _ = hack_stats(uid)
    _, dfn = hack_stats(target_id)
    a = atk * random.uniform(0.8, 1.3)
    d = dfn * random.uniform(0.8, 1.3)

    if a > d:  # نفوذ موفق — منابع از قربانی دزدیده می‌شود و به هکر داده می‌شود
        money_steal = min(int(tp["money"] * random.uniform(0.03, 0.07)), 4000)
        if is_insured(target_id):
            money_steal //= 2
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


# ───── 🛡️ دوئل افتخاری هک (مسابقه‌وار — بدون شرط، سازگار با قوانین) ─────

def panel_duel_stake(chat_id, uid, target_id):
    t = profile(target_id)
    if not t:
        api.send_message(chat_id, "❌ هدف نیست."); return
    api.send_message(chat_id,
                     f"🛡️ چالش دوئل هک با {t['name']}\n\n«دوئل افتخاری» مسابقه‌ای دوستانه است — بدون شرط و پول!\n"
                     f"🏅 برنده: +۳۰⭐ و +۳ اعتبار | بازنده هم +۱۰⭐ می‌گیرد.",
                     inline_keyboard([[("🛡️ شروع دوئل افتخاری", f"hk:new:{target_id}:0")]]))


def duel_create(chat_id, uid, target_id, stake=0):
    p, t = profile(uid), profile(target_id)
    if not t:
        return "❌ هدف نیست."
    if uid == target_id:
        return "😂 با خودت؟"
    if db.fetchone("SELECT 1 FROM duels WHERE challenger=? AND status='pending'", (uid,)):
        return "⚠️ یک دوئل باز داری؛ صبر کن تا جواب بدهند."
    cur = db.execute("INSERT INTO duels(challenger,opponent,stake,status,created_at) VALUES(?,?,0,'pending',?)",
                     (uid, target_id, now_iso()))
    did = cur.lastrowid
    api.send_message(target_id,
                     f"🛡️ دعوت دوئل افتخاری!\n{p['name']} تو را به دوئل سایبری ۳ رانده دعوت کرده!\n"
                     f"🏅 برنده: +۳۰⭐ و +۳ اعتبار | بازنده: +۱۰⭐\n\nاز پنل «🕶 هک» قبول یا رد کن.",
                     inline_keyboard([[("✅ قبول دوئل", f"hk:acc:{did}"), ("❌ رد", f"hk:dec:{did}")]]))
    log_action(uid, "duel_create", f"#{did} vs {target_id} honor")
    return (f"🛡️ چالش دوئل افتخاری ثبت شد!\nبه {t['name']} خبر دادیم؛ اگه قبول کنه مسابقه شروع می‌شه!")


def duel_accept(chat_id, uid, did):
    d = db.fetchone("SELECT * FROM duels WHERE id=?", (did,))
    if not d or d["opponent"] != uid or d["status"] != "pending":
        return "⚠️ دوئل معتبر نیست."
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
    gain_xp(winner, 30); gain_xp(loser, 10)
    db.execute("UPDATE profiles SET reputation=MIN(100,reputation+3) WHERE user_id=?", (winner,))
    res = f"🛡️ دوئل: {pa['name']} {fn(wins_a)} — {fn(wins_b)} {pb['name']} | 🏆 {wp['name']}"
    db.execute("UPDATE duels SET status='done', result=?, finished_at=? WHERE id=?", (res, now_iso(), did))
    txt = ("\n".join(rounds) + f"\n━━━━━━━━━━━\n🏆 برنده مسابقه: {wp['name']}!"
           f"\n🏅 برنده: +۳۰⭐ و +۳ اعتبار | بازنده: +۱۰⭐")
    channel_news(f"🛡️ دوئل افتخاری سایبری!\n\n{res}")
    api.send_message(loser, f"😵 در دوئل #{fn(did)} دوم شدی!\n{txt}")
    api.send_message(winner, f"🏆 در دوئل #{fn(did)} پیروز شدی!\n{txt}")
    log_action(uid, "duel_done", res)
    return txt


def duel_decline(chat_id, uid, did):
    d = db.fetchone("SELECT * FROM duels WHERE id=?", (did,))
    if not d or d["opponent"] != uid or d["status"] != "pending":
        return "⚠️ معتبر نیست."
    db.execute("UPDATE duels SET status='declined', finished_at=? WHERE id=?", (now_iso(), did))
    api.send_message(d["challenger"], f"🤝 {(profile(uid) or {})['name']} فعلاً آماده نبود. دفعه دیگر! 💪")
    return "رد شد؛ سرِ سلامت! 🤝"


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
    # 📦 سبد دارایی کاربر در بالای پنل — با دکمه فروش مستقیم
    holdings = db.fetchall("""SELECT pf.symbol, pf.amount, pf.avg_price, m.name, m.price
                              FROM portfolio pf JOIN markets m ON m.symbol=pf.symbol
                              WHERE pf.user_id=? AND pf.amount>0""", (uid,))
    if holdings:
        total_val = 0
        lines.append("📦 دارایی‌های تو (برای فروش روی هرکدام بزن):")
        for h in holdings:
            val = h["amount"] * h["price"]
            total_val += val
            pnl = (h["price"] / h["avg_price"] - 1) * 100 if h["avg_price"] else 0
            lines.append(f"   {h['name']}: {fn(round(h['amount'],2))} واحد ≈ {fmt_money(val)}💰 ({fn(f'{pnl:+.1f}')}٪)")
            rows.append([(f"💱 فروش {h['name']}", f"mrks:{h['symbol']}")])
        lines.append(f"   💵 ارزش کل سبد: {fmt_money(total_val)}\n━━━━━━━━━━━")
    else:
        lines.append("📭 سبدت خالیه — پایین خرید کن!\n━━━━━━━━━━━")
    for r in db.fetchall("SELECT * FROM markets"):
        price, prev = r["price"], r["prev_price"] or r["price"]
        arrow = "📈" if price >= prev else "📉"
        pct = (price / prev - 1) * 100 if prev else 0
        lines.append(f"{r['name']}: {fmt_money(price)} {arrow} {fn(f'{abs(pct):.1f}')}٪")
        rows.append([(f"معامله {r['name']}", f"mrko:{r['symbol']}")])
    lines.append(f"\n💰 موجودی: {fmt_money(p['money'])} | کارمزد: ۲٪")
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


def trade_fee_for(uid):
    """کارمزد: کیش نصفه، طالع خوش‌اقبال رایگان"""
    fee = TRADE_FEE
    p = profile(uid)
    if p and p["city"] == "کیش":
        fee *= 0.5
    if fortune_of(uid) == "lucky":
        fee = 0
    return fee


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
    fee = int(amount * trade_fee_for(uid))
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
    fee = int(gross * trade_fee_for(uid))
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
    if is_jailed(uid):
        return f"⛓ تو زندانی! جنگ نمی‌تونی کنی تا {is_jailed(uid)[5:16]}."
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

    gb = guard_blocks(target_id, p["name"], "حمله جنگی")   # 🆕 v7: گارد شخصی
    if gb:
        return gb

    pa = battle_power(uid) * random.uniform(0.8, 1.2)
    pd = battle_power(target_id) * random.uniform(0.8, 1.2)

    if pa >= pd:  # 🏆 پیروزی حمله‌کننده
        loot = min(int(t["money"] * 0.08), 5000 + p["level"] * 200, t["money"])
        if is_insured(target_id) and loot > 0:
            loot //= 2  # 🏥 بیمه قربانی نصف غارت را جبران می‌کند
        if loot > 0:
            change_money(target_id, -loot, "war", f"غارت توسط {p['name']}")
            change_money(uid, loot, "war", f"غنیمت از {t['name']}")
        bounty = bounty_collect(uid, target_id)
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
        ins_txt = "\n🏥 حریف بیمه بود؛ غارت نصف شد!" if is_insured(target_id) else ""
        bty_txt = f"\n🎯 جایزه‌ی روی سرش را هم گرفتی: +{fmt_money(bounty)}💰!" if bounty else ""
        return (f"🏆 برنده شدی!\n💰 غنیمت: +{fmt_money(loot)} تومان | 🏆 +۳ اعتبار | ⭐ +۲۵ XP{bty_txt}{ins_txt}"
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

def broadcast_to_all(text, sender_name="مدیریت", header="📢 اطلاعیه مدیریت:"):
    """ارسال پیام به همه کاربران با for روی آیدی‌ها — گزارش موفق/ناموفق"""
    users = db.fetchall("SELECT user_id FROM users WHERE is_banned=0")
    ok_c = fail_c = 0
    for r in users:
        try:
            res = api.send_message(r["user_id"], f"{header}\n\n{text}")
            if res is not None:
                ok_c += 1
            else:
                fail_c += 1
        except Exception:
            fail_c += 1
    return ok_c, fail_c, len(users)


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
    """هر ۴ ساعت: رویداد جهانی + سیزن هفتگی (جوایز رتبه‌بندی) + 🆕 v6: گنج و شهردار"""
    try:
        ensure_treasure()     # 🆕 v6: صندوق گنج هر ~۳ ساعت
        ensure_daily_deal()   # 🆕 v7: معامله طلایی روزانه بازار
        radio_tick()          # 🆕 v7: رادیو شهر هر ۶ ساعت
    except Exception:
        pass
    # 🏁 سیزن هفتگی: هفته‌ی جدید → جوایز نفرات برتر هفته‌ی قبل
    iso = datetime.now().isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    if get_setting("season_week") != week:
        if get_setting("season_week"):  # اولین اجرا نباشد
            top = db.fetchall("SELECT user_id, name, money FROM profiles ORDER BY money DESC LIMIT 3")
            rewards = [30, 20, 10]
            lines = ["🏁 سیزن هفته تمام شد! نتایج:\n"]
            for i, tp in enumerate(top):
                add_gems(tp["user_id"], rewards[i])
                api.send_message(tp["user_id"], f"🏆 در سیزن هفتگی نفر {fn(i+1)} شدی! +{fn(rewards[i])}💎 سکه طلا!")
                lines.append(f"{['🥇','🥈','🥉'][i]} {tp['name']} — {fmt_money(tp['money'])}💰")
            channel_news("\n".join(lines) + "\n\n🎮 سیزن جدید شروع شد — برید جلو!")
            try:
                resolve_election(get_setting("season_week"))   # 🆕 v6: شهردار جدید!
            except Exception as e:
                log.warning(f"election: {e}")
        set_setting("season_week", week)
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
        rows = [[("🎁 دریافت پاداش روزانه", "fam:bonus"), (f"🧳 سفر خانوادگی ({fmt_money(FAMILY_TRIP_COST)}💰)", "ftrip:go")],
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
    if profile(uid)["city"] == "مشهد":  # بونس شهر مشهد
        db.execute("UPDATE profiles SET happiness=MIN(100,happiness+5) WHERE user_id=?", (uid,))
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
    """نرخ درآمد سرور × رویداد جهانی × پاداش اتحاد × شهر × مدرک × بازتولد × طالع"""
    mult = float(get_setting("income_rate", "1")) * income_mult()
    g = guild_of(uid)
    if g:
        mult *= 1 + min(guild_level(g), 10) * 0.01
    p = profile(uid)
    if p:
        if p["city"] == "تهران":
            mult *= 1.05
        mult *= 1 + (p.get("edu") or 0) * 0.05
        mult *= 1 + (p.get("rebirth") or 0) * 0.05
    fort = fortune_of(uid)
    if fort == "lucky":
        mult *= 1.10
    elif fort == "unlucky":
        mult *= 0.90
    if p:                                        # 🆕 v7: بونس حقوق درجه افتخار
        _, bonus = honor_rank(p["level"])
        mult *= 1 + bonus
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
            [("⚔️ ماموریت هفتگی اتحاد (💎)", "gqw:view")],          # 🆕 v7
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
    used = db.fetchone("SELECT COUNT(*) c FROM logs WHERE actor=? AND action='pet_race' AND created_at LIKE ?",
                       (uid, today() + "%"))["c"]
    tused = today_logs(uid, "pet_train")   # 🆕 v7: تمرینات امروز
    rows = [[("🍖 غذا (۳ 🌾)", "pet:feed"), ("🎾 بازی (-۳⚡)", "pet:play")],
            [(f"🏁 مسابقه پت ({fn(3-used)}/۳ باقی)", "prc:go")],          # 🆕 v6
            [(f"🎾 مدرسه پت ({fn(PET_TRAIN_LIMIT - tused)}/{fn(PET_TRAIN_LIMIT)} باقی، ۱🌾)", "ptr:go")]]   # 🆕 v7
    if not pet.get("talent"):                                                              # 🆕 v7: استعداد
        rows.append([("🛡 استعداد: جنگجو", "ptr:tal:war"), ("🏃 استعداد: دونده", "ptr:tal:race")])
    rows.append([("🕊 آزاد کردن", "pet:free")])
    talent_txt = f"🏅 استعداد: {'🛡 جنگجو (+۲ جنگ)' if pet.get('talent') == 'war' else '🏃 دونده (+۲ مسابقه)' if pet.get('talent') == 'race' else '—'}"
    api.send_message(chat_id,
                     f"🐾 «{pet['name']}» ({sp[1]}) — لول {fn(pet['level'])}\n━━━━━━━━━━━\n"
                     f"🍖 گرسنگی: {bar(pet['hunger'])} {fn(pet['hunger'])}\n"
                     f"😊 شادی: {bar(pet['happy'])} {fn(pet['happy'])}\n"
                     f"⚔️ بونس جنگ: +{fn(power)}{' (فعال ✅)' if pet['hunger'] < 80 else ' (گرسنه‌است، نصف ⚠️)'}\n"
                     f"{talent_txt}",
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
    # 🆕 v7: سپرده بلندمدت سه‌روزه با ۸٪ سود
    if (p.get("dep_locked") or 0) > 0:
        rows.append([("🔓 برداشت سپرده بلندمدت", "bnk:unlock")])
    else:
        rows.append([("🔒 سپرده ۳روزه ۵هزار (۸٪ سود)", "bnk:lock:5000"),
                     ("🔒 سپرده ۳روزه ۲۰هزار (۸٪)", "bnk:lock:20000")])
    locked_txt = ""
    if (p.get("dep_locked") or 0) > 0:
        locked_txt = f"\n🔒 سپرده قفل: {fmt_money(p['dep_locked'])} تا { (p.get('dep_until') or '')[:10] } (سود {fn(int(LOCK_DEPOSIT_RATE*100))}٪)"
    api.send_message(chat_id,
                     f"🏦 بانک شهر\n━━━━━━━━━━━\n"
                     f"💰 موجودی نقد: {fmt_money(p['money'])}\n"
                     f"🏦 سپرده: {fmt_money(p.get('bank_balance') or 0)} (سود روزانه ۱٪)\n"
                     f"💳 بدهی وام: {fmt_money(debt)}\n"
                     f"🏧 سقف وام تو: {fmt_money(max_loan)} (لول × ۲٬۰۰۰ + ۵٬۰۰۰)\n"
                     f"{due_txt}{locked_txt}", inline_keyboard(rows))


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
# [8.5] 🆕 v5: بیست فیچر خفن (قرعه‌کشی رایگان، برج، جنایت، بیمه، ...)
# ══════════════════════════════════════════════════════════════════

def log_count(uid, action):
    return db.fetchone("SELECT COUNT(*) c FROM logs WHERE actor=? AND action=?", (uid, action))["c"]

def is_jailed(uid):
    p = profile(uid)
    if p and p.get("jail_until"):
        try:
            if datetime.fromisoformat(p["jail_until"]) > datetime.now():
                return p["jail_until"]
        except Exception:
            pass
    return None

def is_insured(uid):
    p = profile(uid)
    if p and p.get("insured_until"):
        try:
            return datetime.fromisoformat(p["insured_until"]) > datetime.now()
        except Exception:
            return False
    return False

def fortune_of(uid):
    p = profile(uid)
    if p and p.get("fortune_day") == today():
        return p.get("fortune")
    return None


# ───── [1] 🎰 لاتاری روزانه ─────

def ensure_lottery():
    """قرعه‌کشی رایگان روزانه — پات ثابت از خزانه فرهنگی شهر (بدون فروش بلیت)"""
    db.execute("INSERT OR IGNORE INTO lottery(day,pot) VALUES(?,?)", (today(), LOTTERY_FREE_POT))

def lottery_draw():
    """قرعه‌کشی تنبل: وقتی روز جدید شروع شده، برنده دیروز را می‌کشیم"""
    y = db.fetchone("SELECT * FROM lottery WHERE day<? AND winner_id IS NULL AND pot>0 ORDER BY day DESC LIMIT 1",
                    (today(),))
    if not y:
        return
    tk = db.fetchall("SELECT user_id FROM tickets WHERE day=?", (y["day"],))
    winner = random.choice(tk)["user_id"] if tk else None
    if winner:
        change_money(winner, y["pot"], "raffle", f"برنده قرعه‌کشی رایگان {y['day']}")
        wn = (profile(winner) or {}).get("name", "?")
        db.execute("UPDATE lottery SET winner_id=?, winner_text=? WHERE day=?",
                   (winner, f"🎉 {wn} برنده {fmt_money(y['pot'])} تومان شد!", y["day"]))
        api.send_message(winner, f"🎉🎊 مبارکت باشه! تو برنده قرعه‌کشی رایگان {y['day']} شدی! 💰 {fmt_money(y['pot'])} تومان!")
        channel_news(f"🎉 برنده قرعه‌کشی رایگان دیشب!\n\n{wn} — {fmt_money(y['pot'])} تومان جایزه فرهنگی شهرداری! 🌙")
    else:
        db.execute("UPDATE lottery SET winner_id=-1, winner_text='بدون شرکت‌کننده' WHERE day=?", (y["day"],))


def panel_lottery(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    ensure_lottery(); lottery_draw()
    lot = db.fetchone("SELECT * FROM lottery WHERE day=?", (today(),))
    joined = db.fetchone("SELECT 1 FROM tickets WHERE user_id=? AND day=?", (uid, today()))
    cnt = db.fetchone("SELECT COUNT(*) c FROM tickets WHERE day=?", (today(),))["c"]
    last = db.fetchone("SELECT winner_text FROM lottery WHERE winner_id IS NOT NULL ORDER BY day DESC LIMIT 1")
    rows = []
    if not joined:
        rows.append([("🎟 شرکت رایگان در قرعه‌کشی امروز", "lot:buy")])
    api.send_message(chat_id,
                     f"🎟 قرعه‌کشی رایگان روزانه شهر\n━━━━━━━━━━━\n"
                     f"کاملاً رایگان و فرهنگی — جایزه از خزانه شهرداری! 🌙\n\n"
                     f"💰 جایزه امروز: {fmt_money(lot['pot'])} تومان\n"
                     f"👥 شرکت‌کننده‌ها تا الان: {fn(cnt)} نفر\n"
                     f"🎟 وضعیت تو: {'✅ شرکت کردی! به شانس جوانمردی 😄' if joined else '❌ هنوز شرکت نکردی'}\n"
                     f"⏰ قرعه‌کشی: اولین بازدید فردا\n\n"
                     f"{('دیروز: ' + last['winner_text']) if last and last['winner_text'] else ''}",
                     inline_keyboard(rows) if rows else None)


def lottery_buy(chat_id, uid):
    """شرکت رایگان در قرعه‌کشی — بدون هزینه (مشروع و فرهنگی)"""
    ensure_lottery()
    if db.fetchone("SELECT 1 FROM tickets WHERE user_id=? AND day=?", (uid, today())):
        return "🎟 امروز شرکت کردی! فردا قرعه‌کشی می‌شه 🌙"
    db.execute("INSERT INTO tickets(user_id,day) VALUES(?,?)", (uid, today()))
    gain_xp(uid, 5)
    log_action(uid, "raffle_join", today())
    return f"🎟 ثبت‌نام رایگان انجام شد! (+۵⭐)\nشاید امشب برنده‌ی {fmt_money(LOTTERY_FREE_POT)} تومان شدی! 🤞🌙"


# ───── [2] 🏛 خزانه شهر (جایگزین جک‌پات؛ بدون قمار، صرف امور فرهنگی) ─────

def treasury_amount() -> int:
    try:
        return int(get_setting("city_treasury", "") or 0)
    except Exception:
        return 0


def treasury_feed(amount: int, source=""):
    """تغذیه خزانه شهر از جریمه/مالیات (برای امور فرهنگی: گنج، قرعه‌کشی، حقوق شهردار)"""
    amount = int(amount)
    if amount > 0:
        set_setting("city_treasury", str(treasury_amount() + amount))
        log_action(0, "treasury_feed", f"+{amount} {source}")


def treasury_spend(amount: int) -> bool:
    if treasury_amount() < amount:
        return False
    set_setting("city_treasury", str(treasury_amount() - amount))
    return True


# ───── 🎡 شهربازی مهارتی (کاملاً مشروع ـ بدون شرط‌بندی) ─────

def panel_arcade(chat_id, uid):
    """شهربازی مهارتی: بازی‌های سرگرمی بدون قمار ـ جایزه از صندوق فرهنگی"""
    rows = [[("🧮 چالش ریاضی", "mat:go"), ("🔤 حدس کلمه", "wrd:go")],
            [("🧠 بازی حافظه", "mem:go"), ("⚽ تمرین پنالتی", "pnl:menu")]]
    done = {k: today_logs(uid, f"arcade_{k}") for k in ("math", "word", "mem", "pnl")}
    api.send_message(chat_id,
                     f"🎡 شهربازی مهارتی شهر\n━━━━━━━━━━━\n"
                     f"بازی کاملاً مهارتی و فرهنگی — بدون شرط‌بندی! جوایز از صندوق فرهنگی شهرداری 🌙\n"
                     f"(سقف هر بازی: {fn(ARCADE_DAILY_LIMIT)} بار در روز)\n\n"
                     f"🧮 ریاضی: {fn(done['math'])}/{fn(ARCADE_DAILY_LIMIT)} | 🔤 کلمه: {fn(done['word'])}/{fn(ARCADE_DAILY_LIMIT)}\n"
                     f"🧠 حافظه: {fn(done['mem'])}/{fn(ARCADE_DAILY_LIMIT)} | ⚽ پنالتی: {fn(done['pnl'])}/{fn(ARCADE_DAILY_LIMIT)}",
                     inline_keyboard(rows))


def arcade_limit_ok(uid, key) -> bool:
    return today_logs(uid, f"arcade_{key}") < ARCADE_DAILY_LIMIT


# 🧮 چالش ریاضی — مهارت واقعی (پاسخ با دکمه)
def math_play(chat_id, uid):
    if not arcade_limit_ok(uid, "math"):
        return "🧮 سهمیه امروز چالش ریاضی تمام شد! فردا بیا."
    a, b, c = random.randint(5, 25), random.randint(3, 18), random.randint(2, 15)
    op = random.choice([("همه را جمع کن", a + b + c), ("دو تای اول را جمع و سومی را کم کن", a + b - c),
                        ("دو تای اول را در هم ضرب و سومی را کم کن", a * b - c)])
    ans = op[1]
    opts = {ans, ans + 2, ans - 3, ans + 5}
    while len(opts) < 4:
        opts.add(ans + random.randint(-9, 9) or 4)
    opts = list(opts)
    random.shuffle(opts)
    set_state(uid, "arcade_math", {"ans": ans})
    rows = [[(fn(o), f"mat:a:{o}") for o in opts[:2]], [(fn(o), f"mat:a:{o}") for o in opts[2:]]]
    api.send_message(chat_id,
                     f"🧮 چالش ریاضی:\n\n{op[0]}:\n{fn(a)} ، {fn(b)} ، {fn(c)}\n\nجواب چنده؟ 🤔",
                     inline_keyboard(rows))
    return None


def math_answer(chat_id, uid, picked):
    state, data = get_state(uid)
    if state != "arcade_math" or not data:
        return "⏰ این چالش منقضی شده؛ دوباره شروع کن!"
    set_state(uid)
    log_action(uid, "arcade_math", "")
    if int(picked) == data.get("ans"):
        change_money(uid, MATH_REWARD, "arcade", "جایزه چالش ریاضی (صندوق فرهنگی)")
        gain_xp(uid, 10)
        return f"🧮✅ درسته! باهوشی! جایزه فرهنگی: +{fmt_money(MATH_REWARD)}💰 +۱۰⭐"
    gain_xp(uid, 3)
    return f"🧮❌ نه! جواب درست {fn(data.get('ans'))} بود. فردا تمرین کن! 💪 (+۳⭐)"


# 🔤 حدس کلمه — مهارت، با تایپ جواب
def word_play(chat_id, uid):
    if not arcade_limit_ok(uid, "word"):
        return "🔤 سهمیه امروز حدس کلمه تمام شد! فردا بیا."
    word, hint = pick(WORD_BANK)
    chars = list(word)
    for _ in range(6):
        random.shuffle(chars)
        if "".join(chars) != word:
            break
    set_state(uid, "arcade_word", {"word": word})
    api.send_message(chat_id,
                     f"🔤 حدس کلمه!\n\nحروف به‌هم‌ریخته: «{' '.join(chars)}»\n"
                     f"💡 راهنما: {hint}\n\nکلمه درست را بنویس ✍️ (برای لغو: لغو ❌)")
    return None


def word_answer(chat_id, uid, text, data):
    word = (data or {}).get("word", "")
    norm = lambda s: (s or "").strip().replace("ي", "ی").replace("ك", "ک").replace(" ", "")
    set_state(uid)
    log_action(uid, "arcade_word", "")
    if norm(text) == norm(word):
        change_money(uid, WORD_REWARD, "arcade", "جایزه حدس کلمه (صندوق فرهنگی)")
        gain_xp(uid, 15)
        api.send_message(chat_id, f"🔤✅ آفرین! «{word}» درست بود! +{fmt_money(WORD_REWARD)}💰 +۱۵⭐", MAIN_KB)
    else:
        gain_xp(uid, 3)
        api.send_message(chat_id, f"🔤❌ نشد! کلمه «{word}» بود. (+۳⭐ سعی قشنگی بود 😄)", MAIN_KB)
    return True


# 🧠 بازی حافظه — مهارت واقعی
def mem_play(chat_id, uid):
    if not arcade_limit_ok(uid, "mem"):
        return "🧠 سهمیه امروز بازی حافظه تمام شد! فردا بیا."
    seq = "".join(str(random.randint(0, 9)) for _ in range(5))
    set_state(uid, "arcade_mem", {"seq": seq})
    api.send_message(chat_id,
                     f"🧠 بازی حافظه!\n\nاین ۵ رقم را ۳۰ ثانیه نگاه کن و حفظش کن:\n\n"
                     f"🔢  {fn(seq)}\n\nوقتی آماده‌ای همان اعداد را بنویس ✍️")
    return None


def mem_answer(chat_id, uid, text, data):
    seq = (data or {}).get("seq", "")
    got = parse_num(text)
    set_state(uid)
    log_action(uid, "arcade_mem", "")
    if got == seq:
        change_money(uid, MEM_REWARD, "arcade", "جایزه بازی حافظه (صندوق فرهنگی)")
        gain_xp(uid, 20)
        api.send_message(chat_id, f"🧠✅ واااای! حافظه فولادی داری! +{fmt_money(MEM_REWARD)}💰 +۲۰⭐", MAIN_KB)
    else:
        gain_xp(uid, 3)
        api.send_message(chat_id, f"🧠❌ عددها {fn(seq)} بودند! حافظه با تمرین قوی می‌شه 💪 (+۳⭐)", MAIN_KB)
    return True


# ⚽ تمرین پنالتی — ورزشی، بدون شرط‌بندی
def panel_penalty(chat_id, uid):
    if not arcade_limit_ok(uid, "pnl"):
        api.send_message(chat_id, "⚽ سهمیه امروز تمرین پنالتی تمام شد! فردا بیا.")
        return
    rows = [[("⬅️ بالا-چپ", "pnl:k:0"), ("➡️ بالا-راست", "pnl:k:1")],
            [("↙️ پایین-چپ", "pnl:k:2"), ("↘️ پایین-راست", "pnl:k:3")]]
    api.send_message(chat_id,
                     "⚽ تمرین پنالتی باشگاه شهر\n━━━━━━━━━━━\nورزکاری و سالم! تو شوت می‌زنی، دژا دروازه‌بان بات!\n"
                     "گل بزنی: جایزه ورزشی باشگاه (+۶۰💰 +۸⭐)",
                     inline_keyboard(rows))


def penalty_kick(chat_id, uid, corner):
    log_action(uid, "arcade_pnl", "")
    keeper = random.randint(0, 4)  # ۴ گوشه + وسط (سخت‌تر برای تمرین)
    corners = ["⬅️ بالا-چپ", "➡️ بالا-راست", "↙️ پایین-چپ", "↘️ پایین-راست"]
    mine = int(corner)
    gain_xp(uid, 8)
    if mine != keeper:
        change_money(uid, PENALTY_GOAL_REWARD, "arcade", "جایزه ورزشی پنالتی باشگاه")
        return (f"⚽ شوت به {corners[mine]}... گلوووول! 🥅🎉\n"
                f"دروازه‌بان راه {corners[keeper] if keeper < 4 else 'وسط'} رو انتخاب کرده بود!\n"
                f"🏅 جایزه ورزشی: +{fmt_money(PENALTY_GOAL_REWARD)}💰 +۸⭐")
    gain_xp(uid, 3)
    return (f"⚽ شوت به {corners[mine]}... دروازه‌بان مهار کرد! 🧤\n"
            f"تمرین همیشه ارزشمنده (+۵⭐). فردا دوباره! 💪")


# ───── [3] 🧗 برج قهرمانان (PVE طبقاتی) ─────

def tower_fight(chat_id, uid):
    p = profile(uid)
    if p["energy"] < 15:
        return "🔋 ۱۵ انرژی لازم است!"
    floor = p.get("tower_floor") or 1
    enemy_name, enemy_pwr = pick([("🧟 زامبی", 1.0), ("🤖 روبات", 1.1), ("👹 دیو", 1.2), ("🗿 غول", 0.9)])
    ep = floor * 25 * enemy_pwr + random.uniform(0, 30)
    db.execute("UPDATE profiles SET energy=MAX(0,energy-15) WHERE user_id=?", (uid,))
    my = battle_power(uid) * random.uniform(0.9, 1.2)
    if my > ep:
        reward = floor * 150
        change_money(uid, reward, "tower", f"طبقه {floor} برج")
        gain_xp(uid, 20 + floor * 2)
        db.execute("UPDATE profiles SET tower_floor=tower_floor+1 WHERE user_id=?", (uid,))
        if floor % 5 == 0:
            channel_news(f"🧗 رکورد برج!\n{profile(uid)['name']} طبقه {fn(floor)} را فتح کرد!")
        return (f"🧗 طبقه {fn(floor)}: {enemy_name} شکست خورد!\n"
                f"💰 +{fmt_money(reward)} تومان | ⭐ XP\nصعود به طبقه {fn(floor+1)}! 🚀")
    db.execute("UPDATE profiles SET health=MAX(0,health-10) WHERE user_id=?", (uid,))
    gain_xp(uid, 8)
    return (f"🧗 طبقه {fn(floor)}: {enemy_name} گذاشتت زمین! 😵\n"
            f"❤️ -۱۰ سلامتی — قوی شو (ارتش، پت، VIP) و برگرد!")


# ───── [4] 🔮 طالع روز ─────

def fortune_roll(chat_id, uid):
    if fortune_of(uid):
        f = dict(FORTUNES)
        return f"🔮 طالع امروزت (از قبل کشیدی):\n{f.get(fortune_of(uid), '—')}"
    key, text = random.choice(FORTUNES)
    db.execute("UPDATE profiles SET fortune=?, fortune_day=? WHERE user_id=?", (key, today(), uid))
    return f"🔮 طالع امروزت:\n{text}"


# ───── [5] 📈 سیگنال/تحلیل بورس ─────

def panel_signal(chat_id, uid):
    skills = get_skills(uid)
    trust = min(90, 40 + skills.get("int", 0) * 6)
    lines = [f"📈 سیگنال تحلیل‌گران (اعتماد تحلیل: {fn(trust)}٪ — با 🧠 هوش بالا می‌رود)\n"]
    rows = []
    for r in db.fetchall("SELECT * FROM markets"):
        tr = r["trend"] or 0
        sig = "🟢 صعودی" if tr > 0.05 else "🔴 نزولی" if tr < -0.05 else "⚪ خنثی"
        if random.randint(0, 100) > trust:
            sig = "❓ نامشخص"
        lines.append(f"{r['name']}: {sig}")
    lines.append("\n⚠️ تحلیل تضمینی نیست؛ ریسک با خودت! 😄")
    api.send_message(chat_id, "\n".join(lines))


# ───── [6] 📦 دارایی‌های من (سبد بورس) + [7] 🏪 فروش اقلام (پیشه‌فروشی) ─────

def panel_portfolio(chat_id, uid):
    panel_market(chat_id, uid)  # سبد دارایی در بالای بازار نمایش داده می‌شود

def panel_pawn(chat_id, uid):
    rows = []
    lines = ["🏪 پیشه‌فروشی — اقلامت به قیمت ۷۰٪ پس گرفته می‌شود\n"]
    inv = db.fetchall("""SELECT inv.item_id, i.emoji, i.name, i.price, i.category FROM inventory inv
                         JOIN items i ON i.id=inv.item_id WHERE inv.user_id=?""", (uid,))
    if not inv:
        lines.append("چیزی برای فروش نداری!")
    for it in inv:
        back = int(it["price"] * PAWNBROKER_RATE)
        lines.append(f"{it['emoji']} {it['name']} → پس‌دادن: {fmt_money(back)}💰")
        rows.append([(f"بفروش {it['emoji']} {it['name']} ({fmt_money(back)})", f"pp:{it['item_id']}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def pawn_sell(chat_id, uid, item_id):
    inv = db.fetchone("""SELECT i.price, i.name, i.emoji, i.category FROM inventory inv
                         JOIN items i ON i.id=inv.item_id
                         WHERE inv.user_id=? AND inv.item_id=?""", (uid, item_id))
    if not inv:
        return "❌ این قلم را نداری!"
    back = int(inv["price"] * PAWNBROKER_RATE)
    db.execute("DELETE FROM inventory WHERE user_id=? AND item_id=?", (uid, item_id))
    if inv["category"] == "house":
        set_profile(uid, home="پناهگاه")
    change_money(uid, back, "pawn", f"فروش {inv['name']}")
    log_action(uid, "pawn", f"{inv['name']} +{back}")
    return f"💰 {inv['emoji']} {inv['name']} را با {fmt_money(back)} تومان پس فروختی."


# ───── [8] 💸 انتقال پول به بازیکن ─────

def panel_pay_targets(chat_id, uid):
    rows = []
    for t in db.fetchall("""SELECT p.user_id, p.name FROM profiles p
                            JOIN users u ON u.user_id=p.user_id
                            WHERE p.user_id!=? AND u.is_banned=0
                            ORDER BY u.last_seen DESC LIMIT 8""", (uid,)):
        rows.append([(f"💸 انتقال به {t['name']}", f"pay:{t['user_id']}")])
    api.send_message(chat_id, "💸 کی‌قراره پول بفرستی؟ (کارمزد ۵٪)", inline_keyboard(rows))


def pay_user(chat_id, uid, target_id, amount):
    t = profile(target_id)
    if not t:
        return "❌ مقصد نیست."
    p = profile(uid)
    amount = int(amount)
    if amount < 100:
        return "💸 حداقل ۱۰۰ تومان."
    fee = int(amount * 0.05)
    tax = tax_apply(uid, amount, "transfer")          # 🆕 v7: مالیات شهردار (اگر تنظیم شده)
    total = amount + fee + tax
    if p["money"] < total:
        return f"💸 {fmt_money(total)} لازم است (کارمزد + مالیات شهر {fn(city_tax_rate()*100)}٪)."
    change_money(uid, -total, "transfer", f"انتقال به {t['name']}")
    change_money(target_id, amount, "transfer", f"دریافت از {p['name']}")
    api.send_message(target_id, f"💌 {p['name']} برایت {fmt_money(amount)} تومان فرستاد!")
    log_action(uid, "transfer", f"to={target_id} amount={amount}")
    tax_txt = f" + مالیات شهر {fmt_money(tax)}" if tax else ""
    return f"✅ {fmt_money(amount)} تومان به {t['name']} رسید (کارمزد: {fmt_money(fee)}{tax_txt})."


# ───── [9] 📛 لقب‌ها ─────

def panel_titles(chat_id, uid):
    p = profile(uid)
    rows = []
    lines = [f"📛 لقب فعلی: {p.get('title') or '—'}\n"]
    for t in TITLES:
        cur = "✅" if p.get("title") == t[1] else ""
        lines.append(f"{t[1]} — {fmt_money(t[2])}💰 {cur}")
        if p.get("title") != t[1]:
            rows.append([(f"بخر {t[1]}", f"tit:{t[0]}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def title_buy(chat_id, uid, tid):
    t = next((x for x in TITLES if x[0] == tid), None)
    if not t:
        return "❌"
    if profile(uid)["money"] < t[2]:
        return f"💸 {fmt_money(t[2])} لازم است."
    change_money(uid, -t[2], "title", t[1])
    set_profile(uid, title=t[1])
    db.execute("UPDATE profiles SET reputation=MIN(100,reputation+5) WHERE user_id=?", (uid,))
    channel_news(f"📛 {profile(uid)['name']} لقب «{t[1]}» را خریداری کرد! احترام!")
    return f"📛 تبریک! لقب «{t[1]}» از تو شد (+۵ اعتبار) ✨"


# ───── [10] 🎓 تحصیل ─────

def panel_education(chat_id, uid):
    p = profile(uid)
    lvl = p.get("edu") or 0
    lines = [f"🎓 آکادمی شهر\n━━━━━━━━━━━\nمدرک فعلی: {fn(lvl)}/۳\n"]
    rows = []
    if lvl < len(DEGREES):
        nxt = DEGREES[lvl]
        lines.append(f"قدم بعدی: {nxt[1]} — {fmt_money(nxt[2])}💰 → +{fn(int(nxt[3]*100))}٪ حقوق دائم")
        rows.append([(f"ثبت‌نام {nxt[1]} ({fmt_money(nxt[2])})", "edu:go")])
    else:
        lines.append("🏆 بزرگ‌ترین مدرک را داری! +۱۵٪ حقوق")
    lines.append("هر مدرک سطح حقوقت را برای همیشه بالا می‌برد.")
    rows.append([("📚 دوره‌های مهارتی (کلاس تخصصی)", "crs:menu")])   # 🆕 v7
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def edu_go(chat_id, uid):
    p = profile(uid)
    lvl = p.get("edu") or 0
    if lvl >= len(DEGREES):
        return "🏆 همه مدارک را داری!"
    d = DEGREES[lvl]
    if p["money"] < d[2]:
        return f"💸 شهریه {fmt_money(d[2])} لازم است."
    change_money(uid, -d[2], "education", d[1])
    db.execute("UPDATE profiles SET edu=edu+1 WHERE user_id=?", (uid,))
    lines = gain_xp(uid, 100)
    log_action(uid, "degree", d[1])
    return (f"🎓 فارغ‌التحصیل شدی: {d[1]}!\n+{fn(int(d[3]*100))}٪ حقوق دائم | ⭐ +۱۰۰ XP"
            + ("\n" + "\n".join(lines) if lines else ""))


# ───── [11] 🏥 بیمه ─────

def insurance_buy(chat_id, uid):
    from datetime import timedelta
    p = profile(uid)
    if is_insured(uid):
        return "✅ همین حالا هم بیمه‌ای!"
    if p["money"] < INSURANCE_COST:
        return f"💸 حق بیمه روزانه {fmt_money(INSURANCE_COST)} است."
    change_money(uid, -INSURANCE_COST, "insurance", "بیمه روزانه")
    until = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")
    set_profile(uid, insured_until=until)
    return "🏥 بیمه شدی! ۲۴ ساعت: غارت‌ها/هک/جنگ‌ها از تو نصف کم می‌کنند. 🛡"


# ───── [12] 🚨 جنایت و زندان ─────

def crime_do(chat_id, uid):
    if is_jailed(uid):
        return f"🚔 تو در زندانی تا {is_jailed(uid)[5:16]}! وثیقه بده یا صبر کن."
    p = profile(uid)
    last = p.get("last_crime")
    if last and (datetime.now() - datetime.fromisoformat(last)).total_seconds() < CRIME_COOLDOWN:
        return f"⏳ پلیس سر گوشته! هر {fn(CRIME_COOLDOWN//60)} دقیقه یک جنایت."
    db.execute("UPDATE profiles SET last_crime=? WHERE user_id=?", (now_iso(), uid))
    # قربانی تصادفی میان کاربران اخیر با پول کافی
    targets = db.fetchall("""SELECT p.user_id, p.name, p.money FROM profiles p
                             JOIN users u ON u.user_id=p.user_id
                             WHERE p.user_id!=? AND u.is_banned=0 AND p.money>800
                             ORDER BY RANDOM() LIMIT 5""", (uid,))
    if not targets:
        return "🕳 هیچ‌کس چیزی برای دزدیدن ندارد!"
    targets = [x for x in targets if not guard_active(x["user_id"])]   # 🆕 v7: گارددارها محافظت‌شده‌اند
    if not targets:
        return "🕳 همه قربانیان محتمل امروز گارد استخدام کرده‌اند! فردا بیا 😂"
    t = dict(random.choice(targets))
    if random.random() < 0.35:  # گیر پلیس! 🚔
        from datetime import timedelta
        jail = (datetime.now() + timedelta(hours=JAIL_HOURS)).isoformat(timespec="seconds")
        set_profile(uid, jail_until=jail)
        db.execute("UPDATE profiles SET reputation=MAX(0,reputation-5) WHERE user_id=?", (uid,))
        log_action(uid, "crime_jailed", t["name"])
        return (f"🚔 دستگیر شدی! وسط جیب‌بری از {t['name']} پلیس از پشت گرفتت!\n"
                f"⛓ زندان: {fn(JAIL_HOURS)} ساعت | وثیقه: {fmt_money(BAIL_COST)}💰 (از پنل 🏙 شهر)")
    loot = int(t["money"] * random.uniform(0.02, 0.05))
    change_money(t["user_id"], -loot, "crime", f"جیب‌بری توسط {p['name']}")
    change_money(uid, loot, "crime", f"جیب‌بری از {t['name']}")
    db.execute("INSERT INTO crime_log(criminal,target,amount,created_at) VALUES(?,?,?,?)",   # 🆕 v6: پلیس می‌تواند تعقیب کند
               (uid, t["user_id"], loot, now_iso()))
    api.send_message(t["user_id"], f"🚨 جیبت زده شد! {fmt_money(loot)} تومان از کیفت رفت! 🏥 اگه بیمه بودی نصف کم می‌شد...")
    gain_xp(uid, 15)
    log_action(uid, "crime_win", f"{t['name']} {loot}")
    return f"🥷 جنایت موفق! از جیب {t['name']} مبلغ {fmt_money(loot)} تومان ربودی! 😈 (+۱۵ XP)"


def crime_bail(chat_id, uid):
    if not is_jailed(uid):
        return "✅ زندانی نیستی."
    p = profile(uid)
    if p["money"] < BAIL_COST:
        return f"💸 وثیقه {fmt_money(BAIL_COST)} است."
    change_money(uid, -BAIL_COST, "crime", "وثیقه آزادی")
    set_profile(uid, jail_until=None)
    return "🔓 با وثیقه آزاد شدی! دیگر جیب‌بری نکن (یا دقیق‌تر کن 😎)"


# ───── [13] ✈️ سفر به شهرها ─────

def panel_travel(chat_id, uid):
    p = profile(uid)
    rows = []
    lines = [f"✈️ سفر — شهری که در آن زندگی می‌کنی بونس می‌دهد!\nشهر فعلی: {p['city']}\n"]
    for i, (city, bonus) in enumerate(TRAVEL_CITIES):
        cur = "📍" if p["city"] == city else ""
        lines.append(f"{city}: {bonus} {cur}")
        if p["city"] != city:
            rows.append([(f"✈️ برو به {city} ({fmt_money(TRAVEL_COST)}💰 +۱۰⚡)", f"trv:{i}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def travel_go(chat_id, uid, idx):
    city, bonus = TRAVEL_CITIES[int(idx)]
    p = profile(uid)
    if p["money"] < TRAVEL_COST:
        return f"💸 بلیت {fmt_money(TRAVEL_COST)} تومانه."
    if p["energy"] < 10:
        return "🔋 خسته‌ای."
    change_money(uid, -TRAVEL_COST, "travel", f"سفر به {city}")
    db.execute("UPDATE profiles SET energy=MAX(0,energy-10), city=? WHERE user_id=?", (city, uid))
    log_action(uid, "travel", city)
    return f"✈️ به {city} رسیدی! از این پس: {bonus} 🏙"


# ───── [14] 📰 روزنامه شهر ─────

def panel_news(chat_id, uid):
    ev = world_event()
    lines = ["📰 روزنامه «صبح شهر»\n━━━━━━━━━━━\n"]
    lines.append(f"🌍 رویداد: {ev['title'] if ev else 'روز آرامی پیش‌رو است'}")
    mk = db.fetchall("SELECT * FROM markets ORDER BY ABS(CAST(price AS REAL)/MAX(prev_price,1)-1) DESC LIMIT 1")
    if mk:
        mv = mk[0]
        lines.append(f"📊 بازار: فعال‌ترین — {mv['name']} ({fmt_money(mv['price'])})")
    for w in db.fetchall("SELECT result FROM war_log ORDER BY id DESC LIMIT 3"):
        lines.append(f"⚔️ {w['result']}")
    for lg in db.fetchall("SELECT details FROM logs WHERE action='married' ORDER BY id DESC LIMIT 1"):
        lines.append("💒 یک عروسی در شهر رخ داده!")
    bt = db.fetchone("SELECT target, SUM(amount) s FROM bounties GROUP BY target ORDER BY s DESC LIMIT 1")
    if bt:
        tn = (profile(bt["target"]) or {}).get("name", "?")
        lines.append(f"🎯 بزرگ‌ترین جایزه‌گذاری: {fmt_money(bt['s'])}💰 روی سر {tn}!")
    top = db.fetchone("SELECT name, money FROM profiles ORDER BY money DESC LIMIT 1")
    if top:
        lines.append(f"👑 سلطان فعلی شهر: {top['name']}")
    deal = deal_item_id()   # 🆕 v7
    if deal:
        di = db.fetchone("SELECT emoji, name FROM items WHERE id=?", (deal,))
        da = get_setting("deal_asset")
        an = db.fetchone("SELECT name FROM markets WHERE symbol=?", (da,))
        if di:
            lines.append(f"🛍 معامله طلایی امروز: {di['emoji']} {di['name']} با ۲۵٪ تخفیف!")
        if an:
            lines.append(f"📈 شایعه بازار: امروز {an['name']} پامپ ۸٪ شد!")
    if city_tax_rate() > 0:   # 🆕 v7
        lines.append(f"🏛 مالیات شهری شهردار: {fn(city_tax_rate()*100)}٪ | خزانه: {fmt_money(treasury_amount())}💰")
    api.send_message(chat_id, "\n".join(lines))


# ───── [15] 🔥 جایزه روزانه (استریک) ─────

def streak_claim(chat_id, uid):
    p = profile(uid)
    if p.get("last_streak") == today():
        return f"🔥 امروز گرفتی! استریک تو: {fn(p.get('streak') or 0)} روز 🔥 — فردا با جایزه بزرگ‌تر برگرد!"
    from datetime import timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    streak = (p.get("streak") or 0) + 1 if p.get("last_streak") == yesterday else 1
    reward = 100 * streak
    change_money(uid, reward, "streak", f"جایزه روزانه روز {streak}")
    bonus_txt = ""
    if streak % 7 == 0:
        add_gems(uid, 5)
        bonus_txt = "\n💎 هفته کامل! +۵ سکه طلا بونس!"
        channel_news(f"🔥 استریک {profile(uid)['name']} به {fn(streak)} روز رسید!")
    db.execute("UPDATE profiles SET streak=?, last_streak=? WHERE user_id=?", (streak, today(), uid))
    mission_progress(uid, "life")
    return (f"🔥 جایزه روزانه (روز {fn(streak)} از زنجیره): +{fmt_money(reward)} تومان!{bonus_txt}\n"
            f"فردا بیای بزرگ‌ترش می‌شه 📈")


# ───── [16] 🏅 دستاوردها ─────

def panel_achievements(chat_id, uid):
    p = profile(uid)
    new = []
    for key, name, cond, reward in ACHIEVEMENTS:
        if db.fetchone("SELECT 1 FROM achievements WHERE user_id=? AND akey=?", (uid, key)):
            continue
        try:
            if cond(uid, p):
                db.execute("INSERT INTO achievements(user_id,akey,granted_at) VALUES(?,?,?)",
                           (uid, key, now_iso()))
                lines = apply_effects(uid, {k: v for k, v in reward.items()}, f"دستاورد {name}")
                new.append(f"🏅 {name}\n   {'، '.join(lines)}")
        except Exception:
            pass
    got = db.fetchall("SELECT akey FROM achievements WHERE user_id=?", (uid,))
    got_names = {a[1] for a in ACHIEVEMENTS if any(g["akey"] == a[0] for g in got)}
    txt = "🏅 دفترچه افتخار\n━━━━━━━━━━━\n"
    if new:
        txt += "🎉 تازه برشکافتی:\n" + "\n\n".join(new) + "\n\n"
    txt += f"✅ انجام‌شده: {fn(len(got))}/{fn(len(ACHIEVEMENTS))}\n"
    txt += "، ".join(got_names) if got_names else "— هنوز هیچی!"
    api.send_message(chat_id, txt)


# ───── [17] 🏭 کسب‌وکارهای درآمد غیرفعال ─────

def panel_business(chat_id, uid):
    owned = {r["biz_id"] for r in db.fetchall("SELECT biz_id FROM businesses WHERE user_id=?", (uid,))}
    income = sum(b[3] for b in BUSINESSES if b[0] in owned)
    lines = [f"🏭 کارخانه‌ها و کسب‌وکارها\n━━━━━━━━━━━\nدرآمد فعلی تو: {fmt_money(income)}💰 هر ۶ ساعت (خودکار)\n"]
    rows = []
    for b in BUSINESSES:
        mark = "✅ داری" if b[0] in owned else f"💵 {fmt_money(b[2])}"
        lines.append(f"{b[1]} — درآمد {fmt_money(b[3])}/تیک ({mark})")
        if b[0] not in owned:
            rows.append([(f"راه‌اندازی {b[1]}", f"biz:{b[0]}")])
    lines.append("\n⚙️ درآمد با هر بازدیدت از امپراتوری جمع می‌شود")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def business_buy(chat_id, uid, biz_id):
    b = next((x for x in BUSINESSES if x[0] == biz_id), None)
    if not b:
        return "❌"
    if db.fetchone("SELECT 1 FROM businesses WHERE user_id=? AND biz_id=?", (uid, biz_id)):
        return "⚠️ این کسب‌وکار را داری!"
    p = profile(uid)
    if p["money"] < b[2]:
        return f"💸 {fmt_money(b[2])} لازم است."
    change_money(uid, -b[2], "business", f"راه‌اندازی {b[1]}")
    db.execute("INSERT INTO businesses(user_id,biz_id) VALUES(?,?)", (uid, biz_id))
    log_action(uid, "biz_buy", biz_id)
    return f"🏭 {b[1]} راه افتاد! هر ۶ ساعت {fmt_money(b[3])} تومان درآمد! 💵"


def business_tick(uid):
    """درآمد کسب‌وکارها — همراه تیک امپراتوری"""
    r = ensure_resources(uid)
    if not r.get("biz_tick"):
        db.execute("UPDATE resources SET biz_tick=? WHERE user_id=?", (now_iso(), uid))
        return
    elapsed = (datetime.now() - datetime.fromisoformat(r["biz_tick"])).total_seconds()
    ticks = min(int(elapsed // TICK_SEC), 16)
    if ticks <= 0:
        return
    owned = {row[0] for row in db.fetchall("SELECT biz_id FROM businesses WHERE user_id=?", (uid,))}
    income = sum(b[3] for b in BUSINESSES if b[0] in owned) * ticks
    db.execute("UPDATE resources SET biz_tick=? WHERE user_id=?", (now_iso(), uid))
    if income > 0:
        change_money(uid, income, "business", f"درآمد {fn(ticks)} تیک کسب‌وکار")
        api.send_message(uid, f"🏭 کسب‌وکارهایت در غیابت کار کردند: +{fmt_money(income)} تومان! 💵")


# ───── [18] 🎯 جایزه‌گذاری (Bounty) ─────

def panel_bounty(chat_id, uid):
    lines = ["🎯 تابلوی جایزه‌گذاری‌ها\n━━━━━━━━━━━\nهرکس آن‌ها را در جنگ شکست دهد، جایزه را می‌گیرد!\n"]
    rows = [[("➕ گذاشتن جایزه روی کسی", "bty:tg")]]
    for b in db.fetchall("""SELECT target, SUM(amount) s FROM bounties GROUP BY target
                            ORDER BY s DESC LIMIT 8"""):
        n = (profile(b["target"]) or {}).get("name", "?")
        lines.append(f"🎯 {n}: {fmt_money(b['s'])}💰")
    if len(lines) <= 3:
        lines.append("هنوز جایزه‌ای نیست.")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def bounty_targets(chat_id, uid):
    rows = []
    for t in db.fetchall("""SELECT p.user_id, p.name FROM profiles p
                            JOIN users u ON u.user_id=p.user_id
                            WHERE p.user_id!=? AND u.is_banned=0
                            ORDER BY u.last_seen DESC LIMIT 8""", (uid,)):
        rows.append([(f"🎯 روی سر {t['name']}", f"bty:t:{t['user_id']}")])
    api.send_message(chat_id, "روی سر کی جایزه بگذاری؟ 😈", inline_keyboard(rows))


def bounty_amount(chat_id, uid, target_id):
    t = profile(target_id)
    if not t:
        api.send_message(chat_id, "❌"); return
    rows = [[(f"{fmt_money(a)} 💰", f"bty:{target_id}:{a}") for a in (500, 2000, 5000)]]
    api.send_message(chat_id, f"چقدر روی سر {t['name']} می‌گذاری؟", inline_keyboard(rows))


def bounty_put(chat_id, uid, target_id, amount):
    t = profile(target_id)
    amount = int(amount)
    p = profile(uid)
    if not t:
        return "❌"
    if p["money"] < amount:
        return "💸 پولت کم است."
    change_money(uid, -amount, "bounty", f"جایزه روی سر {t['name']}")
    db.execute("INSERT INTO bounties(target,amount,setter,created_at) VALUES(?,?,?,?)",
               (target_id, amount, uid, now_iso()))
    channel_news(f"🎯 {p['name']} جایزه‌ای {fmt_money(amount)} تومانی روی سر {t['name']} گذاشت! او را در جنگ شکست بده!")
    log_action(uid, "bounty_put", f"{target_id} {amount}")
    return f"🎯 جایزه {fmt_money(amount)} روی سر {t['name']} ثبت شد!"


def bounty_collect(uid, target_id):
    """در برد جنگی — جایزه‌های روی سر حریف را جمع کن"""
    rows = db.fetchall("SELECT * FROM bounties WHERE target=?", (target_id,))
    if not rows:
        return 0
    total = sum(r["amount"] for r in rows)
    db.execute("DELETE FROM bounties WHERE target=?", (target_id,))
    change_money(uid, total, "bounty", f"جمع جایزه‌های روی سر {(profile(target_id) or {}).get('name','')}")
    channel_news(f"💰 قاطع! {profile(uid)['name']} جایزه‌ی {fmt_money(total)} تومانی روی سر حریف را گرفت!")
    return total


# ─── [19] ⭐ بازتولد (Prestige) + [20] 🔗 رفرل ───

def rebirth_do(chat_id, uid):
    p = profile(uid)
    if p["level"] < 10:
        return f"⭐ برای بازتولد باید لول ۱۰+ باشی (الان: {fn(p['level'])})"
    keep = {k: p.get(k) for k in ("gems", "vip", "title")}
    db.execute("""UPDATE profiles SET money=1000, level=1, xp=0, energy=100, health=100, happiness=80,
                  job_id=NULL, job_level=1, home='پناهگاه', skills_json='{}', rebirth=rebirth+1
                  WHERE user_id=?""", (uid,))
    db.execute("UPDATE resources SET soldiers=2, wounded=0 WHERE user_id=?", (uid,))
    channel_news(f"⭐ معجزه بازتولد!\n{profile(uid)['name']} زندگی را از نو شروع کرد و قدرت ابدی گرفت! (بازتولد {fn(p.get('rebirth',0)+1)})")
    log_action(uid, "rebirth", str(p.get("rebirth", 0) + 1))
    return (f"✨ بازتولد شدی! زندگی از نو آغاز شد — اما این‌بار قوی‌تر!\n"
            f"💎 و 👑 و لقبت حفظ شد | +۵٪ قدرت جنگ و حقوق دائم (به ازای هر بازتولد)\n"
            f"بازتولد شماره: {fn(p.get('rebirth', 0) + 1)}")


def panel_referral(chat_id, uid):
    p = profile(uid)
    api.send_message(chat_id,
                     f"🔗 دعوت دوستان\n━━━━━━━━━━━\n"
                     f"این را برای دوستانت بفرست\n(اسم ربات را جای @YourBot بگذار):\n\n"
                     f"https://bale.ai/{'bot'}?start=ref_{uid}\n\n"
                     f"یا بهشون بگو وقتی ربات را استارت کردن بنویسن: /start ref_{uid}\n\n"
                     f"🎁 با ساخت کاراکتر هر نفر: +۱٬۵۰۰💰 و +۵💎 برای تو!\n"
                     f"👥 تا الان دعوت کردی: {fn(p.get('ref_count') or 0)} نفر")


def referral_grant(referrer_id, new_uid):
    change_money(referrer_id, 1500, "ref", f"جایزه دعوت #{new_uid}")
    add_gems(referrer_id, 5)
    db.execute("UPDATE profiles SET ref_count=COALESCE(ref_count,0)+1 WHERE user_id=?", (referrer_id,))
    api.send_message(referrer_id,
                     f"🔗 یکی از دوستات با لینک تو اومد و کاراکتر ساخت! 🎉\n+۱٬۵۰۰💰 و +۵💎 گرفتی!")
    log_action(referrer_id, "referral", str(new_uid))


# ─── پنل‌های جدید منو ───

def panel_fun(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    # 🆕 v6/v7 — نسخه سازگار با قوانین (بدون شرط‌بندی)
    rows = [[("🎟 قرعه‌کشی رایگان", "fun:lot"), ("🎡 شهربازی مهارتی", "fun:arc")],
            [("🧗 برج قهرمانان", "fun:twr"), ("🗺️ ماجراجویی (-۲۰⚡)", "xpl:go")],
            [("🧩 کوییز روزانه", "qiz:play"), ("🔮 طالع امروز", "fun:fort")],
            [("🎁 شکار گنج", "trs:view"), ("💪 باشگاه (+۱۵٪ جنگ)", "gym:go")],
            [("🎯 جایزه‌گذاری‌ها", "fun:bty")]]
    p = profile(uid)
    floor = p.get("tower_floor") or 1
    chest = treasure_active()
    api.send_message(chat_id,
                     f"🎡 مرکز سرگرمی شهر\n━━━━━━━━━━━\n"
                     f"🌙 همه بازی‌ها فرهنگی و بدون شرط‌بندی هستند\n"
                     f"🧗 طبقه برج تو: {fn(floor)} | 🔮 طالع: {'کشیدی' if fortune_of(uid) else 'نکشیدی'}\n"
                     f"🏛 خزانه شهر: {fmt_money(treasury_amount())}💰 | 🎁 گنج: {'فعال! بدو 🏃' if chest else 'بزودی...'}\n"
                     f"💪 باف باشگاه: {('فعال تا ' + gym_active(uid)[11:16]) if gym_active(uid) else '—'}",
                     inline_keyboard(rows))


def panel_city(chat_id, uid):
    if not guard_character(chat_id, uid):
        return
    jail = is_jailed(uid)
    rows = [[("✈️ سفر بین شهرها", "cty:trv"), ("🎓 تحصیل", "cty:edu")],
            [("🏥 بیمه روزانه (۲۰۰💰)", "cty:ins"), ("📰 روزنامه شهر", "cty:news")],
            [("🗳 شهردار هفته (رأی‌گیری!)", "ele:menu"), ("🚔 تابلوی زندان", "jli:board")],
            [("🛡 استخدام گارد روزانه", "grd:hire")],
            [("🚨 جنایت (ریسک زندان!)", "cty:crim")]]
    if jail:
        rows.append([(f"🔓 وثیقه آزادی ({fmt_money(BAIL_COST)}💰)", "cty:bail")])
    ins = "✅ داری" if is_insured(uid) else "❌ نداری"
    api.send_message(chat_id,
                     f"🏙 اداره‌ی شهر\n━━━━━━━━━━━\n"
                     f"🏥 بیمه: {ins} | 🎓 مدرک: {fn(profile(uid).get('edu') or 0)}/۳\n"
                     f"{'⛓ در زندانی تا ' + jail[5:16] if jail else '🕊 آزادی!'}",
                     inline_keyboard(rows))

# ══════════════════════════════════════════════════════════════════
# [8.8] 🆕 v6: شهربازی مهارتی، کوییز روزانه، کاوش،
#       گنج، باشگاه، مزرعه، گاوصندوق، شهردار، پلیس، ماموریت هفتگی، خزانه شهر،
#       مسابقه پت، صرافی، بازار آگهی، ترکیب آیتم، اجاره، تولد
# ══════════════════════════════════════════════════════════════════

def week_key() -> str:
    iso = datetime.now().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def week_start() -> datetime:
    from datetime import timedelta
    d = datetime.now()
    return (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def parse_num(s: str) -> str:
    """ورودی کاربر را به ارقام لاتین تبدیل می‌کند (ورود با کیبورد فارسی هم اوکی)"""
    return (s or "").translate(EN_DIGITS).replace(",", "").replace("٬", "").strip()


def logs_since(uid, action, since_dt) -> int:
    return db.fetchone("SELECT COUNT(*) c FROM logs WHERE actor=? AND action=? AND created_at>=?",
                       (uid, action, since_dt.isoformat(timespec="seconds")))["c"]


def today_logs(uid, action) -> int:
    return db.fetchone("SELECT COUNT(*) c FROM logs WHERE actor=? AND action=? AND created_at LIKE ?",
                       (uid, action, today() + "%"))["c"]


# ───── 🧩 کوییز روزانه ─────

def quiz_state(uid):
    row = db.fetchone("SELECT * FROM quiz WHERE user_id=?", (uid,))
    if not row or row["day"] != today():
        qs = random.sample(range(len(QUIZ_BANK)), min(QUIZ_DAILY, len(QUIZ_BANK)))
        db.execute("INSERT OR REPLACE INTO quiz(user_id,day,qidx,score) VALUES(?,?,?,0)",
                   (uid, today(), jd({"qs": qs, "i": 0})))
        return {"qs": qs, "i": 0}, 0
    return jl(row["qidx"], {"qs": [], "i": 0}), row["score"]


def quiz_next(chat_id, uid):
    st, score = quiz_state(uid)
    i = st["i"]
    if i >= len(st["qs"]):
        api.send_message(chat_id,
                         f"🧩 کوییز امروزت تمام شد! ✅ {fn(score)}/{fn(len(st['qs']))} درست\n"
                         f"💰 جایزه‌ها واریز شد. فردا سری جدید میاد!")
        return
    q, opts, _ = QUIZ_BANK[st["qs"][i]]
    order = list(range(len(opts)))
    random.shuffle(order)
    st["order"] = order
    db.execute("UPDATE quiz SET qidx=? WHERE user_id=?", (jd(st), uid))
    rows = [[(opts[o], f"qiz:a:{k}")] for k, o in enumerate(order)]
    api.send_message(chat_id, f"🧩 سؤال {fn(i+1)} از {fn(len(st['qs']))}:\n\n❓ {q}", inline_keyboard(rows))


def quiz_answer(chat_id, uid, k):
    row = db.fetchone("SELECT * FROM quiz WHERE user_id=?", (uid,))
    if not row or row["day"] != today():
        quiz_next(chat_id, uid)
        return None
    st = jl(row["qidx"], {"qs": [], "i": 0})
    i = st["i"]
    if i >= len(st["qs"]):
        return "🧩 کوییز امروز تمام شده!"
    q, opts, ans = QUIZ_BANK[st["qs"][i]]
    order = st.get("order", list(range(len(opts))))
    picked = order[int(k)] if int(k) < len(order) else -1
    correct = picked == ans
    score = row["score"] + (1 if correct else 0)
    st["i"] = i + 1
    st.pop("order", None)
    db.execute("UPDATE quiz SET qidx=?, score=? WHERE user_id=?", (jd(st), score, uid))
    if correct:
        change_money(uid, QUIZ_REWARD, "quiz", "جواب درست کوییز")
        gain_xp(uid, 10)
        head = f"✅ آفرین! درست بود. +{fmt_money(QUIZ_REWARD)}💰 +۱۰⭐"
    else:
        gain_xp(uid, 3)
        head = f"❌ غلط بود! جواب: «{opts[ans]}»"
    if st["i"] >= len(st["qs"]):
        bonus = ""
        if score == len(st["qs"]):
            change_money(uid, QUIZ_ALL_BONUS, "quiz", "بونس فول‌مارک کوییز")
            bonus = f"\n🏆 فول‌مارک! بونس +{fmt_money(QUIZ_ALL_BONUS)}💰"
        return f"{head}\n\n🏁 کوییز امروز تمام شد: {fn(score)}/{fn(len(st['qs']))} درست!{bonus}"
    api.send_message(chat_id, f"{head}\nسؤال بعدی میاد... ⏳")
    quiz_next(chat_id, uid)
    return None


# ───── 🗺️ ماجراجویی (کاوش) ─────

def explore_go(chat_id, uid):
    if is_jailed(uid):
        return f"⛓ در زندان که سفر نمی‌شود! (تا {is_jailed(uid)[5:16]})"
    p = profile(uid)
    if p["energy"] < EXPLORE_ENERGY:
        return f"🔋 کاوش {fn(EXPLORE_ENERGY)}⚡ انرژی می‌خواهد!"
    db.execute("UPDATE profiles SET energy=MAX(0,energy-?) WHERE user_id=?", (EXPLORE_ENERGY, uid))
    gain_xp(uid, 12)
    log_action(uid, "explore", "")
    roll = random.random()
    if roll < 0.30:  # 💰 گنج نقدی
        loot = random.randint(300, 1200)
        change_money(uid, loot, "explore", "گنج کاوش")
        return f"🗺️ توی خرابه‌ها کندوکاو کردی و یه صندوقچه پیدا کردی!\n💰 +{fmt_money(loot)} تومان! (+۱۲⭐)"
    if roll < 0.40:  # 💎 سکه
        g = random.randint(2, 5)
        add_gems(uid, g)
        if g >= 4:
            channel_news(f"🗺️ {profile(uid)['name']} موقع کاوش به گنج {fn(g)}💎 سکه‌ای رسید!")
        return f"🗺️ زیر خاک‌ها جعبه‌ای درخشان بود... 💎 +{fn(g)} سکه طلا! (+۱۲⭐)"
    if roll < 0.55:  # 📦 منابع امپراتوری
        ensure_resources(uid)
        col, emo = pick([("food", "🌾"), ("iron", "⚒️"), ("medicine", "💊")])
        amt = random.randint(5, 15)
        db.execute(f"UPDATE resources SET {col}={col}+? WHERE user_id=?", (amt, uid))
        return f"🗺️ به یه انبار متروکه رسیدی! 📦 +{fn(amt)} {emo} به امپراتوریت اضافه شد. (+۱۲⭐)"
    if roll < 0.70:  # ⚔️ برخورد
        if battle_power(uid) * random.uniform(0.8, 1.3) > random.uniform(60, 180):
            loot = random.randint(400, 900)
            change_money(uid, loot, "explore", "غارت راهزن")
            return f"🗺️ وسط راه یه راهزن جلوت را گرفت — ولی زمینش زدی! 😤\n💰 +{fmt_money(loot)} غنیمت! (+۱۲⭐)"
        db.execute("UPDATE profiles SET health=MAX(0,health-10) WHERE user_id=?", (uid,))
        return "🗺️ وسط راه راهزن‌ها محاصره‌ات کردند و فرار کردی... ❤️ -۱۰ سلامتی (+۱۲⭐)"
    if roll < 0.85:  # 🕳 تله
        db.execute("UPDATE profiles SET health=MAX(0,health-12) WHERE user_id=?", (uid,))
        return "🗺️ داخل یه غار قدیمی به تله خوردی! 🤕 ❤️ -۱۲ سلامتی — بیمارستان یادت نره! (+۱۲⭐)"
    # 🌀 اتفاق عجیب
    return pick([
        "🗺️ یه پیره‌مرد بهت نقشه گنجی داد... که شش‌راه به بن‌بست رسید! 😂 (فقط +۱۲⭐)",
        "🗺️ ساعت‌ها گشتی و فقط یه گربه راهزن پیدا کردی که نگاهت کرد و رفت. 🐈 (+۱۲⭐)",
        "🗺️ بارون گرفت و برگشتی خانه — ولی حداقل هوای خوبی خوردی. 🌧️ (+۱۲⭐)",
        "🗺️ ته دره یه درخت پول پیدا کردی... خواب بود! بیدار شدی. 😴 (+۱۲⭐)",
    ])


# ───── 🎁 شکار گنج (سراسری؛ اولین نفر برنده) ─────

def ensure_treasure():
    """اسپاون تنبل صندوق گنج هر ~۳ ساعت"""
    cur = get_setting("treasure", "")
    if cur:
        return
    nxt = get_setting("treasure_next", "")
    if nxt:
        try:
            if datetime.fromisoformat(nxt) > datetime.now():
                return
        except Exception:
            pass
    prize = random.randint(3000, 8000)
    gems = random.randint(0, 4)
    set_setting("treasure", jd({"prize": prize, "gems": gems, "since": now_iso()}))
    log_action(0, "treasure_spawn", f"{prize}+{gems}g")


def treasure_active():
    return jl(get_setting("treasure", ""), None)


def panel_treasure(chat_id, uid):
    ensure_treasure()
    t = treasure_active()
    if t:
        rows = [[("🏃 آره! شکارش می‌کنم!", "trs:claim")]]
        api.send_message(chat_id,
                         f"🎁 یه صندوق گنج توی شهر پنهان شده!\n━━━━━━━━━━━\n"
                         f"داخلش حدود {fmt_money(t['prize'])}💰" + (f" و {fn(t['gems'])}💎" if t.get("gems") else "") +
                         "\nاولین نفری که بزند «شکار» برنده است! 😱", inline_keyboard(rows))
    else:
        nxt = get_setting("treasure_next", "")
        left = ""
        if nxt:
            try:
                mins = max(0, int((datetime.fromisoformat(nxt) - datetime.now()).total_seconds() // 60))
                left = f"\n⏳ صندوق بعدی حدود {fn(mins)} دقیقه دیگر می‌افتد!"
            except Exception:
                pass
        api.send_message(chat_id, "🎁 فعلاً گنج فعالی نیست!" + left + "\nهر چند ساعت یه صندوق می‌افتد — چشم‌وگوش هواس!")


def treasure_claim(chat_id, uid):
    ensure_treasure()
    t = treasure_active()
    if not t:
        return "😅 یارو زودتر از تو زدش! صبر کن صندوق بعدی بیاد..."
    set_setting("treasure", "")
    from datetime import timedelta
    set_setting("treasure_next", (datetime.now() + timedelta(seconds=TREASURE_INTERVAL)).isoformat(timespec="seconds"))
    prize = int(t["prize"])
    treasury_spend(prize)          # 🏛 گنج از خزانه شهر پرداخت می‌شود (فرهنگی)
    change_money(uid, prize, "treasure", "شکار گنج")
    if t.get("gems"):
        add_gems(uid, int(t["gems"]))
    nm = profile(uid)["name"]
    gain_xp(uid, 30)
    log_action(uid, "treasure_win", str(t["prize"]))
    channel_news(f"🎁 گنج پیدا شد!\n{nm} صندوق {fmt_money(t['prize'])} تومانی شهر را شکار کرد! 🏃💨\nصندوق بعدی چند ساعت دیگر می‌افتد...")
    return (f"🎉🎁 اولین نفر بودی! صندوق گنج مال تو:\n💰 +{fmt_money(t['prize'])} تومان" +
            (f" | 💎 +{fn(t['gems'])}" if t.get("gems") else "") + " | ⭐ +۳۰ XP")


# ───── 💪 باشگاه (باف موقت جنگ) ─────

def gym_go(chat_id, uid):
    cur = gym_active(uid)
    if cur:
        return f"💪 باف باشگاهت هنوز فعاله (تا {cur[11:16]})! برو جنگ و برگرد. 😎"
    p = profile(uid)
    if p["money"] < GYM_COST:
        return f"💸 باشگاه {fmt_money(GYM_COST)}💰 هزینه دارد."
    if p["energy"] < 10:
        return "🔋 ۱۰⚡ انرژی لازم است برای تمرین!"
    change_money(uid, -GYM_COST, "gym", "ورزش باشگاه")
    db.execute("UPDATE profiles SET energy=MAX(0,energy-10) WHERE user_id=?", (uid,))
    from datetime import timedelta
    until = (datetime.now() + timedelta(hours=GYM_HOURS)).isoformat(timespec="seconds")
    set_profile(uid, gym_until=until)
    return (f"💪 تمرین سنگین تمام شد! برای {fn(GYM_HOURS)} ساعت آینده:\n"
            f"⚔️ قدرت جنگ +۱۵٪ (تا {until[11:16]})\nبرو جنگ، دوئل، برج — بترکون! 🔥")


# ───── 🌻 مزرعه ─────

def panel_farm(chat_id, uid):
    ensure_resources(uid)
    rows = []
    lines = ["🌻 مزرعه تو\n━━━━━━━━━━━\nبذر بکار، چند ساعت بعد محصول برداشت کن — مستقیم به انبار امپراتوری! 🌾\n"]
    for slot in range(1, FARM_SLOTS + 1):
        row = db.fetchone("SELECT * FROM farm WHERE user_id=? AND slot=?", (uid, slot))
        if not row:
            lines.append(f"🕳 زمین {fn(slot)}: خالی — آماده کشت")
            rows.append([(f"🌱 کاشت در زمین {fn(slot)}", f"far:pl:{slot}")])
        else:
            crop = next((c for c in FARM_CROPS if c[0] == row["crop"]), None)
            try:
                ready = datetime.fromisoformat(row["ready_at"])
                left = (ready - datetime.now()).total_seconds()
            except Exception:
                left = 0
            if left <= 0:
                prod = "، ".join(f"{fn(v)} {'🌾' if k=='food' else '💊' if k=='medicine' else '⚒️'}" for k, v in crop[3].items())
                lines.append(f"✅ زمین {fn(slot)}: {crop[1]} رسیده! ({prod})")
                rows.append([(f"🧺 برداشت زمین {fn(slot)} 🎉", f"far:hv:{slot}")])
            else:
                lines.append(f"🌱 زمین {fn(slot)}: {crop[1]} — {fn(int(left//60)+1)} دقیقه مونده")
    r = ensure_resources(uid)
    lines.append(f"\n📦 انبار: 🌾 {fn(round(r['food'],1))} | ⚒️ {fn(round(r['iron'],1))} | 💊 {fn(int(r['medicine']))}")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def farm_plant_menu(chat_id, uid, slot):
    rows = [[(f"{c[1]} — {fmt_money(c[2])}💰 / {fn(c[4])}ساعت", f"far:bl:{slot}:{c[0]}")] for c in FARM_CROPS]
    rows.append([("↩️ برگشت", "far:menu")])
    api.send_message(chat_id, "🌱 کدام محصول را بکاری؟", inline_keyboard(rows))


def farm_plant(chat_id, uid, slot, crop_id):
    slot = int(slot)
    crop = next((c for c in FARM_CROPS if c[0] == crop_id), None)
    if not crop:
        return "❌"
    if db.fetchone("SELECT 1 FROM farm WHERE user_id=? AND slot=?", (uid, slot)):
        return "🌱 این زمین اشغال است!"
    p = profile(uid)
    if p["money"] < crop[2]:
        return f"💸 بذر {crop[1]} به قیمت {fmt_money(crop[2])}💰 است."
    change_money(uid, -crop[2], "farm", f"بذر {crop[1]}")
    from datetime import timedelta
    ready = (datetime.now() + timedelta(hours=crop[4])).isoformat(timespec="seconds")
    db.execute("INSERT INTO farm(user_id,slot,crop,ready_at) VALUES(?,?,?,?)", (uid, slot, crop_id, ready))
    return f"🌱 {crop[1]} کاشته شد! بعد از {fn(crop[4])} ساعت برگرد و برداشت کن. 🌧️"


def farm_harvest(chat_id, uid, slot):
    slot = int(slot)
    row = db.fetchone("SELECT * FROM farm WHERE user_id=? AND slot=?", (uid, slot))
    if not row:
        return "🕳 زمین خالی است!"
    try:
        if datetime.fromisoformat(row["ready_at"]) > datetime.now():
            return "🌱 هنوز نرسیده! کمی صبر..."
    except Exception:
        pass
    crop = next((c for c in FARM_CROPS if c[0] == row["crop"]), None)
    ensure_resources(uid)
    gains = []
    for k, v in crop[3].items():
        db.execute(f"UPDATE resources SET {k}={k}+? WHERE user_id=?", (v, uid))
        gains.append(f"+{fn(v)} {'🌾' if k=='food' else '💊' if k=='medicine' else '⚒️'}")
    db.execute("DELETE FROM farm WHERE user_id=? AND slot=?", (uid, slot))
    gain_xp(uid, 15)
    log_action(uid, "farm_harvest", crop[0])
    return f"🧺 برداشت {crop[1]}! {('، '.join(gains))} به انبار امپراتوریت رفت! 🎉 (+۱۵⭐)"


# ───── 🧰 گاوصندوق منابع ─────

def vault_of(uid):
    db.execute("INSERT OR IGNORE INTO rvault(user_id) VALUES(?)", (uid,))
    return db.fetchone("SELECT * FROM rvault WHERE user_id=?", (uid,))


def panel_vault(chat_id, uid):
    ensure_resources(uid)
    v = vault_of(uid)
    cap = v["lvl"] * VAULT_CAP_PER_LVL
    rows = [
        [("➕ ۵ 🌾", "vlt:d:food"), ("➖ ۵ 🌾", "vlt:w:food")],
        [("➕ ۵ ⚒️", "vlt:d:iron"), ("➖ ۵ ⚒️", "vlt:w:iron")],
        [("➕ ۲ 💊", "vlt:d:medicine"), ("➖ ۲ 💊", "vlt:w:medicine")],
        [(f"🔺 ارتقا گاوصندوق → سطح {fn(v['lvl']+1)} ({fmt_money(v['lvl']*1500)}💰 + {fn(v['lvl']*5)}⚒️)", "vlt:up")],
    ]
    api.send_message(chat_id,
                     f"🧰 گاوصندوق منابع — سطح {fn(v['lvl'])}\n━━━━━━━━━━━\n"
                     f"منابع اینجا از هک، غارت ارتش و جیب‌بری در امان‌اند! 🛡\n\n"
                     f"🌾 غذا: {fn(v['food'])}/{fn(cap)}  ⚒️ آهن: {fn(v['iron'])}/{fn(cap)}  💊 دارو: {fn(v['medicine'])}/{fn(cap)}\n"
                     f"(ظرفیت هر منبع با هر ارتقا +{fn(VAULT_CAP_PER_LVL)} می‌شود)",
                     inline_keyboard(rows))


def vault_move(chat_id, uid, mode, kind):
    v = vault_of(uid)
    r = ensure_resources(uid)
    amt = 2 if kind == "medicine" else 5
    cap = v["lvl"] * VAULT_CAP_PER_LVL
    names = {"food": "🌾 غذا", "iron": "⚒️ آهن", "medicine": "💊 دارو"}
    if mode == "d":
        amt = min(amt, int(r[kind]))
        if amt <= 0:
            return f"📦 {names[kind]} کافی توی انبار نداری!"
        if v[kind] + amt > cap:
            return f"🧰 گاوصندوق پر است! (ظرفیت: {fn(cap)}) ارتقاش بده."
        db.execute(f"UPDATE rvault SET {kind}={kind}+? WHERE user_id=?", (amt, uid))
        db.execute(f"UPDATE resources SET {kind}={kind}-? WHERE user_id=?", (amt, uid))
        return f"🔒 {fn(amt)} {names[kind]} به گاوصندوق رفت — در امان!"
    amt = min(amt, v[kind])
    if amt <= 0:
        return "🧰 چیزی توی گاوصندوق نیست!"
    db.execute(f"UPDATE rvault SET {kind}={kind}-? WHERE user_id=?", (amt, uid))
    db.execute(f"UPDATE resources SET {kind}={kind}+? WHERE user_id=?", (amt, uid))
    return f"📤 {fn(amt)} {names[kind]} به انبار برگشت."


def vault_upgrade(chat_id, uid):
    v = vault_of(uid)
    cost_m, cost_i = v["lvl"] * 1500, v["lvl"] * 5
    p = profile(uid)
    r = ensure_resources(uid)
    if p["money"] < cost_m:
        return f"💸 ارتقا {fmt_money(cost_m)}💰 می‌خواهد."
    if r["iron"] < cost_i:
        return f"⚒️ {fn(cost_i)} آهن لازم است."
    change_money(uid, -cost_m, "vault", "ارتقا گاوصندوق")
    db.execute("UPDATE resources SET iron=iron-? WHERE user_id=?", (cost_i, uid))
    db.execute("UPDATE rvault SET lvl=lvl+1 WHERE user_id=?", (uid,))
    return f"🧰 گاوصندوق سطح {fn(v['lvl']+1)} شد! ظرفیت هر منبع: {fn((v['lvl']+1)*VAULT_CAP_PER_LVL)} 🛡"


# ───── 🗳️ شهردار هفته ─────

def mayor_of():
    try:
        uid = int(get_setting("mayor_uid", "") or 0)
    except Exception:
        uid = 0
    return profile(uid) if uid else None


def panel_election(chat_id, uid):
    wk = week_key()
    mayor = mayor_of()
    me = profile(uid)
    rows = []
    lines = ["🗳️ انتخابات شهردار هفته\n━━━━━━━━━━━\n"]
    lines.append(f"🏛 شهردار فعلی: {mayor['name'] if mayor else '—'}")
    # 🆕 v7: خزانه و مالیات
    lines.append(f"🏛 خزانه شهر: {fmt_money(treasury_amount())}💰 | مالیات شهری: {fn(city_tax_rate()*100)}٪")
    if mayor and mayor["user_id"] == uid and me.get("mayor_last") != today():
        rows.append([(f"💼 دریافت حقوق روزانه شهردار ({fmt_money(MAYOR_SALARY)}💰)", "ele:salary")])
    if mayor and mayor["user_id"] == uid:
        rows.append([("🏛 مالیات ۰٪", "ele:tax:0"), ("🏛 مالیات ۵٪", "ele:tax:5"), ("🏛 مالیات ۱۰٪", "ele:tax:10")])
    lines.append(f"\n📋 کاندیداهای این هفته:")
    cands = db.fetchall("SELECT * FROM elec WHERE week=? ORDER BY votes DESC", (wk,))
    voted = db.fetchone("SELECT * FROM elec_votes WHERE week=? AND voter=?", (wk, uid))
    if not cands:
        lines.append("هنوز کسی کاندید نشده! اولین نفر باش 😎")
    for c in cands:
        cp = profile(c["candidate"])
        nm = cp["name"] if cp else "?"
        mark = " 🗳(رأی تو)" if voted and voted["candidate"] == c["candidate"] else ""
        lines.append(f"▫️ {nm} — {fn(c['votes'])} رأی{mark}")
        if not voted and c["candidate"] != uid:
            rows.append([(f"🗳 رأی به {nm}", f"ele:vote:{c['candidate']}")])
    if not db.fetchone("SELECT 1 FROM elec WHERE week=? AND candidate=?", (wk, uid)):
        rows.append([(f"🙋 کاندید شدن ({fmt_money(MAYOR_ENTRY)}💰)", "ele:join")])
    lines.append(f"\n💰 کاندیداتوری: {fmt_money(MAYOR_ENTRY)}💰 | 🗳 هر نفر ۱ رأی در هفته")
    lines.append(f"👑 شهردارِ منتخب هر هفته: حقوق روزانه {fmt_money(MAYOR_SALARY)}💰 + اعلام در کانال!")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def election_join(chat_id, uid):
    wk = week_key()
    if db.fetchone("SELECT 1 FROM elec WHERE week=? AND candidate=?", (wk, uid)):
        return "🙋 همین الانم کاندیدی!"
    p = profile(uid)
    if p["money"] < MAYOR_ENTRY:
        return f"💸 کاندیداتوری {fmt_money(MAYOR_ENTRY)}💰 هزینه دارد."
    if is_jailed(uid):
        return "⛓ زندانی که کاندید نمی‌شود! 😂"
    change_money(uid, -MAYOR_ENTRY, "election", "هزینه کاندیداتوری شهردار")
    db.execute("INSERT INTO elec(week,candidate,votes) VALUES(?,?,1)", (wk, uid))
    db.execute("INSERT OR REPLACE INTO elec_votes(week,voter,candidate) VALUES(?,?,?)", (wk, uid, uid))
    channel_news(f"🗳️ {p['name']} خودش را کاندیدای شهرداری شهر کرد! برنامه‌ها را بشنوید و رأی بدهید!")
    log_action(uid, "election_join", wk)
    return "🎉 کاندید شدی! به بقیه بگو بهت رأی بدهند 🗳️ (خودت هم ۱ رأی داری)"


def election_vote(chat_id, uid, cand):
    wk = week_key()
    if db.fetchone("SELECT 1 FROM elec_votes WHERE week=? AND voter=?", (wk, uid)):
        return "🗳 این هفته رأی دادی! صبر کن هفته بعد."
    c = db.fetchone("SELECT * FROM elec WHERE week=? AND candidate=?", (wk, cand))
    if not c:
        return "❌ چنین کاندیدی نیست."
    db.execute("UPDATE elec SET votes=votes+1 WHERE week=? AND candidate=?", (wk, cand))
    db.execute("INSERT INTO elec_votes(week,voter,candidate) VALUES(?,?,?)", (wk, uid, cand))
    nm = (profile(cand) or {}).get("name", "?")
    log_action(uid, "election_vote", str(cand))
    return f"🗳 رأیت به «{nm}» ثبت شد! انتخابات آخر هفته نتیجه می‌دهد."


def election_salary(chat_id, uid):
    mayor = mayor_of()
    if not mayor or mayor["user_id"] != uid:
        return "🏛 تو شهردار نیستی! اول انتخاب شو 😄"
    p = profile(uid)
    if p.get("mayor_last") == today():
        return "💼 حقوق امروزت را گرفتی! فردا بیا."
    change_money(uid, MAYOR_SALARY, "mayor", "حقوق روزانه شهردار")
    db.execute("UPDATE profiles SET mayor_last=? WHERE user_id=?", (today(), uid))
    return f"💼 حقوق شهرداری واریز شد: +{fmt_money(MAYOR_SALARY)}💰 | برای شهر مفید باش! 🎩"


def resolve_election(prev_week):
    """آخر هر هفته: بالاترین رأی = شهردار جدید"""
    cands = db.fetchall("SELECT * FROM elec WHERE week=? ORDER BY votes DESC", (prev_week,))
    if not cands:
        set_setting("mayor_uid", "")
        return
    winner = cands[0]
    set_setting("mayor_uid", str(winner["candidate"]))
    nm = (profile(winner["candidate"]) or {}).get("name", "?")
    api.send_message(winner["candidate"],
                     f"👑🎉 تبریک! با {fn(winner['votes'])} رأی، شهردارِ این هفته شهر شدی!\n"
                     f"هر روز از پنل «🏙 شهر → شهردار هفته» حقوق {fmt_money(MAYOR_SALARY)}💰 بگیر!")
    channel_news(f"👑 نتیجه انتخابات!\n«{nm}» با {fn(winner['votes'])} رأی شهردار جدید شهر شد!\n🏛 دوره جدید شهرداری آغاز شد...")
    log_action(0, "mayor_elected", f"{winner['candidate']} votes={winner['votes']}")


# ───── 🚓 گشت شبانه پلیس ─────

def police_patrol(chat_id, uid):
    p = profile(uid)
    if p["job_id"] != "police":
        return "👮 فقط افسر پلیس می‌تواند گشت بزند!"
    if is_jailed(uid):
        return "⛓ خودت که زندانی! 😂"
    used = today_logs(uid, "police_patrol")
    if used >= POLICE_PATROL_LIMIT:
        return f"🚓 شیفت گشتت تمام شد ({fn(POLICE_PATROL_LIMIT)}/روز). فردا بیا!"
    log_action(uid, "police_patrol", "")
    from datetime import timedelta
    since = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    rows = db.fetchall("""SELECT DISTINCT criminal FROM crime_log
                          WHERE busted=0 AND created_at>=? AND criminal!=?
                          ORDER BY RANDOM() LIMIT 5""", (since, uid))
    if not rows:
        gain_xp(uid, 5)
        return "🚓 گشت زدی ولی شهر امن بود؛ مجرمی پیدا نشد! 🕊 (+۵⭐)"
    crim_id = rows[0]["criminal"]
    cp = profile(crim_id)
    if random.random() < 0.65:
        fine = min(1000, max(0, (cp["money"] if cp else 0)))
        if is_jailed(crim_id):
            fine //= 2
        if fine <= 0:
            fine = 200  # جریمه رمانی ثابت اگر پول نداشت (از هوا! شوخی — شهر می‌دهد)
        else:
            change_money(crim_id, -fine, "police", f"دستگیری توسط افسر {p['name']}")
        reward = int(fine * POLICE_REWARD_RATE)
        change_money(uid, reward, "police", f"جایزه دستگیری {cp['name'] if cp else '?'}")
        treasury_feed(int(fine * 0.3), "police")   # 🏛 ۳۰٪ جریمه → خزانه شهر
        db.execute("UPDATE crime_log SET busted=1 WHERE criminal=? AND busted=0", (crim_id,))
        gain_xp(uid, 25)
        if cp:
            api.send_message(crim_id,
                             f"🚔 افسر پلیس «{p['name']}» رد جیب‌بری‌هایت را گرفت!\n"
                             f"💸 جریمه: -{fmt_money(fine)} تومان. دیگر شوخی نکن! 😬")
        log_action(uid, "police_bust", f"{crim_id} fine={fine}")
        return (f"🚔 دستگیری موفق! رد «{cp['name'] if cp else '?'}» را پیدا کردی.\n"
                f"💰 جایزه: +{fmt_money(reward)} تومان (نیم از جریمه)\n🏛 ۳۰٪ جریمه به خزانه فرهنگی شهر رفت! (+۲۵⭐)")
    gain_xp(uid, 8)
    return "🚓 تعقیب کردی ولی مظنون از کوچه‌های خلوت فرار کرد! 💨 (+۸⭐)"


# ───── 📅 ماموریت‌های هفتگی ─────

def panel_weekly_missions(chat_id, uid):
    wk = week_key()
    ws = week_start()
    rows = []
    lines = [f"📅 ماموریت‌های هفته ({wk}) 🎁\n━━━━━━━━━━━\n"]
    for mkey, title, action, target, reward in WEEKLY_DEF:
        db.execute("INSERT OR IGNORE INTO wmissions(user_id,week,mkey,done) VALUES(?,?,?,0)", (uid, wk, mkey))
        done = db.fetchone("SELECT done FROM wmissions WHERE user_id=? AND week=? AND mkey=?", (uid, wk, mkey))["done"]
        prog = logs_since(uid, action, ws)
        r_txt = " + ".join(([f"{fmt_money(reward['money'])}💰"] if reward.get("money") else []) +
                           ([f"{fn(reward['gems'])}💎"] if reward.get("gems") else []))
        if done:
            lines.append(f"{title}\n   ✅ انجام شد | {r_txt}")
        elif prog >= target:
            lines.append(f"{title}\n   🎁 آماده دریافت! | {r_txt}")
            rows.append([(f"دریافت: {title.split(' ', 1)[1][:20]}", f"wms:cl:{mkey}")])
        else:
            lines.append(f"{title}\n   ⏳ {fn(min(prog, target))}/{fn(target)} | {r_txt}")
    lines.append("\n⏰ هر دوشنبه ماموریت‌های تازه می‌آید!")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def weekly_claim(chat_id, uid, mkey):
    wk = week_key()
    d = next((x for x in WEEKLY_DEF if x[0] == mkey), None)
    if not d:
        return "❌"
    _, title, action, target, reward = d
    row = db.fetchone("SELECT done FROM wmissions WHERE user_id=? AND week=? AND mkey=?", (uid, wk, mkey))
    if row and row["done"]:
        return "⚠️ جایزه را گرفتی!"
    if logs_since(uid, action, week_start()) < target:
        return "⏳ هنوز کامل نشده!"
    db.execute("INSERT OR REPLACE INTO wmissions(user_id,week,mkey,done) VALUES(?,?,?,1)", (uid, wk, mkey))
    out = f"🎁 «{title}» انجام شد!\n"
    if reward.get("money"):
        change_money(uid, reward["money"], "wmission", title)
        out += f"💰 +{fmt_money(reward['money'])}\n"
    if reward.get("gems"):
        add_gems(uid, reward["gems"])
        out += f"💎 +{fn(reward['gems'])}"
    log_action(uid, "wmission_claim", mkey)
    return out


# ───── 🏁 مسابقه پت ─────

def pet_race(chat_id, uid):
    pet = pet_tick(uid)
    if not pet:
        return "🐾 اول یه پت بخر!"
    if pet["hunger"] >= 80:
        return "🍖 پتت خیلی گرسنه است؛ نمی‌تواند بدود! اول غذاش بده."
    used = today_logs(uid, "pet_race")
    if used >= 3:
        return "🏁 سه مسابقه امروزت تمام شد! پت هم باید استراحت کنه 😴"
    log_action(uid, "pet_race", "")
    sp = next((x for x in PETS if x[0] == pet["species"]), PETS[0])
    rivals = [("گربه عمو جعفر", random.uniform(1, 8)), ("سگ پادار", random.uniform(1, 8)), ("خرگوش تیزپا", random.uniform(1, 8))]
    mine = pet["level"] + pet["happy"] / 20 - pet["hunger"] / 30 + random.uniform(0, 5)
    if pet.get("talent") == "race":          # 🆕 v7: استعداد دونده
        mine += 2
    results = sorted([("«" + pet["name"] + "»", mine)] + rivals, key=lambda x: x[1], reverse=True)
    rank = next(i + 1 for i, (n, _) in enumerate(results) if n == f"«{pet['name']}»")
    order = " 🏁 ".join(n for n, _ in results)
    prizes = {1: 800 + pet["level"] * 120, 2: 350, 3: 150, 4: 0}
    prize = prizes.get(rank, 0)
    if prize:
        change_money(uid, prize, "pet_race", f"مسابقه پت — رتبه {rank}")
    lvl_txt = ""
    if rank == 1:
        gain_xp(uid, 20)
        if random.random() < 0.4 and pet["level"] < 15:
            db.execute("UPDATE pets SET level=level+1 WHERE user_id=?", (uid,))
            lvl_txt = f"\n🆙 «{pet['name']}» یک لول صعود کرد!"
        if prize >= 2000:
            channel_news(f"🏁 مسابقه پت‌ها!\n«{pet['name']}» ({sp[1]}) متعلق به {profile(uid)['name']} قهرمان شد! 🥇")
        medal = "🥇"
    elif rank == 2:
        gain_xp(uid, 10); medal = "🥈"
    elif rank == 3:
        gain_xp(uid, 5); medal = "🥉"
    else:
        gain_xp(uid, 3); medal = "4️⃣"
    return (f"🏁 مسابقه پت‌ها!\n{order}\n━━━━━━━━━━━\n"
            f"{medal} رتبه «{pet['name']}»: {fn(rank)}\n"
            f"{'💰 +' + fmt_money(prize) + ' تومان!' if prize else '💨 جایزه نگرفتی — پتت را قوی‌تر کن (بازی/غذا)!'}{lvl_txt}")


# ───── 💱 صرافی سکه ─────

def panel_exchange(chat_id, uid):
    p = profile(uid)
    rows = [[(f"خرید {n}💎 ({fmt_money(n*GEM_BUY_PRICE)}💰)", f"exc:b:{n}") for n in (1, 5, 10)],
            [(f"فروش {n}💎 ({fmt_money(n*GEM_SELL_PRICE)}💰)", f"exc:s:{n}") for n in (1, 5, 10)]]
    api.send_message(chat_id,
                     f"💱 صرافی شهر\n━━━━━━━━━━━\n"
                     f"💎 سکه‌های تو: {fn(p.get('gems') or 0)}\n"
                     f"خرید: هر 💎 = {fmt_money(GEM_BUY_PRICE)}💰 | فروش: هر 💎 = {fmt_money(GEM_SELL_PRICE)}💰",
                     inline_keyboard(rows))


def exchange_do(chat_id, uid, side, n):
    n = int(n)
    p = profile(uid)
    if side == "b":
        cost = n * GEM_BUY_PRICE
        if p["money"] < cost:
            return f"💸 {fmt_money(cost)}💰 لازم است."
        change_money(uid, -cost, "exchange", f"خرید {n} سکه")
        add_gems(uid, n)
        return f"💱 {fn(n)}💎 سکه خریدی! (-{fmt_money(cost)}💰)"
    if (p.get("gems") or 0) < n:
        return "💎 سکه کافی نداری."
    add_gems(uid, -n)
    gain = n * GEM_SELL_PRICE
    change_money(uid, gain, "exchange", f"فروش {n} سکه")
    return f"💱 {fn(n)}💎 فروختی! +{fmt_money(gain)}💰"


# ───── 🛒 بازار آگهی کاربران (P2P) ─────

def panel_ads(chat_id, uid):
    rows = [[("➕ گذاشتن آگهی جدید", "ads:mk")], [("📋 آگهی‌های من", "ads:mine")]]
    lines = ["🛒 بازار آگهی کاربران\n━━━━━━━━━━━\nاقلامت را خودت قیمت بگذار و به بقیه بفروش! (کارمزد ۵٪)\n"]
    ads = db.fetchall("""SELECT a.*, i.emoji, i.name FROM ads a JOIN items i ON i.id=a.item_id
                         ORDER BY a.id DESC LIMIT 8""")
    if not ads:
        lines.append("فعلاً آگهی نیست! اولین آگهی را تو بگذار 😎")
    for a in ads:
        sp = profile(a["seller"])
        own = a["seller"] == uid
        lines.append(f"▫️ {a['emoji']} {a['name']} — {fmt_money(a['price'])}💰 (فروشنده: {sp['name'] if sp else '?'})")
        if not own:
            rows.append([(f"خرید {a['emoji']} {a['name']} ({fmt_money(a['price'])})", f"ads:buy:{a['id']}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


def ads_make_menu(chat_id, uid):
    inv = db.fetchall("""SELECT inv.item_id, i.emoji, i.name FROM inventory inv
                         JOIN items i ON i.id=inv.item_id WHERE inv.user_id=?""", (uid,))
    if not inv:
        return "📦 چیزی توی کوله‌ات نیست که آگهی بگذاری!"
    rows = [[(f"{it['emoji']} {it['name']}", f"ads:new:{it['item_id']}")] for it in inv]
    api.send_message(chat_id, "کدام قلم را می‌خواهی بفروشی؟", inline_keyboard(rows))
    return None


def ads_new(chat_id, uid, item_id):
    if not db.fetchone("SELECT 1 FROM inventory WHERE user_id=? AND item_id=?", (uid, item_id)):
        return "❌ این قلم را نداری!"
    if db.fetchone("SELECT 1 FROM ads WHERE seller=? AND item_id=?", (uid, item_id)):
        return "⚠️ برای این قلم از قبل آگهی داری («آگهی‌های من» را ببین)."
    set_state(uid, "ads_price", {"item_id": int(item_id)})
    api.send_message(chat_id, "💵 قیمت فروش را به تومان بنویس (مثلاً 5000):\n(برای لغو: لغو ❌)")
    return None


def ads_price_done(chat_id, uid, text, data):
    t = parse_num(text)
    if not t.isdigit() or not (10 <= int(t) <= 1_000_000_000):
        api.send_message(chat_id, "⚠️ قیمت معتبر بنویس (حداقل ۱۰):")
        return True
    item_id = int(data.get("item_id", 0))
    if not db.fetchone("SELECT 1 FROM inventory WHERE user_id=? AND item_id=?", (uid, item_id)):
        set_state(uid)
        api.send_message(chat_id, "❌ دیگر آن قلم را نداری!", MAIN_KB)
        return True
    db.execute("INSERT INTO ads(seller,item_id,price,created_at) VALUES(?,?,?,?)", (uid, item_id, int(t), now_iso()))
    set_state(uid)
    it = db.fetchone("SELECT emoji,name FROM items WHERE id=?", (item_id,))
    log_action(uid, "ads_new", f"{item_id} {t}")
    api.send_message(chat_id, f"📢 آگهی ثبت شد! {it['emoji']} {it['name']} به قیمت {fmt_money(int(t))}💰 در بازار آگهی است.", MAIN_KB)
    return True


def ads_buy(chat_id, uid, ad_id):
    a = db.fetchone("""SELECT a.*, i.emoji, i.name FROM ads a JOIN items i ON i.id=a.item_id WHERE a.id=?""", (ad_id,))
    if not a:
        return "❌ آگهی فروخته یا حذف شده."
    if a["seller"] == uid:
        return "😂 نمی‌توانی از خودت بخری!"
    if db.fetchone("SELECT 1 FROM inventory WHERE user_id=? AND item_id=?", (uid, a["item_id"])):
        return "⚠️ این قلم را از قبل داری!"
    if not db.fetchone("SELECT 1 FROM inventory WHERE user_id=? AND item_id=?", (a["seller"], a["item_id"])):
        db.execute("DELETE FROM ads WHERE id=?", (ad_id,))
        return "❌ فروشنده دیگر قلم را ندارد — آگهی حذف شد."
    p = profile(uid)
    if p["money"] < a["price"]:
        return f"💸 {fmt_money(a['price'])}💰 لازم است."
    gain = int(a["price"] * (1 - ADS_FEE))
    tax = tax_apply(uid, a["price"], "ads")            # 🆕 v7: مالیات شهردار
    cost = a["price"] + tax
    if profile(uid)["money"] < cost:
        return f"💸 با مالیات شهر ({fmt_money(tax)}) جمعاً {fmt_money(cost)} لازم است."
    change_money(uid, -cost, "ads", f"خرید {a['name']} از بازار آگهی")
    change_money(a["seller"], gain, "ads", f"فروش {a['name']} (کارمزد {fmt_money(a['price']-gain)})")
    db.execute("UPDATE inventory SET user_id=? WHERE user_id=? AND item_id=?", (uid, a["seller"], a["item_id"]))
    db.execute("DELETE FROM ads WHERE id=?", (ad_id,))
    api.send_message(a["seller"],
                     f"🎉 آگهیت فروخته شد! {a['emoji']} {a['name']} → +{fmt_money(gain)}💰 (۵٪ کارمزد کسر شد)")
    log_action(uid, "ads_buy", str(ad_id))
    return f"🛒 خریدی! {a['emoji']} {a['name']} به کوله‌ات اضافه شد. (-{fmt_money(a['price'])}💰)"


def panel_ads_mine(chat_id, uid):
    rows = []
    lines = ["📋 آگهی‌های من\n"]
    mine = db.fetchall("""SELECT a.*, i.emoji, i.name FROM ads a JOIN items i ON i.id=a.item_id
                          WHERE a.seller=? ORDER BY a.id DESC""", (uid,))
    if not mine:
        lines.append("آگهی فعالی نداری.")
    for a in mine:
        lines.append(f"▫️ {a['emoji']} {a['name']} — {fmt_money(a['price'])}💰")
        rows.append([(f"🗑 حذف آگهی {a['emoji']} {a['name']}", f"ads:del:{a['id']}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def ads_delete(chat_id, uid, ad_id):
    a = db.fetchone("SELECT * FROM ads WHERE id=? AND seller=?", (ad_id, uid))
    if not a:
        return "❌ چنین آگهی‌ای نداری."
    db.execute("DELETE FROM ads WHERE id=?", (ad_id,))
    return "🗑 آگهی حذف شد (قلم در کوله‌ات ماند)."


# ───── ⚗️ ترکیب و ذوب آیتم ─────

def panel_craft(chat_id, uid):
    inv = db.fetchall("""SELECT inv.item_id, i.emoji, i.name, i.price FROM inventory inv
                         JOIN items i ON i.id=inv.item_id WHERE inv.user_id=?""", (uid,))
    if len(inv) < 2:
        api.send_message(chat_id,
                         "⚗️ آتشگاه ذوب آیتم\n━━━━━━━━━━━\nدو قلم از کوله‌ات را در کوره بریز و شانس جایزه بهتر داشته باش!\n"
                         "📦 حداقل ۲ قلم لازم است — از فروشگاه یا بازار آگهی تهیه کن.")
        return
    rows = [[(f"{it['emoji']} {it['name']}", f"crf:a:{it['item_id']}")] for it in inv]
    api.send_message(chat_id,
                     "⚗️ آتشگاه ذوب آیتم\n━━━━━━━━━━━\nقوانین کوره:\n"
                     "🔥 ۳۵٪ پول نقد (x۱.۳ جمع قیمت‌ها)\n💎 ۲۵٪ سکه طلا\n⭐ ۲۵٪ XP قابل توجه\n💨 ۱۵٪ کوره می‌ترکد — هیچی!\n\nقلم اول را انتخاب کن:",
                     inline_keyboard(rows))


def craft_pick_b(chat_id, uid, item_a):
    inv = db.fetchall("""SELECT inv.item_id, i.emoji, i.name FROM inventory inv
                         JOIN items i ON i.id=inv.item_id WHERE inv.user_id=? AND inv.item_id!=?""",
                      (uid, int(item_a)))
    if not inv:
        return "📦 قلم دومی نداری!"
    rows = [[(f"{it['emoji']} {it['name']}", f"crf:b:{item_a}:{it['item_id']}")] for it in inv]
    api.send_message(chat_id, "⚗️ حالا قلم دوم:", inline_keyboard(rows))
    return None


def craft_do(chat_id, uid, item_a, item_b):
    item_a, item_b = int(item_a), int(item_b)
    rows = db.fetchall("""SELECT inv.item_id, i.price FROM inventory inv JOIN items i ON i.id=inv.item_id
                          WHERE inv.user_id=? AND inv.item_id IN (?,?)""", (uid, item_a, item_b))
    if len(rows) < 2:
        return "❌ قلم‌ها دیگر در کوله نیستند!"
    total = sum(r["price"] for r in rows)
    db.execute("DELETE FROM inventory WHERE user_id=? AND item_id IN (?,?)", (uid, item_a, item_b))
    roll = random.random()
    log_action(uid, "craft", f"{item_a}+{item_b}")
    if roll < 0.35:
        gain = int(total * 1.3)
        change_money(uid, gain, "craft", "ذوب آیتم → پول")
        return f"⚗️🔥 کوره غرشید و چیزی براق بیرون افتاد... 💰 +{fmt_money(gain)} تومان!"
    if roll < 0.60:
        g = max(1, min(8, total // 2500))
        add_gems(uid, g)
        if g >= 5:
            channel_news(f"⚗️ کیمیاگر شهر! {profile(uid)['name']} در کوره {fn(g)}💎 سکه طلا ذوب کرد!")
        return f"⚗️💎 معجزه کیمیاگری! از دل کوره {fn(g)} سکه طلا بیرون آمد!"
    if roll < 0.85:
        xp = max(30, total // 40)
        gain_xp(uid, xp)
        return f"⚗️⭐ صنعتگر شدی! تجربه ارزشمندی بود: +{fn(xp)} XP"
    return "⚗️💨 ترکید...! کوره داغ شد و هر دو قلم خاکستر شدند. (ریسک دیگه!)"


# ───── 🏠 اجاره املاک ─────

def rent_collect(chat_id, uid):
    houses = [n for (n,) in db.fetchall("""SELECT i.name FROM inventory inv JOIN items i ON i.id=inv.item_id
                                           WHERE inv.user_id=?""", (uid,)) if n in RENT_RATES]
    if not houses:
        return "🏠 ملکی نداری که اجاره بدهی!"
    row = db.fetchone("SELECT * FROM rent WHERE user_id=?", (uid,))
    if not row:
        db.execute("INSERT INTO rent(user_id,last_collect) VALUES(?,?)", (uid, now_iso()))
        return "🏠 مستأجرها مستقر شدند! از همین حالا هر ۶ ساعت اجاره جمع می‌شود. ⏰"
    try:
        elapsed = (datetime.now() - datetime.fromisoformat(row["last_collect"])).total_seconds()
    except Exception:
        elapsed = 0
    ticks = min(6, int(elapsed // TICK_SEC))
    if ticks <= 0:
        left = TICK_SEC - elapsed
        return f"⏳ هنوز اجاره‌ای جمع نشده! اجاره بعدی: {fn(int(left//60)+1)} دقیقه دیگر."
    gross = sum(RENT_RATES[n] for n in houses) * ticks
    net = int(gross * (1 - RENT_MAINT))
    db.execute("UPDATE rent SET last_collect=? WHERE user_id=?", (now_iso(), uid))
    change_money(uid, net, "rent", f"اجاره {fn(ticks)} دور (خالص پس از نگهداری)")
    gain_xp(uid, 10)
    detail = " + ".join(f"{n}({fmt_money(RENT_RATES[n])})" for n in houses)
    return (f"💵 اجاره جمع شد! ({fn(ticks)} دور ۶ ساعته)\n"
            f"🏠 {detail}\n🔧 نگهداری ۱۰٪: -{fmt_money(gross - net)}\n"
            f"✅ خالص: +{fmt_money(net)} تومان!")


# ───── 🎂 تولد ─────

def panel_birthday(chat_id, uid):
    row = db.fetchone("SELECT * FROM birthday WHERE user_id=?", (uid,))
    d = datetime.now()
    if not row:
        rows = [[("🎂 ثبت تاریخ تولدم", "bdy:set")]]
        api.send_message(chat_id,
                         f"🎂 تولدت را ثبت کن؛ در روز تولدت جایزه بزرگ می‌گیری!\n"
                         f"🎁 جایزه: {fmt_money(BDAY_MONEY)}💰 + {fn(BDAY_GEMS)}💎 (سالی یک بار)",
                         inline_keyboard(rows))
        return
    is_today = row["day"] == d.day and row["month"] == d.month
    can = is_today and row["last_year"] != d.year
    rows = []
    if can:
        rows.append([("🎁 گرفتن جایزه تولد!", "bdy:claim")])
    api.send_message(chat_id,
                     f"🎂 تولد تو: {fn(row['day'])}/{fn(row['month'])}\n"
                     + ("🎉🎉🎉 امروز تولدته! جایزه را بردار!" if can else
                        ("✅ جایزه امسالت را گرفتی!" if is_today else "⏳ به تاریخ تولدت که رسید جایزه می‌گیری!")) +
                     f"\n🎁 جایزه: {fmt_money(BDAY_MONEY)}💰 + {fn(BDAY_GEMS)}💎",
                     inline_keyboard(rows) if rows else None)


def birthday_set_ask(chat_id, uid):
    set_state(uid, "bday_set", {})
    api.send_message(chat_id, "🎂 تاریخ تولدت را این‌طوری بنویس: روز/ماه\nمثلاً: 15/7 (یعنی ۱۵ تیر)")


def birthday_set_done(chat_id, uid, text):
    t = parse_num(text).replace(" ", "").replace("-", "/")
    parts = t.split("/")
    ok = len(parts) == 2 and all(x.isdigit() for x in parts)
    if ok:
        day, month = int(parts[0]), int(parts[1])
        ok = 1 <= day <= 31 and 1 <= month <= 12
    if not ok:
        api.send_message(chat_id, "⚠️ فرمت درست: روز/ماه — مثل 15/7")
        return True
    db.execute("INSERT OR REPLACE INTO birthday(user_id,day,month,last_year) VALUES(?,?,?,COALESCE((SELECT last_year FROM birthday WHERE user_id=?),0))",
               (uid, day, month, uid))
    set_state(uid)
    api.send_message(chat_id, f"🎂 ثبت شد! تولدت: {fn(day)}/{fn(month)} — اون روز بیا و جایزه‌ات را بگیر! 🎁", MAIN_KB)
    return True


def birthday_claim(chat_id, uid):
    row = db.fetchone("SELECT * FROM birthday WHERE user_id=?", (uid,))
    d = datetime.now()
    if not row or row["day"] != d.day or row["month"] != d.month:
        return "🎂 امروز تولدت نیست!"
    if row["last_year"] == d.year:
        return "✅ جایزه امسالت را گرفتی!"
    db.execute("UPDATE birthday SET last_year=? WHERE user_id=?", (d.year, uid))
    change_money(uid, BDAY_MONEY, "birthday", "جایزه تولد")
    add_gems(uid, BDAY_GEMS)
    gain_xp(uid, 50)
    log_action(uid, "birthday", str(d.year))
    channel_news(f"🎂 امروز تولد «{profile(uid)['name']}» است! همه تبریک بگویند! 🥳🎉")
    return (f"🥳🎂 تولدت مبارک!!!\n🎁 جایزه تولد: +{fmt_money(BDAY_MONEY)}💰 و +{fn(BDAY_GEMS)}💎 سکه طلا!\n"
            f"⭐ +۵۰ XP | یک سال عالی پیش رو! 🎉")


# ══════════════════════════════════════════════════════════════════
# [8.9] 🆕 v7: پیمان کاری، سپرده بلندمدت، خزانه/مالیات شهردار، تابلوی زندان،
#       دوره‌های آموزشی، مدرسه پت، کویست اتحاد، سفر خانوادگی، درجه افتخار،
#       رتبه‌بندی چندبعدی، رادیو شهر، معامله طلایی، گارد شخصی، سفارش امپراتوری
# ══════════════════════════════════════════════════════════════════

# ───── 🎖 درجه‌های افتخار ─────

def honor_rank(level: int):
    for min_lvl, title, bonus in HONOR_RANKS:
        if level >= min_lvl:
            return title, bonus
    return "🐣 نوزاد شهر", 0.0


# ───── 📜 پیمان کاری (۵مین شیفت روز = بونس) ─────

def work_contract_tick(uid, salary):
    """داخل job_work صدا زده می‌شود: شمارش شیفت‌های امروز"""
    p = profile(uid)
    if p.get("work_shifts_day") != today():
        db.execute("UPDATE profiles SET work_shifts_day=?, work_shifts=1 WHERE user_id=?", (today(), uid))
        cnt = 1
    else:
        cnt = (p.get("work_shifts") or 0) + 1
        db.execute("UPDATE profiles SET work_shifts=? WHERE user_id=?", (cnt, uid))
    if cnt == WORK_CONTRACT_TARGET:
        bonus = salary * WORK_CONTRACT_MULT
        change_money(uid, bonus, "contract", f"پیمان کاری روزانه ({WORK_CONTRACT_TARGET} شیفت)")
        channel_news(f"📜 کارگر نمونه!\n{profile(uid)['name']} امروز {fn(WORK_CONTRACT_TARGET)} شیفت کامل کار کرد و بونس {fmt_money(bonus)} تومانی گرفت! 💪")
        log_action(uid, "work_contract", str(bonus))
        return f"\n📜 پیمان کاری تکمیل شد! بونس +{fmt_money(bonus)} تومان (×{fn(WORK_CONTRACT_MULT)} حقوق) 🎉"
    return f"\n📜 شیفت امروز: {fn(cnt)}/{fn(WORK_CONTRACT_TARGET)} (بونس در شیفت {fn(WORK_CONTRACT_TARGET)}م)"


# ───── 🏦 سپرده بلندمدت ─────

def lock_deposit(chat_id, uid, amount):
    amount = int(amount)
    p = profile(uid)
    if (p.get("dep_locked") or 0) > 0:
        return "🔒 یک سپرده قفل فعال داری! اول آزادش کن."
    if p["money"] < amount:
        return f"💸 {fmt_money(amount)} تومان لازم است."
    change_money(uid, -amount, "bank", "سپرده بلندمدت (قفل ۳ روزه)")
    from datetime import timedelta
    until = (datetime.now() + timedelta(days=LOCK_DEPOSIT_DAYS)).isoformat(timespec="seconds")
    db.execute("UPDATE profiles SET dep_locked=?, dep_until=? WHERE user_id=?", (amount, until, uid))
    log_action(uid, "lock_dep", str(amount))
    return (f"🏦 سپرده بلندمدت ثبت شد!\n💰 {fmt_money(amount)} تومان → تا {until[:10]} قفل شد\n"
            f"🎁 پس از {fn(LOCK_DEPOSIT_DAYS)} روز با سود {fn(int(LOCK_DEPOSIT_RATE*100))}٪ برمی‌گردد = {fmt_money(int(amount*(1+LOCK_DEPOSIT_RATE)))} 💰")


def unlock_deposit(chat_id, uid):
    p = profile(uid)
    locked = p.get("dep_locked") or 0
    if locked <= 0:
        return "🏦 سپرده قفلی نداری."
    due = True
    try:
        due = datetime.fromisoformat(p["dep_until"]) <= datetime.now()
    except Exception:
        pass
    if due:
        total = int(locked * (1 + LOCK_DEPOSIT_RATE))
        change_money(uid, total, "bank", "آزادسازی سپرده بلندمدت با سود")
        db.execute("UPDATE profiles SET dep_locked=0, dep_until=NULL WHERE user_id=?", (uid,))
        log_action(uid, "unlock_dep", str(total))
        return f"🎉 سپرده سررسید شد! +{fmt_money(total)} تومان (اصل + سود {fn(int(LOCK_DEPOSIT_RATE*100))}٪)"
    change_money(uid, locked, "bank", "برداشت زودهنگام سپرده (بدون سود)")
    db.execute("UPDATE profiles SET dep_locked=0, dep_until=NULL WHERE user_id=?", (uid,))
    return f"🔓 زودهنگام برداشتی؛ فقط اصل {fmt_money(locked)} برگشت (سود سوخت 😬)"


# ───── 🏛 خزانه شهر + مالیات شهردار ─────

def city_tax_rate() -> float:
    try:
        return float(get_setting("city_tax", "0")) / 100.0
    except Exception:
        return 0.0


def tax_apply(uid, amount, kind_fa, payer_is_sender=True):
    """مالیات بر تراکنش‌ها (انتقال/آگهی) → خزانه شهر"""
    rate = city_tax_rate()
    tax = int(amount * rate)
    if tax > 0:
        treasury_feed(tax, kind_fa)
    return tax


def mayor_set_tax(chat_id, uid, rate):
    mayor = mayor_of()
    if not mayor or mayor["user_id"] != uid:
        return "🏛 فقط شهردار فعلی می‌تواند مالیات را تعیین کند!"
    set_setting("city_tax", str(rate))
    nm = profile(uid)["name"]
    channel_news(f"🏛 تصمیم شهرداری!\nشهردار «{nm}» مالیات شهری را {fn(rate)}٪ اعلام کرد.\n"
                 f"(روی انتقال پول و خرید از بازار آگهی اعمال می‌شود → خزانه صرف کارهای فرهنگی می‌شود)")
    log_action(uid, "mayor_tax", str(rate))
    return f"🏛 مالیات شهری روی {fn(rate)}٪ تنظیم شد!"


# ───── 🚔 تابلوی زندان همگانی ─────

def panel_jail(chat_id, uid):
    rows = []
    lines = ["🚔 سجل زندان شهر\n━━━━━━━━━━━\n"]
    jailed = db.fetchall("""SELECT user_id, name, jail_until, last_crime FROM profiles
                            WHERE jail_until IS NOT NULL AND jail_until != ''""")
    found = 0
    for j in jailed:
        try:
            if datetime.fromisoformat(j["jail_until"]) <= datetime.now():
                continue
        except Exception:
            continue
        found += 1
        left = int((datetime.fromisoformat(j["jail_until"]) - datetime.now()).total_seconds() // 60)
        lines.append(f"⛓ {j['name']} — {fn(left)} دقیقه دیگه (بازدید: -۳۰ دقیقه)")
        if j["user_id"] != uid:
            rows.append([(f"🌹 دلجویی از {j['name']}", f"jli:hi:{j['user_id']}")])
    if not found:
        lines.append("شهر امن و آرومه؛ زندانی نداریم! 🕊")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def jail_visit(chat_id, uid, target_id):
    tp = profile(target_id)
    if not tp:
        return "❌"
    if today_logs(uid, f"jail_visit"):
        return "🌹 امروز یک دلجویی کردی؛ بذار نفس بکشن!"
    jail = is_jailed(target_id)
    if not jail:
        return "🕊 این رفیقت آزاد شده!"
    log_action(uid, "jail_visit", str(target_id))
    from datetime import timedelta
    new_until = (datetime.fromisoformat(jail) - timedelta(minutes=30)).isoformat(timespec="seconds")
    db.execute("UPDATE profiles SET jail_until=?, happiness=MIN(100,happiness+8) WHERE user_id=?", (new_until, target_id))
    gain_xp(uid, 10)
    api.send_message(target_id,
                     f"🌹 {profile(uid)['name']} به دیدنت اومد زندان!\n⏰ ۳۰ دقیقه از محکومیتت کم شد | 😊 +۸ شادی")
    if is_jailed(target_id) is None:
        api.send_message(target_id, "🎉 با این بازدید آزاد شدی! دوست خوبی داری 🥹")
    return f"🌹 دلجویی ثبت شد! ۳۰ دقیقه از حکم {tp['name']} کم شد (+۱۰⭐)"


# ───── 🎓 دوره‌های آموزشی ─────

def panel_courses(chat_id, uid):
    rows = []
    lines = ["🎓 مرکز آموزش شهر\n━━━━━━━━━━━\nهر دوره: +۱ مهارت فوری (تا ۳ بار هر دوره)\n"]
    for cid, name, skill, price, cap in COURSES:
        taken = log_count(uid, f"course_{cid}")
        mark = f"({fn(taken)}/{fn(cap)})"
        if taken >= cap:
            lines.append(f"🏁 {name} — اتمام ظرفیت {mark}")
        else:
            lines.append(f"▫️ {name} — {fmt_money(price)}💰 → +۱ {SKILLS[skill]} {mark}")
            rows.append([(f"ثبت‌نام {name} ({fmt_money(price)})", f"crs:buy:{cid}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def course_buy(chat_id, uid, cid):
    c = next((x for x in COURSES if x[0] == cid), None)
    if not c:
        return "❌"
    _, name, skill, price, cap = c
    if log_count(uid, f"course_{cid}") >= cap:
        return "🏁 ظرفیت این دوره برای تو پر شده."
    p = profile(uid)
    if p["money"] < price:
        return f"💸 شهریه {fmt_money(price)} لازم است."
    change_money(uid, -price, "course", name)
    nv = gain_skill(uid, skill)
    log_action(uid, f"course_{cid}", name)
    return f"🎓 کلاس «{name}» تمام شد! {SKILLS[skill]} → لول {fn(nv)} 📈"


# ───── 🐕 مدرسه پت + استعداد ─────

def pet_train(chat_id, uid):
    pet = pet_of(uid)
    if not pet:
        return "🐾 اول یه پت بخر!"
    if today_logs(uid, "pet_train") >= PET_TRAIN_LIMIT:
        return f"🎾 پت امروز حسابی تمرین کرده — بذار استراحت کنه (روزی {fn(PET_TRAIN_LIMIT)} بار) 😴"
    r = ensure_resources(uid)
    if r["food"] < PET_TRAIN_FOOD:
        return "🌾 برای تمرین انرژی‌بخشی به پت، غذا کم داری! (از امپراتوری/مزرعه تهیه کن)"
    db.execute("UPDATE resources SET food=food-? WHERE user_id=?", (PET_TRAIN_FOOD, uid))
    log_action(uid, "pet_train", "")
    total = log_count(uid, "pet_train")
    db.execute("UPDATE pets SET happy=MIN(100,happy+10), hunger=MIN(100,hunger+8) WHERE user_id=?", (uid,))
    gain_xp(uid, 5)
    lvl_txt = ""
    if total % PET_TRAIN_LEVEL == 0 and pet["level"] < 15:
        db.execute("UPDATE pets SET level=level+1 WHERE user_id=?", (uid,))
        lvl_txt = f"\n🆙 تبریک! «{pet['name']}» لول {fn(pet['level']+1)} شد!"
    return (f"🎾 تمرین موفق! «{pet['name']}» خوشحال شد 😊+۱۰ | ۱ 🌾 مصرف شد\n"
            f"مجموع تمرین‌ها: {fn(total)} (هر {fn(PET_TRAIN_LEVEL)} تمرین = +۱ لول){lvl_txt}")


def pet_talent_pick(chat_id, uid, talent):
    pet = pet_of(uid)
    if not pet:
        return "🐾 پتی نداری!"
    if pet.get("talent"):
        return f"🏅 استعداد «{pet['name']}» از قبل ثبت شده: {pet['talent']}"
    if talent not in ("war", "race"):
        return "❌"
    db.execute("UPDATE pets SET talent=? WHERE user_id=?", (talent, uid))
    label = "🛡 جنگجو (+۲ قدرت جنگ)" if talent == "war" else "🏃 دونده (+۲ امتیاز مسابقه)"
    log_action(uid, "pet_talent", talent)
    return f"🏅 استعداد «{pet['name']}»: {label}\nاز امروز در {('جنگ‌ها' if talent=='war' else 'مسابقه‌ها')} بهتره! 🎉"


# ───── 🤝 ماموریت هفتگی اتحاد ─────

def guild_week_wins(gid) -> int:
    rows = db.fetchall("SELECT user_id FROM guild_members WHERE guild_id=?", (gid,))
    return sum(logs_since(r["user_id"], "war_win", week_start()) for r in rows)


def panel_gquest(chat_id, uid):
    g = guild_of(uid)
    if not g:
        api.send_message(chat_id, "🤝 در اتحادی نیستی! اول عضو یک اتحاد شو.")
        return
    done = db.fetchone("SELECT 1 FROM gquests WHERE guild_id=? AND week=?", (g["id"], week_key()))
    wins = guild_week_wins(g["id"])
    rows = []
    if done:
        st = "✅ انجام شد!"
    elif wins >= GQUEST_TARGET:
        st = "🎁 آماده دریافت!"
        rows.append([(f"🎁 دریافت جایزه اتحاد (+{fn(GQUEST_GEMS)}💎 خزانه)", "gqw:claim")])
    else:
        st = f"⏳ {fn(wins)}/{fn(GQUEST_TARGET)}"
    api.send_message(chat_id,
                     f"🤝 ماموریت هفتگی اتحاد «{g['name']}»\n━━━━━━━━━━━\n"
                     f"⚔️ ماموریت: مجموع {fn(GQUEST_TARGET)} برد جنگی اعضا در این هفته\n"
                     f"پیشرفت: {st}\n"
                     f"🎁 جایزه: +{fn(GQUEST_GEMS)}💎 سکه به خزانه اتحاد + اعلام افتخار در کانال!",
                     inline_keyboard(rows) if rows else None)


def gquest_claim(chat_id, uid):
    g = guild_of(uid)
    if not g:
        return "🤝 اتحادی نداری!"
    wk = week_key()
    if db.fetchone("SELECT 1 FROM gquests WHERE guild_id=? AND week=?", (g["id"], wk)):
        return "⚠️ جایزه این هفته گرفته شده!"
    if guild_week_wins(g["id"]) < GQUEST_TARGET:
        return f"⏳ هنوز کامل نشده! ({fn(guild_week_wins(g['id']))}/{fn(GQUEST_TARGET)})"
    db.execute("INSERT INTO gquests(guild_id,week) VALUES(?,?)", (g["id"], wk))
    db.execute("UPDATE guilds SET gems=gems+? WHERE id=?", (GQUEST_GEMS, g["id"]))
    channel_news(f"🤝⚔️ اتحاد «{g['name']}» ماموریت هفتگی را فتح کرد!\n+{fn(GQUEST_GEMS)}💎 به گنجینه اتحاد!")
    log_action(uid, "gquest_claim", g["name"])
    return f"🎁 ماموریت هفتگی اتحاد انجام شد! +{fn(GQUEST_GEMS)}💎 به گنجینه مشترک 💎 پادرمیانیِ دست‌جمعیت! 🎉"


# ───── 💑 سفر خانوادگی ─────

def family_trip(chat_id, uid):
    fam = family_of(uid)
    if not fam or not fam["spouse_id"]:
        return "💑 برای سفر خانوادگی باید ازدواج کرده باشی! (حلقه بخر 💍)"
    p = profile(uid)
    if p["money"] < FAMILY_TRIP_COST:
        return f"💸 سفر خانوادگی {fmt_money(FAMILY_TRIP_COST)} تومان هزینه دارد."
    if today_logs(uid, "family_trip"):
        return "🧳 امروز با خانواده سفر رفتی؛ فردا دوباره!"
    change_money(uid, -FAMILY_TRIP_COST, "family", "سفر خانوادگی")
    log_action(uid, "family_trip", "")
    kids = fam["children"] or 0
    joy = min(40, 20 + kids * 4)
    db.execute("UPDATE profiles SET happiness=MIN(100,happiness+?) WHERE user_id IN (?,?)", (joy, uid, fam["spouse_id"]))
    total = log_count(uid, "family_trip")
    sp = profile(fam["spouse_id"])
    if sp:
        api.send_message(fam["spouse_id"],
                         f"🧳 {p['name']} کل خانواده رو برد مسافرت! 🏖\n😊 شادی همه: +{fn(joy)}")
    gain_xp(uid, 10)
    bonus_txt = ""
    if total % FAMILY_TRIP_GEM_EVERY == 0:
        add_gems(uid, 3)
        bonus_txt = f"\n💎 {fn(FAMILY_TRIP_GEM_EVERY)}مین سفر خانوادگی! یادگاری مشترک: +۳ سکه طلا!"
        channel_news(f"💑 خانواده نمونه!\n{p['name']} و {sp['name'] if sp else ''} {fn(FAMILY_TRIP_GEM_EVERY)}مین سفر مشترکشان را رفتند! 💎")
    behesht = pick(["ساحل خزر 🌊", "باغ‌های شیراز 🌹", "کوه‌های البرز ⛰", "کویر مرنجاب 🏜", "جنگل گیلان 🌲"])
    return (f"🧳 سفر خانوادگی به {behesht}!\n💑 همسر و {fn(kids)} فرزند — همه شاد شدند: +{fn(joy)}😊\n"
            f"سفر مشترک شماره {fn(total)} (+۱۰⭐){bonus_txt}")


# ───── 📊 رتبه‌بندی چندبعدی ─────

def panel_leaderboard_tabs(chat_id, uid, mode="money"):
    medals = ["🥇", "🥈", "🥉"]
    tabs = [("💰", "lb:money"), ("💪", "lb:war"), ("🤝", "lb:guild"), ("🧗", "lb:tower"), ("🐾", "lb:pet")]
    rows = [[tuple(x) for x in tabs[:3]], [tuple(x) for x in tabs[3:]]]
    lines = []
    if mode == "war":
        lines.append("💪 قدرتمندترین جنگجویان (قدرت فعلی):\n")
        allu = db.fetchall("SELECT user_id, name FROM profiles ORDER BY level DESC LIMIT 40")
        scored = sorted(((battle_power(r["user_id"]), r["name"]) for r in allu), reverse=True)[:10]
        for i, (pw, nm) in enumerate(scored):
            lines.append(f"{medals[i] if i < 3 else fn(i+1)+'.'} {nm} — ⚔️ {fn(pw)}")
    elif mode == "guild":
        lines.append("🤝 بزرگ‌ترین اتحادها (گنجینه):\n")
        for i, g in enumerate(db.fetchall("SELECT name, bank, donations FROM guilds ORDER BY donations DESC LIMIT 10")):
            lines.append(f"{medals[i] if i < 3 else fn(i+1)+'.'} {g['name']} — خزانه {fmt_money(g['bank'])} | {fmt_money(g['donations'])} کمک")
        if len(lines) == 1:
            lines.append("هنوز اتحادی نیست!")
    elif mode == "tower":
        lines.append("🧗 صعودکنندگان برج:\n")
        for i, r in enumerate(db.fetchall("SELECT name, tower_floor FROM profiles ORDER BY tower_floor DESC LIMIT 10")):
            lines.append(f"{medals[i] if i < 3 else fn(i+1)+'.'} {r['name']} — طبقه {fn(r['tower_floor'])}")
    elif mode == "pet":
        lines.append("🐾 پت‌دوستان بزرگ:\n")
        for i, r in enumerate(db.fetchall("""SELECT p.name, pt.name AS pname, pt.level FROM pets pt
                                             JOIN profiles p ON p.user_id=pt.user_id
                                             ORDER BY pt.level DESC LIMIT 10""")):
            lines.append(f"{medals[i] if i < 3 else fn(i+1)+'.'} «{r['pname']}» ({r['name']}) — لول {fn(r['level'])}")
        if len(lines) == 1:
            lines.append("هنوز پتی در شهر نیست!")
    else:  # money
        lines.append("💰 ثروتمندترین‌ها (با درجه افتخار):\n")
        for i, r in enumerate(db.fetchall("SELECT name, money, level FROM profiles ORDER BY money DESC LIMIT 10")):
            rank, _ = honor_rank(r["level"])
            lines.append(f"{medals[i] if i < 3 else fn(i+1)+'.'} {r['name']} {rank} — {fmt_money(r['money'])}💰")
    p = profile(uid)
    my_rank, _ = honor_rank(p["level"])
    lines.append(f"\n🎖 درجه تو: {my_rank} | لول {fn(p['level'])}")
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows))


# ───── 📻 رادیو شهر ─────

def radio_tick():
    """هر ۶ ساعت: برنامه زنده رادیو بله‌سیم (+ ۱ خبر داینامیک)"""
    last = get_setting("radio_last")
    if last:
        try:
            if (datetime.now() - datetime.fromisoformat(last)).total_seconds() < RADIO_INTERVAL:
                return
        except Exception:
            pass
    set_setting("radio_last", now_iso())
    line = pick(RADIO_LINES)
    dyn = pick([
        lambda: f"🎙 مالی شهر: خزانه شهرداری {fmt_money(treasury_amount())} تومان است — دهنده‌دان و کارگر نمونه، تشکر!",
        lambda: f"🎙 ورزش محله‌: (شهردار فعلی) {(mayor_of() or {}).get('name', 'شهر فعلاً بدون شهردار است — نامزد شو!')}".replace("(شهردار فعلی) ", ""),
        lambda: f"🎙 هواشناسی: آسمان بورس {'آفتابی و پررونق' if world_event() else 'صاف و آرام'} است 📊",
    ])()
    msg = f"{line}\n{dyn}"
    channel_news(msg)
    db.execute("INSERT INTO announcements(text,created_at) VALUES(?,?)", (msg, now_iso()))
    log_action(0, "radio", "")


# ───── 🛍 معامله طلایی روزانه (تخفیف فروشگاه + پامپ بورس) ─────

def ensure_daily_deal():
    day = get_setting("deal_day")
    if day == today():
        return
    set_setting("deal_day", today())
    it = pick(db.fetchall("SELECT id, name, emoji FROM items WHERE category='shop'"))
    mk = pick(db.fetchall("SELECT symbol, name FROM markets"))
    set_setting("deal_item", str(it["id"]) if it else "")
    set_setting("deal_asset", mk["symbol"] if mk else "")
    if mk:
        db.execute("UPDATE markets SET prev_price=price, price=CAST(price*? AS INTEGER), updated_at=? WHERE symbol=?",
                   (DAILY_DEAL_PUMP, now_iso(), mk["symbol"]))
    if it:
        db.execute("INSERT INTO announcements(text,created_at) VALUES(?,?)",
                   (f"🛍 معامله طلایی امروز: {it['emoji']} {it['name']} با {fmt_money(int(100-DAILY_DEAL_DISCOUNT*100))}٪ تخفیف!", now_iso()))


def deal_item_id():
    ensure_daily_deal()
    try:
        return int(get_setting("deal_item", "") or 0)
    except Exception:
        return 0


# ───── 🛡 گارد امنیتی شخصی ─────

def guard_active(uid) -> bool:
    p = profile(uid)
    return bool(p and p.get("guard_day") == today())


def guard_hire(chat_id, uid):
    if guard_active(uid):
        return "🛡 امروز گارد داری! از فردا برای گارد بعدی بیا."
    p = profile(uid)
    if p["money"] < GUARD_COST:
        return f"💸 برای استخدام گارد {fmt_money(GUARD_COST)} تومان لازم است."
    change_money(uid, -GUARD_COST, "guard", "استخدام گارد شخصی روزانه")
    db.execute("UPDATE profiles SET guard_day=? WHERE user_id=?", (today(), uid))
    log_action(uid, "guard_hire", "")
    return (f"🛡 گارد شخصی استخدام شد (تا پایان امروز)!\n"
            f"اولین جنگ/هک/غارت ارتشی امروز را از تو دفع می‌کند. 🧱\n"
            f"💰 -{fmt_money(GUARD_COST)} تومان")


def guard_blocks(target_id, attacker_name, kind_fa):
    """اگر قربانی امروز گارد دارد: حمله را دفع کن و گارد مصرف شود"""
    if not guard_active(target_id):
        return None
    db.execute("UPDATE profiles SET guard_day=NULL WHERE user_id=?", (target_id,))
    api.send_message(target_id,
                     f"🛡 گارد شخصی‌ات تو را از {kind_fa} «{attacker_name}» نجات داد! ماموریت محافظت انجام شد. 🧱")
    log_action(target_id, "guard_saved", f"vs {attacker_name} {kind_fa}")
    return (f"🛡 {kind_fa} ناموفق! «{attacker_name}» هدفش گارد شخصی استخدام کرده بود — "
            f"محافظت کامل انجام شد. ظرفیت روزانه‌اش هم مصرف شد!")


# ───── 📦 سفارش‌های امپراتوری (NPC روزانه) ─────

def ensure_empire_orders(uid):
    row = db.fetchone("SELECT * FROM eorders WHERE user_id=? AND day=?", (uid, today()))
    if row:
        try:
            return jl(row["data"], {"orders": []})
        except Exception:
            pass
    picks = random.sample(EMPIRE_ORDERS, min(EMPIRE_ORDERS_DAILY, len(EMPIRE_ORDERS)))
    data = {"orders": [{"need": need, "pay": pay} for need, pay in picks], "done": [False] * len(picks)}
    db.execute("INSERT OR REPLACE INTO eorders(user_id,day,data) VALUES(?,?,?)", (uid, today(), jd(data)))
    return data


def panel_empire_orders(chat_id, uid):
    st = ensure_empire_orders(uid)
    rows = []
    lines = ["📨 سفارش‌های روزانه تاجران شهر\n━━━━━━━━━━━\nمنابعت به قیمت خوب!\n"]
    em = {"food": "🌾", "iron": "⚒️", "medicine": "💊"}
    for i, o in enumerate(st["orders"]):
        n_txt = " + ".join(f"{v}{em[k]}" for k, v in o["need"].items())
        mark = "✅ انجام شد" if st["done"][i] else "⏳"
        lines.append(f"{mark} تحویل {n_txt} → 💰 {fmt_money(o['pay'])}")
        if not st["done"][i]:
            rows.append([(f"📦 تحویل سفارش {fn(i+1)} (+{fmt_money(o['pay'])}💰)", f"ord2:ok:{i}")])
    api.send_message(chat_id, "\n".join(lines), inline_keyboard(rows) if rows else None)


def empire_order_fulfill(chat_id, uid, idx):
    idx = int(idx)
    st = ensure_empire_orders(uid)
    if idx >= len(st["orders"]) or idx < 0:
        return "❌"
    if st["done"][idx]:
        return "✅ قبلاً انجام شده!"
    o = st["orders"][idx]
    r = ensure_resources(uid)
    need_txt = " + ".join(f"{v}{'🌾' if k=='food' else '⚒️' if k=='iron' else '💊'}" for k, v in o["need"].items())
    for k, v in o["need"].items():
        if r[k] < v:
            return f"📦 منابع کافی نیستی! نیاز: {need_txt}"
    for k, v in o["need"].items():
        db.execute(f"UPDATE resources SET {k}={k}-? WHERE user_id=?", (v, uid))
    st["done"][idx] = True
    db.execute("UPDATE eorders SET data=? WHERE user_id=? AND day=?", (jd(st), uid, today()))
    change_money(uid, o["pay"], "empire_order", "تحویل سفارش تاجر شهر")
    gain_xp(uid, 15)
    log_action(uid, "empire_order", str(o))
    return f"🎉 سفارش تحویل شد! {need_txt} رفت و +{fmt_money(o['pay'])} 💰 گرفتی (+۱۵⭐)"


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
        ok_c, fail_c, total = broadcast_to_all(text, header="📣 اطلاعیه رسمی:")
        log_action(uid, "announcement", f"{text[:40]} sent={ok_c}")
        set_state(uid)
        api.send_message(chat_id,
                         f"📣 اطلاعیه هم برای همه ارسال شد و در ربات ثبت شد.\n"
                         f"✅ {fn(ok_c)} موفق | ❌ {fn(fail_c)} ناموفق (از {fn(total)})", ADMIN_KB)
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
        if not text:
            api.send_message(chat_id, "⚠️ متن پیام پیدا نشد؛ دوباره از «📢 پیام همگانی» شروع کن.", ADMIN_KB)
            ans("⚠️"); return True
        ok_c, fail_c, total = broadcast_to_all(text)
        log_action(uid, "broadcast", f"sent={ok_c}")
        api.send_message(chat_id, f"📢 پیام همگانی: ✅ {fn(ok_c)} موفق | ❌ {fn(fail_c)} ناموفق (از {fn(total)})", ADMIN_KB)
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
    "🎡 سرگرمی": panel_fun,
    "🏙 شهر": panel_city,
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
        ref = None
        parts = text.split()
        if len(parts) > 1 and parts[1].startswith("ref_") and parts[1][4:].isdigit():
            cand = int(parts[1][4:])
            if cand != uid and db.fetchone("SELECT user_id FROM profiles WHERE user_id=?", (cand,)):
                ref = cand
        cmd_start(chat_id, uid, ref=ref)
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

    # 📢 ارسال همگانی سریع ادمین: /bc متن پیام
    if text.startswith("/bc ") and is_admin(uid):
        btext = text[4:].strip()
        if btext:
            ok_c, fail_c, total = broadcast_to_all(btext)
            log_action(uid, "broadcast_cmd", f"sent={ok_c}")
            api.send_message(chat_id, f"📢 ارسال شد: ✅ {fn(ok_c)} | ❌ {fn(fail_c)} (از {fn(total)})", ADMIN_KB)
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
    if not tg_user or not tg_user.get("id"):
        return
    uid = ensure_user(tg_user)   # کاربر حتی با کلیک اینلاین هم ثبت می‌شود (برای پیام همگانی)
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data") or ""
    cb_id = cb.get("id")
    if not (chat_id and data):
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

    # ── v5: سرگرمی/شهر/اقتصاد+ ──
    if data == "fun:lot":   api.answer_callback(cb_id); panel_lottery(chat_id, uid); return
    if data == "fun:arc":   api.answer_callback(cb_id); panel_arcade(chat_id, uid); return
    # 🎡 شهربازی مهارتی (بدون شرط‌بندی)
    if data == "mat:go":
        api.answer_callback(cb_id, "🧮")
        r = math_play(chat_id, uid)
        if r: api.send_message(chat_id, r)
        return
    if data.startswith("mat:a:"):
        api.answer_callback(cb_id, "🧮")
        api.send_message(chat_id, math_answer(chat_id, uid, data.split(":")[2])); return
    if data == "wrd:go":
        api.answer_callback(cb_id, "🔤")
        r = word_play(chat_id, uid)
        if r: api.send_message(chat_id, r)
        return
    if data == "mem:go":
        api.answer_callback(cb_id, "🧠")
        r = mem_play(chat_id, uid)
        if r: api.send_message(chat_id, r)
        return
    if data == "pnl:menu":  api.answer_callback(cb_id); panel_penalty(chat_id, uid); return
    if data.startswith("pnl:k:"):
        api.answer_callback(cb_id, "⚽")
        api.send_message(chat_id, penalty_kick(chat_id, uid, int(data.split(":")[2]))); return
    if data == "fun:twr":
        api.answer_callback(cb_id, "🧗")
        api.send_message(chat_id, tower_fight(chat_id, uid)); return
    if data == "fun:fort":
        api.answer_callback(cb_id, "🔮")
        api.send_message(chat_id, fortune_roll(chat_id, uid)); return
    if data == "fun:bty":   api.answer_callback(cb_id); panel_bounty(chat_id, uid); return
    if data == "lot:buy":
        api.answer_callback(cb_id, "🎟")
        api.send_message(chat_id, lottery_buy(chat_id, uid)); return
    if data == "bty:tg":    api.answer_callback(cb_id); bounty_targets(chat_id, uid); return
    if data.startswith("bty:t:"):
        api.answer_callback(cb_id); bounty_amount(chat_id, uid, int(data.split(":")[2])); return
    if data.startswith("bty:"):
        _, tgt, amt = data.split(":")
        api.answer_callback(cb_id, "🎯")
        api.send_message(chat_id, bounty_put(chat_id, uid, int(tgt), int(amt))); return
    if data == "cty:trv":   api.answer_callback(cb_id); panel_travel(chat_id, uid); return
    if data == "cty:edu":   api.answer_callback(cb_id); panel_education(chat_id, uid); return
    if data == "cty:ins":
        api.answer_callback(cb_id, "🏥")
        api.send_message(chat_id, insurance_buy(chat_id, uid)); return
    if data == "cty:news":  api.answer_callback(cb_id); panel_news(chat_id, uid); return
    if data == "cty:crim":
        api.answer_callback(cb_id, "🥷")
        api.send_message(chat_id, crime_do(chat_id, uid)); return
    if data == "cty:bail":
        api.answer_callback(cb_id, "🔓")
        api.send_message(chat_id, crime_bail(chat_id, uid)); return
    if data.startswith("trv:"):
        api.answer_callback(cb_id, "✈️")
        api.send_message(chat_id, travel_go(chat_id, uid, data.split(":")[1])); return
    if data == "edu:go":
        api.answer_callback(cb_id, "🎓")
        api.send_message(chat_id, edu_go(chat_id, uid)); return
    if data.startswith("tit:"):
        if data == "tit:list":
            api.answer_callback(cb_id); panel_titles(chat_id, uid); return
        api.answer_callback(cb_id, "📛")
        api.send_message(chat_id, title_buy(chat_id, uid, data.split(":")[1])); return
    if data == "eco:pf":    api.answer_callback(cb_id); panel_market(chat_id, uid); return
    if data == "eco:pawn":  api.answer_callback(cb_id); panel_pawn(chat_id, uid); return
    if data == "eco:signal":api.answer_callback(cb_id); panel_signal(chat_id, uid); return
    if data == "eco:pay":   api.answer_callback(cb_id); panel_pay_targets(chat_id, uid); return
    if data.startswith("pp:"):
        api.answer_callback(cb_id, "💰")
        api.send_message(chat_id, pawn_sell(chat_id, uid, int(data.split(":")[1]))); return
    if data.startswith("pay:"):
        parts = data.split(":")
        if len(parts) == 2:
            t = profile(int(parts[1]))
            rows = [[(f"{fmt_money(a)} 💰", f"pay:{parts[1]}:{a}") for a in (500, 2000, 10000)]]
            api.answer_callback(cb_id)
            api.send_message(chat_id, f"چقدر به {t['name'] if t else '؟'} بفرستی؟ (+۵٪ کارمزد)", inline_keyboard(rows))
        else:
            api.answer_callback(cb_id, "💸")
            api.send_message(chat_id, pay_user(chat_id, uid, int(parts[1]), parts[2]))
        return
    if data == "daily:claim":
        api.answer_callback(cb_id, "🔥")
        api.send_message(chat_id, streak_claim(chat_id, uid)); return
    if data == "achv:view": api.answer_callback(cb_id); panel_achievements(chat_id, uid); return
    if data == "emp:biz":   api.answer_callback(cb_id); panel_business(chat_id, uid); return
    if data.startswith("biz:"):
        api.answer_callback(cb_id, "🏭")
        api.send_message(chat_id, business_buy(chat_id, uid, data.split(":")[1])); return
    if data == "reb:ask":
        api.answer_callback(cb_id)
        api.send_message(chat_id,
                         "⭐ بازتولد یعنی: لول/پول/شغل از نو — ولی +۵٪ قدرت و حقوق ابدی (انباشته)!\n"
                         "💎 سکه‌ها، 👑 و لقبت حفظ می‌شود. مطمئنی؟",
                         inline_keyboard([[("⭐ بله، بازتولد!", "reb:ok"), ("❌ نه", "set:no")]]))
        return
    if data == "reb:ok":
        api.answer_callback(cb_id, "✨")
        api.send_message(chat_id, rebirth_do(chat_id, uid)); return
    if data == "ref:show":  api.answer_callback(cb_id); panel_referral(chat_id, uid); return

    # ──────── 🆕 v6: شهربازی مهارتی و قابلیت‌های جدید ────────
    if data == "qiz:play":  api.answer_callback(cb_id); quiz_next(chat_id, uid); return
    if data.startswith("qiz:a:"):
        api.answer_callback(cb_id, "🧩")
        r = quiz_answer(chat_id, uid, int(data.split(":")[2]))
        if r: api.send_message(chat_id, r)
        return
    if data == "xpl:go":
        api.answer_callback(cb_id, "🗺️")
        api.send_message(chat_id, explore_go(chat_id, uid)); return
    if data == "trs:view":  api.answer_callback(cb_id); panel_treasure(chat_id, uid); return
    if data == "trs:claim":
        api.answer_callback(cb_id, "🎁")
        api.send_message(chat_id, treasure_claim(chat_id, uid)); return
    if data == "gym:go":
        api.answer_callback(cb_id, "💪")
        api.send_message(chat_id, gym_go(chat_id, uid)); return
    if data == "far:menu":  api.answer_callback(cb_id); panel_farm(chat_id, uid); return
    if data.startswith("far:pl:"):
        api.answer_callback(cb_id); farm_plant_menu(chat_id, uid, data.split(":")[2]); return
    if data.startswith("far:bl:"):
        api.answer_callback(cb_id, "🌱")
        _, _, slot, crop = data.split(":")
        api.send_message(chat_id, farm_plant(chat_id, uid, slot, crop)); return
    if data.startswith("far:hv:"):
        api.answer_callback(cb_id, "🧺")
        api.send_message(chat_id, farm_harvest(chat_id, uid, data.split(":")[2])); return
    if data == "vlt:menu":  api.answer_callback(cb_id); panel_vault(chat_id, uid); return
    if data.startswith("vlt:up"):
        api.answer_callback(cb_id, "🔺")
        api.send_message(chat_id, vault_upgrade(chat_id, uid)); return
    if data.startswith("vlt:"):
        api.answer_callback(cb_id, "🧰")
        _, mode, kind = data.split(":")
        api.send_message(chat_id, vault_move(chat_id, uid, mode, kind)); return
    if data == "ele:menu":  api.answer_callback(cb_id); panel_election(chat_id, uid); return
    if data == "ele:join":
        api.answer_callback(cb_id, "🙋")
        api.send_message(chat_id, election_join(chat_id, uid)); return
    if data.startswith("ele:vote:"):
        api.answer_callback(cb_id, "🗳️")
        api.send_message(chat_id, election_vote(chat_id, uid, int(data.split(":")[2]))); return
    if data == "ele:salary":
        api.answer_callback(cb_id, "💼")
        api.send_message(chat_id, election_salary(chat_id, uid)); return
    if data == "plc:go":
        api.answer_callback(cb_id, "🚓")
        api.send_message(chat_id, police_patrol(chat_id, uid)); return
    if data == "wms:view":  api.answer_callback(cb_id); panel_weekly_missions(chat_id, uid); return
    if data.startswith("wms:cl:"):
        api.answer_callback(cb_id, "🎁")
        api.send_message(chat_id, weekly_claim(chat_id, uid, data.split(":")[2])); return
    if data == "prc:go":
        api.answer_callback(cb_id, "🏁")
        api.send_message(chat_id, pet_race(chat_id, uid)); return
    if data == "exc:menu":  api.answer_callback(cb_id); panel_exchange(chat_id, uid); return
    if data.startswith("exc:"):
        api.answer_callback(cb_id, "💱")
        _, side, n = data.split(":")
        api.send_message(chat_id, exchange_do(chat_id, uid, side, n)); return
    if data == "ads:list":  api.answer_callback(cb_id); panel_ads(chat_id, uid); return
    if data == "ads:mk":
        api.answer_callback(cb_id)
        r = ads_make_menu(chat_id, uid)
        if r: api.send_message(chat_id, r)
        return
    if data.startswith("ads:new:"):
        api.answer_callback(cb_id)
        r = ads_new(chat_id, uid, int(data.split(":")[2]))
        if r: api.send_message(chat_id, r)
        return
    if data.startswith("ads:buy:"):
        api.answer_callback(cb_id, "🛒")
        api.send_message(chat_id, ads_buy(chat_id, uid, int(data.split(":")[2]))); return
    if data == "ads:mine":  api.answer_callback(cb_id); panel_ads_mine(chat_id, uid); return
    if data.startswith("ads:del:"):
        api.answer_callback(cb_id, "🗑")
        api.send_message(chat_id, ads_delete(chat_id, uid, int(data.split(":")[2]))); return
    if data == "crf:menu":  api.answer_callback(cb_id); panel_craft(chat_id, uid); return
    if data.startswith("crf:a:"):
        api.answer_callback(cb_id)
        r = craft_pick_b(chat_id, uid, data.split(":")[2])
        if r: api.send_message(chat_id, r)
        return
    if data.startswith("crf:b:"):
        api.answer_callback(cb_id, "⚗️")
        _, _, a, b = data.split(":")
        api.send_message(chat_id, craft_do(chat_id, uid, a, b)); return
    if data == "rnt:collect":
        api.answer_callback(cb_id, "💵")
        api.send_message(chat_id, rent_collect(chat_id, uid)); return
    if data == "bdy:menu":  api.answer_callback(cb_id); panel_birthday(chat_id, uid); return
    if data == "bdy:set":   api.answer_callback(cb_id); birthday_set_ask(chat_id, uid); return
    if data == "bdy:claim":
        api.answer_callback(cb_id, "🥳")
        api.send_message(chat_id, birthday_claim(chat_id, uid)); return

    # ──────── 🆕 v7: پانزده قابلیت جدید ────────
    if data.startswith("bnk:lock:"):
        api.answer_callback(cb_id, "🔒")
        api.send_message(chat_id, lock_deposit(chat_id, uid, data.split(":")[2])); return
    if data == "bnk:unlock":
        api.answer_callback(cb_id, "🔓")
        api.send_message(chat_id, unlock_deposit(chat_id, uid)); return
    if data == "jli:board":  api.answer_callback(cb_id); panel_jail(chat_id, uid); return
    if data.startswith("jli:hi:"):
        api.answer_callback(cb_id, "🌹")
        api.send_message(chat_id, jail_visit(chat_id, uid, int(data.split(":")[2]))); return
    if data == "crs:menu":  api.answer_callback(cb_id); panel_courses(chat_id, uid); return
    if data.startswith("crs:buy:"):
        api.answer_callback(cb_id, "🎓")
        api.send_message(chat_id, course_buy(chat_id, uid, data.split(":")[2])); return
    if data == "ptr:go":
        api.answer_callback(cb_id, "🎾")
        api.send_message(chat_id, pet_train(chat_id, uid)); return
    if data.startswith("ptr:tal:"):
        api.answer_callback(cb_id, "🏅")
        api.send_message(chat_id, pet_talent_pick(chat_id, uid, data.split(":")[2])); return
    if data == "gqw:view":  api.answer_callback(cb_id); panel_gquest(chat_id, uid); return
    if data == "gqw:claim":
        api.answer_callback(cb_id, "💎")
        api.send_message(chat_id, gquest_claim(chat_id, uid)); return
    if data == "ftrip:go":
        api.answer_callback(cb_id, "🧳")
        api.send_message(chat_id, family_trip(chat_id, uid)); return
    if data == "ord2:menu": api.answer_callback(cb_id); panel_empire_orders(chat_id, uid); return
    if data.startswith("ord2:ok:"):
        api.answer_callback(cb_id, "📦")
        api.send_message(chat_id, empire_order_fulfill(chat_id, uid, data.split(":")[2])); return
    if data.startswith("grd:hire"):
        api.answer_callback(cb_id, "🛡")
        api.send_message(chat_id, guard_hire(chat_id, uid)); return
    if data.startswith("ele:tax:"):
        api.answer_callback(cb_id, "🏛")
        api.send_message(chat_id, mayor_set_tax(chat_id, uid, data.split(":")[2])); return
    if data.startswith("lb:"):
        api.answer_callback(cb_id, "🏆")
        mode_map = {"lb:money": "money", "lb:war": "war", "lb:guild": "guild", "lb:tower": "tower", "lb:pet": "pet"}
        panel_leaderboard_tabs(chat_id, uid, mode_map.get(data, "money")); return

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
║   بازی متنی شبیه‌ساز زندگی — نسخه ۶     ║
╚══════════════════════════════════════════╝
"""


# ─────────────── 🌐 کیپ‌الایو برای هاست‌های رایگان (Render / Phemeral / Koyeb...) ───────────────
def start_keepalive():
    """یک سرور HTTP کوچک روی پورت $PORT باز می‌کند تا هاست تصور کند وب‌سرویس داریم و ربات را خاموش نکند.
    روی هاست: همان لینکی که پنل می‌دهد را در UptimeRobot (رایگان) بگذار تا هر ۵ دقیقه پینگ بخورد."""
    port = int(os.getenv("PORT") or "8080")

    def _run():
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, body):
                body = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.startswith("/health"):
                    self._reply("OK")
                else:
                    self._reply("🤖 Life Simulator Bot برای بله آنلاین است!")

            def do_HEAD(self):
                self._reply("")

            def log_message(self, *args):
                pass

        try:
            srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
            log.info(f"🌐 کیپ‌الایو روی پورت {port} فعال شد (برای هاست‌هایی که health-check دارند)")
            srv.serve_forever()
        except Exception as e:
            log.warning(f"⚠️ کیپ‌الایو روی پورت {port} باز نشد: {e} (روی موبایل مهم نیست)")

    threading.Thread(target=_run, daemon=True).start()


def main():
    global api, db
    print(BANNER)

    start_keepalive()   # 🆕 v6: جلوگیری از خاموش شدن ربات روی هاست (پورت HTTP)

    if not BOT_TOKEN or BOT_TOKEN.startswith("PUT_YOUR"):
        print("❌ توکن ربات تنظیم نشده!\n\n"
              "   📱 روی گوشی: فایل main.py را توی ادیتور باز کن و در بخش تنظیمات (\n"
              "      خطوط اول فایل) جای PUT_YOUR_BALE_BOT_TOKEN_HERE توکن را بگذار.\n"
              "      مثل:  BOT_TOKEN = \"123456789:AAf3k...\"\n\n"
              "   💻 روی سرور: متغیر محیطی BALE_BOT_TOKEN را در تنظیمات هاست بگذار\n"
              "   ⏳ کیپ‌الایو فعال است — پنل هاست را باز نگه داشتم؛ همین‌جا می‌مانی تا توکن را بگذاری!")

        # روی هاست: سرویس را زنده نگه می‌داریم تا لاگ و health-check خراب نشود
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return

    _masked = BOT_TOKEN[:6] + "…" + BOT_TOKEN[-4:] if len(BOT_TOKEN) > 12 else "***"
    log.info(f"🔑 توکن تنظیم شده ({_masked}) | 🗂 دیتابیس: {DB_PATH}")

    db = Database(DB_PATH)
    log.info(f"💾 دیتابیس آماده شد: {DB_PATH}")

    api = BaleAPI(BOT_TOKEN)
    me = api.call("getMe")
    if not me:
        print("❌ اتصال به بله ناموفق بود!\n"
              "   موارد محتمل:\n"
              "   ۱) توکن اشتباه یا منقضی است → از ربات‌ساز بله دوباره بگیر\n"
              "   ۲) هاست/گوشی به tapi.bale.ai دسترسی ندارد (اینترنت/فیلترشکن)\n"
              "   ۳) IP هاست توسط بله محدود شده — یک هاست داخلی ایرانی امتحان کن")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return
    log.info(f"✅ ربات متصل شد: @{me.get('username')} ({me.get('first_name')})")
    log.info(f"👑 ادمین‌ها: {sorted({*ADMIN_IDS, *[r['user_id'] for r in db.fetchall('SELECT user_id FROM admins')]})}")
    log.info("🚀 ربات آنلاین است و پیام‌ها را می‌گیرد! (Ctrl+C برای توقف)")

    api.call("deleteWebhook")  # اطمینان از حالت polling
    while True:
        try:
            for update in api.poll():
                handle_update(update)
        except KeyboardInterrupt:
            print("\n👋 خداحافظ! ربات متوقف شد.")
            break
        except TokenError as e:
            log.error(f"🚫 {e} ربات متوقف می‌شود تا هاست مدام ری‌استارت نکند.")
            time.sleep(30)
            # سرویس را زنده نگه می‌داریم ولی polling متوقف است
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                break
        except Exception as e:
            log.exception(f"💥 خطای اصلی حلقه: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
