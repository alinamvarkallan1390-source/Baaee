#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Life Simulator AI — Rubika Edition
نسخه روبیکایی بر پایه منطق Life Simulator پروژه Baaee.
UI فقط Reply Keyboard معمولی؛ بدون Inline/Glass buttons.
"""

import os
import json
import time
import random
import sqlite3
import threading
import logging
from datetime import datetime
from collections import defaultdict

try:
    import requests
except ImportError:
    raise SystemExit("requests is required: pip install requests")

# ================================================================
# تنظیمات
# ================================================================
RUBIKA_BOT_TOKEN = os.getenv("RUBIKA_BOT_TOKEN", "TEST_TOKEN_REPLACE_ME")
MY_ADMIN_IDS = [1975639269, 558945434]
_env_admins = os.getenv("RUBIKA_ADMIN_IDS", "")
ADMIN_IDS = set(MY_ADMIN_IDS) | {int(x) for x in _env_admins.replace(" ", "").split(",") if x.isdigit()}

DB_PATH = os.getenv("LIFE_SIM_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "life_simulator_rubika.db"))
BOT_VERSION = "Rubika 1.0.0"
TEAM_NAME = "Life Simulator"

RATE_LIMIT = 30
WORK_COOLDOWN = 45
REST_COOLDOWN = 60
EVENT_ENERGY_COST = 10
WORK_ENERGY_COST = 20
TRAIN_ENERGY_COST = 15
MARKET_INTERVAL = 1200
TRADE_FEE = 0.02
ATTACK_COOLDOWN = 300
ATTACK_ENERGY_COST = 25
BOSS_GEMS_REWARD = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ================================================================
# Rubika API
# ================================================================
class RubikaAPI:
    def __init__(self, token):
        self.token = token
        self.base = "https://botapi.rubika.ir/v3"
        self.session = requests.Session()

    def call(self, method, data=None):
        url = f"{self.base}/{self.token}/{method}"
        try:
            r = self.session.post(url, json=data or {}, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.exception("Rubika API error: %s", e)
            return {}

    def get_updates(self, offset=None):
        data = {}
        if offset is not None:
            data["offset_id"] = offset
        return self.call("getUpdates", data)

    def send_message(self, chat_id, text, keyboard=None):
        data = {"chat_id": chat_id, "text": str(text)}
        if keyboard:
            data["reply_markup"] = {"keyboard": keyboard, "resize_keyboard": True}
        return self.call("sendMessage", data)

    def send_text(self, chat_id, text, keyboard=None):
        return self.send_message(chat_id, text, keyboard)

api = RubikaAPI(RUBIKA_BOT_TOKEN)

# ================================================================
# دیتابیس
# ================================================================
_db_lock = threading.RLock()

def db():
    con = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with _db_lock, db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            uid TEXT PRIMARY KEY,
            username TEXT DEFAULT '',
            name TEXT DEFAULT 'بازیکن',
            age INTEGER DEFAULT 18,
            money INTEGER DEFAULT 100000000,
            bank INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 100,
            health INTEGER DEFAULT 100,
            happiness INTEGER DEFAULT 70,
            intelligence INTEGER DEFAULT 50,
            strength INTEGER DEFAULT 50,
            charisma INTEGER DEFAULT 50,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            gems INTEGER DEFAULT 0,
            job TEXT DEFAULT 'بیکار',
            company TEXT DEFAULT '',
            company_value INTEGER DEFAULT 0,
            ref_by TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_work REAL DEFAULT 0,
            last_rest REAL DEFAULT 0,
            last_attack REAL DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_daily TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS inventory (
            uid TEXT,
            item TEXT,
            amount INTEGER DEFAULT 0,
            PRIMARY KEY(uid,item)
        );
        CREATE TABLE IF NOT EXISTS market (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            price INTEGER,
            updated REAL
        );
        CREATE TABLE IF NOT EXISTS companies (
            owner TEXT PRIMARY KEY,
            name TEXT,
            product TEXT,
            value INTEGER DEFAULT 0,
            employees INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            listed INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS stocks (
            uid TEXT,
            symbol TEXT,
            amount INTEGER DEFAULT 0,
            PRIMARY KEY(uid,symbol)
        );
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            kind TEXT,
            amount INTEGER DEFAULT 0,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        seed_market(con)


def seed_market(con):
    rows = [
        ("TECH", "فناوری", 120000000),
        ("FOOD", "غذا", 80000000),
        ("AUTO", "خودرو", 150000000),
        ("BANK", "بانک", 110000000),
        ("ENERGY", "انرژی", 95000000),
    ]
    for s, n, p in rows:
        con.execute("INSERT OR IGNORE INTO market(symbol,name,price,updated) VALUES(?,?,?,?)", (s,n,p,time.time()))
    con.commit()


def row(uid):
    with _db_lock, db() as con:
        return con.execute("SELECT * FROM users WHERE uid=?", (str(uid),)).fetchone()


def profile(uid):
    r = row(uid)
    return dict(r) if r else None


def ensure_user(uid, name="بازیکن", username=""):
    uid = str(uid)
    with _db_lock, db() as con:
        r = con.execute("SELECT uid FROM users WHERE uid=?", (uid,)).fetchone()
        if not r:
            con.execute("INSERT INTO users(uid,name,username) VALUES(?,?,?)", (uid, name[:80], username[:80]))
            con.commit()
            return True
        con.execute("UPDATE users SET name=?, username=? WHERE uid=?", (name[:80], username[:80], uid))
        con.commit()
    return False


def update(uid, **fields):
    if not fields:
        return
    allowed = set([x[1] for x in db().execute("PRAGMA table_info(users)").fetchall()])
    fields = {k:v for k,v in fields.items() if k in allowed}
    if not fields:
        return
    sql = ", ".join(f"{k}=?" for k in fields)
    with _db_lock, db() as con:
        con.execute(f"UPDATE users SET {sql} WHERE uid=?", (*fields.values(), str(uid)))
        con.commit()


def change_money(uid, amount, kind="system", desc=""):
    with _db_lock, db() as con:
        con.execute("UPDATE users SET money=MAX(0,money+?) WHERE uid=?", (int(amount),str(uid)))
        con.execute("INSERT INTO logs(uid,kind,amount,description) VALUES(?,?,?,?)", (str(uid),kind,int(amount),desc))
        con.commit()


def xp(uid, amount):
    p = profile(uid)
    if not p:
        return
    value = p["xp"] + amount
    level = p["level"]
    while value >= level * 100:
        value -= level * 100
        level += 1
        change_money(uid, level * 100000, "level", f"ارتقای سطح به {level}")
    update(uid, xp=value, level=level)

# ================================================================
# منوی معمولی روبیکا
# ================================================================
MAIN_KB = [
    [{"text":"👤 پروفایل"}, {"text":"💰 اقتصاد"}],
    [{"text":"💼 کار و شغل"}, {"text":"🏢 شرکت"}],
    [{"text":"📈 بازار بورس"}, {"text":"⚔️ نبرد"}],
    [{"text":"🎁 روزانه"}, {"text":"🎒 دارایی‌ها"}],
    [{"text":"🏆 رتبه‌بندی"}, {"text":"ℹ️ راهنما"}],
]
ECONOMY_KB = [
    [{"text":"💵 موجودی"}, {"text":"🏦 بانک"}],
    [{"text":"💸 انتقال"}, {"text":"🔙 بازگشت"}],
]
JOB_KB = [
    [{"text":"🔎 انتخاب شغل"}, {"text":"💼 کار کردن"}],
    [{"text":"📚 آموزش"}, {"text":"🛌 استراحت"}],
    [{"text":"🔙 بازگشت"}],
]
COMPANY_KB = [
    [{"text":"🏗 ساخت شرکت"}, {"text":"📊 شرکت من"}],
    [{"text":"👷 استخدام"}, {"text":"📈 عرضه سهام"}],
    [{"text":"🔙 بازگشت"}],
]
MARKET_KB = [
    [{"text":"📊 قیمت‌ها"}, {"text":"🛒 خرید سهم"}],
    [{"text":"💰 فروش سهم"}, {"text":"📦 سهام من"}],
    [{"text":"🔙 بازگشت"}],
]


def menu_for(section="main"):
    return {"main":MAIN_KB,"economy":ECONOMY_KB,"jobs":JOB_KB,"company":COMPANY_KB,"market":MARKET_KB}.get(section, MAIN_KB)

# ================================================================
# بازی
# ================================================================
JOBS = {
    "کارگر": (800000, 15),
    "راننده": (1200000, 18),
    "فروشنده": (1500000, 20),
    "برنامه‌نویس": (2500000, 25),
    "مهندس": (3500000, 25),
    "پزشک": (5000000, 30),
    "کارآفرین": (7000000, 30),
}


def fmt(n):
    return f"{int(n):,}".replace(",", "٬")


def profile_text(uid):
    p = profile(uid)
    return (
        "👤 پروفایل زندگی شما\n\n"
        f"نام: {p['name']}\n"
        f"سن: {p['age']}\n"
        f"💰 پول: {fmt(p['money'])} تومان\n"
        f"🏦 بانک: {fmt(p['bank'])} تومان\n"
        f"⚡ انرژی: {p['energy']}/100\n"
        f"❤️ سلامت: {p['health']}/100\n"
        f"😊 شادی: {p['happiness']}/100\n"
        f"🧠 هوش: {p['intelligence']}\n"
        f"💪 قدرت: {p['strength']}\n"
        f"🗣 کاریزما: {p['charisma']}\n"
        f"💼 شغل: {p['job']}\n"
        f"⭐ سطح: {p['level']} | XP: {p['xp']}\n"
        f"💎 جم: {p['gems']}"
    )


def work(uid):
    p = profile(uid)
    if time.time() - p["last_work"] < WORK_COOLDOWN:
        return "⏳ هنوز زمان کار بعدی نرسیده."
    if p["energy"] < WORK_ENERGY_COST:
        return "⚡ انرژی کافی نداری. استراحت کن."
    salary, cost = JOBS.get(p["job"], (500000, 15))
    bonus = random.randint(0, max(1, salary // 5))
    income = salary + bonus
    update(uid, money=p["money"] + income, energy=max(0,p["energy"]-WORK_ENERGY_COST), last_work=time.time(), happiness=max(0,p["happiness"]-1))
    xp(uid, 15)
    return f"💼 شیفت کاری تمام شد!\n\n💰 درآمد: {fmt(income)} تومان\n⚡ انرژی: -{WORK_ENERGY_COST}\n⭐ XP: +15"


def rest(uid):
    p = profile(uid)
    if time.time() - p["last_rest"] < REST_COOLDOWN:
        return "⏳ کمی صبر کن تا دوباره استراحت کنی."
    energy = min(100, p["energy"] + 40)
    health = min(100, p["health"] + 5)
    update(uid, energy=energy, health=health, happiness=min(100,p["happiness"]+5), last_rest=time.time())
    return "🛌 استراحت کردی.\n\n⚡ انرژی +40\n❤️ سلامت +5\n😊 شادی +5"


def choose_job(uid, job):
    if job not in JOBS:
        return "❌ این شغل وجود ندارد."
    update(uid, job=job)
    return f"✅ شغل جدیدت شد: {job}\n💰 درآمد پایه هر شیفت: {fmt(JOBS[job][0])} تومان"


def company_text(uid):
    with _db_lock, db() as con:
        c = con.execute("SELECT * FROM companies WHERE owner=?", (str(uid),)).fetchone()
    if not c:
        return "🏢 هنوز شرکتی نداری.\n\nبرای ساخت شرکت حداقل ۱ میلیارد تومان لازم است."
    return (f"🏢 {c['name']}\n\nمحصول: {c['product']}\nارزش: {fmt(c['value'])} تومان\n"
            f"👷 کارمندان: {c['employees']}\n📈 سهام: {c['shares']}\n"
            f"وضعیت بورس: {'فعال' if c['listed'] else 'ثبت نشده'}")


def create_company(uid):
    p = profile(uid)
    cost = 1_000_000_000
    if p["money"] < cost:
        return f"❌ سرمایه کافی نیست.\nسرمایه لازم: {fmt(cost)} تومان\nسرمایه فعلی: {fmt(p['money'])} تومان"
    with _db_lock, db() as con:
        if con.execute("SELECT 1 FROM companies WHERE owner=?", (str(uid),)).fetchone():
            return "❌ تو قبلاً شرکت داری."
        name = f"شرکت {p['name'][:15]}"
        product = random.choice(["فناوری","مواد غذایی","خودرو","انرژی","فین‌تک"])
        con.execute("INSERT INTO companies(owner,name,product,value,employees) VALUES(?,?,?,?,?)", (str(uid),name,product,cost,1))
        con.commit()
    update(uid, money=p["money"]-cost, company=name, company_value=cost)
    xp(uid, 100)
    return f"🏢 شرکت با موفقیت ساخته شد!\n\nنام: {name}\nمحصول: {product}\nارزش اولیه: {fmt(cost)} تومان"

# ================================================================
# بازار بورس
# ================================================================
def market_update():
    with _db_lock, db() as con:
        rows = con.execute("SELECT * FROM market").fetchall()
        for r in rows:
            change = random.uniform(-0.08, 0.08)
            price = max(1000, int(r["price"] * (1 + change)))
            con.execute("UPDATE market SET price=?, updated=? WHERE symbol=?", (price,time.time(),r["symbol"]))
        con.commit()


def market_prices():
    with _db_lock, db() as con:
        rows = con.execute("SELECT * FROM market ORDER BY symbol").fetchall()
    if not rows:
        return "📈 بازار خالی است."
    if time.time() - rows[0]["updated"] >= MARKET_INTERVAL:
        market_update()
        with _db_lock, db() as con:
            rows = con.execute("SELECT * FROM market ORDER BY symbol").fetchall()
    return "📈 قیمت لحظه‌ای بازار\n\n" + "\n".join(f"{r['symbol']} — {r['name']}: 💰 {fmt(r['price'])}" for r in rows)

# ================================================================
# روزانه / رتبه‌بندی
# ================================================================
def daily(uid):
    p = profile(uid)
    today = datetime.now().strftime("%Y-%m-%d")
    if p["last_daily"] == today:
        return "🎁 جایزه روزانه امروزت رو قبلاً گرفتی."
    reward = 500000 + p["streak"] * 100000
    update(uid, money=p["money"]+reward, gems=p["gems"]+1, streak=p["streak"]+1, last_daily=today)
    xp(uid, 25)
    return f"🎁 جایزه روزانه دریافت شد!\n\n💰 +{fmt(reward)} تومان\n💎 +1 جم\n🔥 استریک: {p['streak']+1} روز"


def leaderboard():
    with _db_lock, db() as con:
        rows = con.execute("SELECT name,money,level FROM users ORDER BY money DESC LIMIT 10").fetchall()
    if not rows:
        return "🏆 هنوز بازیکنی ثبت نشده."
    return "🏆 ۱۰ ثروتمند برتر\n\n" + "\n".join(f"{i}. {r['name']} — 💰 {fmt(r['money'])} — Lv.{r['level']}" for i,r in enumerate(rows,1))

# ================================================================
# پردازش پیام
# ================================================================
def help_text():
    return (
        "ℹ️ راهنمای Life Simulator\n\n"
        "در این بازی از صفر شروع می‌کنی و می‌توانی ثروتمند شوی.\n\n"
        "👤 پروفایل — وضعیت زندگی\n"
        "💼 کار و شغل — انتخاب شغل، کار، آموزش و استراحت\n"
        "🏢 شرکت — ساخت و مدیریت شرکت\n"
        "📈 بازار بورس — قیمت‌ها و معاملات\n"
        "🎁 روزانه — جایزه و استریک\n"
        "⚔️ نبرد — سیستم مبارزه و باس\n"
        "🎒 دارایی‌ها — دارایی‌های بازی\n\n"
        "💡 هر کار روی انرژی اثر دارد؛ اقتصاد بازی بر پایه عرضه، تقاضا و ریسک طراحی شده است."
    )


def process(uid, text, name="بازیکن", username=""):
    ensure_user(uid, name, username)
    text = (text or "").strip()

    if text in ("/start", "/شروع", "شروع"):
        return (f"🤖 به Life Simulator روبیکا خوش آمدی!\n\n"
                "تو با 💰 ۱۰۰ میلیون تومان شروع می‌کنی.\n"
                "شغل بگیر، کار کن، سرمایه‌گذاری کن، شرکت بساز و وارد بورس شو!\n\n"
                "از دکمه‌های زیر استفاده کن 👇", MAIN_KB)
    if text in ("👤 پروفایل", "/profile"):
        return profile_text(uid), MAIN_KB
    if text == "💰 اقتصاد":
        return "💰 بخش اقتصاد\n\nیکی از گزینه‌ها را انتخاب کن:", ECONOMY_KB
    if text == "💵 موجودی":
        p=profile(uid); return f"💰 موجودی نقدی: {fmt(p['money'])} تومان\n🏦 بانک: {fmt(p['bank'])} تومان", ECONOMY_KB
    if text == "🏦 بانک":
        p=profile(uid); return f"🏦 موجودی بانک: {fmt(p['bank'])} تومان\n\nبرای واریز/برداشت می‌توانی در نسخه بعدی از فرمان‌های مربوط استفاده کنی.", ECONOMY_KB
    if text == "💸 انتقال":
        return "💸 انتقال پول\n\nفرمت: /pay شناسه مبلغ", ECONOMY_KB
    if text == "💼 کار و شغل":
        return "💼 سیستم شغل\n\nانتخاب کن:", JOB_KB
    if text == "🔎 انتخاب شغل":
        jobs="\n".join(f"• {j} — {fmt(v[0])} تومان" for j,v in JOBS.items())
        return "🔎 شغل‌های موجود:\n\n"+jobs+"\n\nبرای انتخاب: /job نام_شغل", JOB_KB
    if text == "💼 کار کردن": return work(uid), JOB_KB
    if text == "🛌 استراحت": return rest(uid), JOB_KB
    if text == "📚 آموزش":
        p=profile(uid)
        if p['energy'] < TRAIN_ENERGY_COST: return "⚡ انرژی کافی نداری.", JOB_KB
        update(uid, energy=p['energy']-TRAIN_ENERGY_COST, intelligence=p['intelligence']+2, xp=p['xp']+10)
        return "📚 آموزش انجام شد!\n🧠 هوش +2\n⭐ XP +10\n⚡ انرژی -15", JOB_KB
    if text == "🏢 شرکت": return company_text(uid), COMPANY_KB
    if text == "🏗 ساخت شرکت": return create_company(uid), COMPANY_KB
    if text == "📊 شرکت من": return company_text(uid), COMPANY_KB
    if text == "👷 استخدام":
        with _db_lock, db() as con:
            c=con.execute("SELECT * FROM companies WHERE owner=?",(str(uid),)).fetchone()
        if not c: return "❌ اول شرکت بساز.", COMPANY_KB
        return "👷 برای استخدام ۱ کارمند، ۵۰ میلیون تومان هزینه می‌شود.\nفرمان: /hire", COMPANY_KB
    if text == "📈 عرضه سهام":
        with _db_lock, db() as con:
            c=con.execute("SELECT * FROM companies WHERE owner=?",(str(uid),)).fetchone()
            if not c: return "❌ شرکت نداری.", COMPANY_KB
            if c['value'] < 4_000_000_000: return f"❌ ارزش شرکت هنوز کافی نیست.\nارزش فعلی: {fmt(c['value'])}\nحداقل: ۴ میلیارد تومان", COMPANY_KB
            con.execute("UPDATE companies SET listed=1,shares=1000 WHERE owner=?",(str(uid),)); con.commit()
        return "📈 شرکت با موفقیت وارد بازار سهام شد!\n۱۰۰۰ سهم برای معامله ایجاد شد.", COMPANY_KB
    if text == "📈 بازار بورس": return market_prices(), MARKET_KB
    if text == "📊 قیمت‌ها": return market_prices(), MARKET_KB
    if text == "🛒 خرید سهم": return "🛒 خرید سهم\n\nفرمت: /buy SYMBOL AMOUNT", MARKET_KB
    if text == "💰 فروش سهم": return "💰 فروش سهم\n\nفرمت: /sell SYMBOL AMOUNT", MARKET_KB
    if text == "📦 سهام من":
        with _db_lock, db() as con: rows=con.execute("SELECT symbol,amount FROM stocks WHERE uid=? AND amount>0",(str(uid),)).fetchall()
        return "📦 سهام من\n\n" + ("\n".join(f"{r['symbol']}: {r['amount']} سهم" for r in rows) if rows else "هنوز سهمی نداری."), MARKET_KB
    if text == "🎁 روزانه": return daily(uid), MAIN_KB
    if text == "🏆 رتبه‌بندی": return leaderboard(), MAIN_KB
    if text == "ℹ️ راهنما": return help_text(), MAIN_KB
    if text == "🎒 دارایی‌ها":
        p=profile(uid); return f"🎒 دارایی‌ها\n\n💰 پول: {fmt(p['money'])}\n🏦 بانک: {fmt(p['bank'])}\n💎 جم: {p['gems']}\n🏢 ارزش شرکت: {fmt(p['company_value'])}", MAIN_KB
    if text == "⚔️ نبرد": return "⚔️ بخش نبرد\n\nدر نسخه اصلی سیستم حمله و باس وجود دارد.\nبرای حمله: /attack", MAIN_KB
    if text == "🔙 بازگشت": return "🏠 منوی اصلی", MAIN_KB

    parts=text.split()
    if parts and parts[0] == "/job" and len(parts)>1:
        return choose_job(uid, " ".join(parts[1:])), JOB_KB
    if parts and parts[0] == "/pay" and len(parts)==3:
        try:
            target=str(parts[1]); amount=int(parts[2]); p=profile(uid)
            if amount<=0 or p['money']<amount: return "❌ مبلغ نامعتبر یا موجودی ناکافی.", ECONOMY_KB
            if not profile(target): return "❌ کاربر مقصد پیدا نشد.", ECONOMY_KB
            change_money(uid,-amount,"transfer",f"انتقال به {target}"); change_money(target,amount,"transfer",f"از {uid}")
            return f"✅ {fmt(amount)} تومان منتقل شد.", ECONOMY_KB
        except ValueError: pass
    if parts and parts[0] == "/hire":
        with _db_lock, db() as con:
            c=con.execute("SELECT * FROM companies WHERE owner=?",(str(uid),)).fetchone()
            if not c: return "❌ شرکت نداری.", COMPANY_KB
            cost=50_000_000; p=profile(uid)
            if p['money']<cost: return "❌ پول کافی نیست.", COMPANY_KB
            con.execute("UPDATE companies SET employees=employees+1,value=value+75000000 WHERE owner=?",(str(uid),)); con.commit()
        update(uid,money=p['money']-cost,company_value=p['company_value']+75_000_000)
        return "👷 استخدام موفق!\n💰 هزینه: ۵۰ میلیون\n📈 ارزش شرکت +۷۵ میلیون", COMPANY_KB
    return "❓ این دستور شناخته نشد. از دکمه‌های منو استفاده کن یا ℹ️ راهنما را بزن.", MAIN_KB

# ================================================================
# استخراج آپدیت روبیکا
# ================================================================
def extract_updates(data):
    return data.get("data", {}).get("updates", []) if isinstance(data,dict) else []


def extract_message(upd):
    msg = upd.get("new_message") or upd.get("message") or upd.get("inline_message") or {}
    if not isinstance(msg, dict): return None
    chat_id = msg.get("chat_id") or msg.get("object_guid")
    text = msg.get("text") or ""
    sender = msg.get("sender_id") or msg.get("author_object_guid") or ""
    name = "بازیکن"
    username = ""
    sender_obj = msg.get("sender") or msg.get("author") or {}
    if isinstance(sender_obj,dict):
        name = sender_obj.get("first_name") or sender_obj.get("name") or name
        username = sender_obj.get("username") or ""
    return chat_id, str(sender), str(text), str(name), str(username)


def handle_update(upd):
    item=extract_message(upd)
    if not item: return
    chat_id, uid, text, name, username=item
    if not chat_id: return
    try:
        response, keyboard=process(uid,text,name,username)
        api.send_message(chat_id,response,keyboard)
    except Exception:
        logging.exception("Handler failure")
        api.send_message(chat_id,"❌ خطایی رخ داد. لطفاً دوباره امتحان کن.",MAIN_KB)


def run():
    init_db()
    logging.info("Life Simulator Rubika started — %s", BOT_VERSION)
    offset=None
    while True:
        try:
            data=api.get_updates(offset)
            for upd in extract_updates(data):
                try:
                    offset=upd.get("update_id") or upd.get("message_id") or offset
                    handle_update(upd)
                except Exception:
                    logging.exception("Update failure")
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception:
            logging.exception("Polling failure")
            time.sleep(5)


if __name__ == "__main__":
    run()
