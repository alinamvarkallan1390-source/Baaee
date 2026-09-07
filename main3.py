#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Life Simulator AI — Rubika Edition
پورت روبیکایی بازی Life Simulator با Reply Keyboard معمولی.
تمام UI این فایل فقط دکمه‌های معمولی روبیکا است؛ Inline/Glass استفاده نشده.
"""
import os,time,random,sqlite3,threading,logging,shutil
from datetime import datetime,timedelta
import requests

TOKEN=os.getenv("RUBIKA_BOT_TOKEN","TEST_TOKEN_REPLACE_ME")
ADMIN_IDS={1975639269,558945434}
_env=os.getenv("RUBIKA_ADMIN_IDS","")
ADMIN_IDS|={int(x) for x in _env.replace(" ","").split(",") if x.isdigit()}
DB_PATH=os.getenv("LIFE_SIM_DB",os.path.join(os.path.dirname(os.path.abspath(__file__)),"life_simulator_rubika.db"))
VERSION="Rubika 2.0.0"
TEAM="Life Simulator"
WORK_CD=45; REST_CD=60; TRAIN_CD=30; MARKET_CD=1200
log=logging.getLogger("LifeSimRubika"); logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(message)s")
lock=threading.RLock()

# ----------------------------- API -----------------------------
class RubikaAPI:
    BASE="https://botapi.rubika.ir/v3"
    def __init__(self,token):
        self.token=token; self.s=requests.Session()
    def call(self,method,payload=None,timeout=40):
        try:
            r=self.s.post(f"{self.BASE}/{self.token}/{method}",json=payload or {},timeout=timeout)
            r.raise_for_status(); body=r.json()
            if isinstance(body,dict) and isinstance(body.get("data"),dict): return body["data"]
            return body if isinstance(body,dict) else {}
        except Exception as e:
            log.warning("Rubika API %s: %s",method,e); return {}
    def get_updates(self,offset=None):
        p={"limit":100}
        if offset: p["offset_id"]=offset
        return self.call("getUpdates",p,45)
    def send(self,chat_id,text,keyboard=None):
        p={"chat_id":str(chat_id),"text":str(text)[:4096]}
        if keyboard: p["chat_keypad_type"]="New"; p["chat_keypad"]={"rows":[{"buttons":[{"id":b,"type":"Simple","button_text":b} for b in row]} for row in keyboard],"resize_keyboard":True,"on_time_keyboard":False}
        return self.call("sendMessage",p)
    def edit(self,*a,**k): return None
api=RubikaAPI(TOKEN)

# ----------------------------- DB -----------------------------
def con():
    c=sqlite3.connect(DB_PATH,timeout=30,check_same_thread=False); c.row_factory=sqlite3.Row; return c

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".",exist_ok=True)
    with lock,con() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(uid TEXT PRIMARY KEY,name TEXT DEFAULT 'بازیکن',username TEXT DEFAULT '',age INTEGER DEFAULT 18,money INTEGER DEFAULT 100000000,bank INTEGER DEFAULT 0,energy INTEGER DEFAULT 100,health INTEGER DEFAULT 100,happiness INTEGER DEFAULT 70,intelligence INTEGER DEFAULT 50,strength INTEGER DEFAULT 50,charisma INTEGER DEFAULT 50,level INTEGER DEFAULT 1,xp INTEGER DEFAULT 0,gems INTEGER DEFAULT 0,job TEXT DEFAULT 'بیکار',company TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP,last_work REAL DEFAULT 0,last_rest REAL DEFAULT 0,last_train REAL DEFAULT 0,streak INTEGER DEFAULT 0,last_daily TEXT DEFAULT '',ref_by TEXT DEFAULT '',banned INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS inventory(uid TEXT,item TEXT,amount INTEGER DEFAULT 0,PRIMARY KEY(uid,item));
        CREATE TABLE IF NOT EXISTS market(symbol TEXT PRIMARY KEY,name TEXT,price INTEGER,prev INTEGER,updated REAL);
        CREATE TABLE IF NOT EXISTS companies(owner TEXT PRIMARY KEY,name TEXT,product TEXT,value INTEGER DEFAULT 0,employees INTEGER DEFAULT 1,shares INTEGER DEFAULT 0,listed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS stocks(uid TEXT,symbol TEXT,amount INTEGER DEFAULT 0,avg_price INTEGER DEFAULT 0,PRIMARY KEY(uid,symbol));
        CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,uid TEXT,kind TEXT,amount INTEGER DEFAULT 0,description TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT);
        ''')
        for s,n,p in [("TECH","فناوری",120000000),("FOOD","غذا",80000000),("AUTO","خودرو",150000000),("BANK","بانک",110000000),("ENERGY","انرژی",95000000)]: c.execute("INSERT OR IGNORE INTO market VALUES(?,?,?,?,?)",(s,n,p,p,time.time()))
        c.commit()

def get(uid):
    with lock,con() as c: r=c.execute("SELECT * FROM users WHERE uid=?",(str(uid),)).fetchone()
    return dict(r) if r else None

def ensure(uid,name="بازیکن",username=""):
    uid=str(uid)
    with lock,con() as c:
        if not c.execute("SELECT 1 FROM users WHERE uid=?",(uid,)).fetchone(): c.execute("INSERT INTO users(uid,name,username) VALUES(?,?,?)",(uid,name[:80],username[:80]))
        else: c.execute("UPDATE users SET name=?,username=? WHERE uid=?",(name[:80],username[:80],uid))
        c.commit()

def update(uid,**kw):
    if not kw:return
    with lock,con() as c:
        cols={r[1] for r in c.execute("PRAGMA table_info(users)")}; kw={k:v for k,v in kw.items() if k in cols}
        if kw: c.execute("UPDATE users SET "+",".join(f"{k}=?" for k in kw)+" WHERE uid=?",(*kw.values(),str(uid))); c.commit()

def log_action(uid,kind,amount=0,desc=""):
    with lock,con() as c: c.execute("INSERT INTO logs(uid,kind,amount,description) VALUES(?,?,?,?)",(str(uid),kind,int(amount),desc)); c.commit()

def money(uid,amount,kind="system",desc=""):
    p=get(uid)
    if not p:return
    new=max(0,p["money"]+int(amount)); update(uid,money=new); log_action(uid,kind,amount,desc)

def xp(uid,n):
    p=get(uid)
    if not p:return
    val=p["xp"]+int(n); lvl=p["level"]
    while val>=lvl*100:
        val-=lvl*100; lvl+=1; money(uid,lvl*100000,"level",f"Level {lvl}")
    update(uid,xp=val,level=lvl)

def fmt(n): return f"{int(n):,}".replace(",","٬")
def admin(uid): return int(uid) in ADMIN_IDS

def kb(*rows): return [list(r) for r in rows]
MAIN=kb(("👤 پروفایل","💰 اقتصاد"),("💼 کار و شغل","🏢 شرکت"),("📈 بازار بورس","⚔️ نبرد"),("🎁 روزانه","🎒 دارایی‌ها"),("🏆 رتبه‌بندی","ℹ️ راهنما"))
ECON=kb(("💵 موجودی","🏦 بانک"),("💸 انتقال","🔙 بازگشت"))
JOBS_KB=kb(("🔎 شغل‌ها","💼 کار کردن"),("📚 آموزش","🛌 استراحت"),("🔙 بازگشت",))
COMP=kb(("🏗 ساخت شرکت","📊 شرکت من"),("👷 استخدام","📈 عرضه سهام"),("🔙 بازگشت",))
MARKET=kb(("📊 قیمت‌ها","🛒 خرید سهم"),("💰 فروش سهم","📦 سهام من"),("🔙 بازگشت",))
BATTLE=kb(("⚔️ حمله تمرینی","🏆 رکورد نبرد"),("🔙 بازگشت",))
ADMIN=kb(("👥 آمار","📢 پیام همگانی"),("💰 جایزه همگانی","💾 بکاپ"),("🔙 خروج",))

# ----------------------------- GAME -----------------------------
JOBS={"کارگر":(800000,15),"راننده":(1200000,18),"فروشنده":(1500000,20),"برنامه‌نویس":(2500000,25),"مهندس":(3500000,25),"پزشک":(5000000,30),"کارآفرین":(7000000,30)}

def profile_text(uid):
    p=get(uid); return (f"👤 پروفایل\n━━━━━━━━━━\nنام: {p['name']}\nسن: {p['age']}\n💰 پول: {fmt(p['money'])}\n🏦 بانک: {fmt(p['bank'])}\n⚡ انرژی: {p['energy']}/100\n❤️ سلامت: {p['health']}/100\n😊 شادی: {p['happiness']}/100\n🧠 هوش: {p['intelligence']}\n💪 قدرت: {p['strength']}\n🗣 کاریزما: {p['charisma']}\n💼 شغل: {p['job']}\n⭐ Level: {p['level']} | XP: {p['xp']}\n💎 جم: {p['gems']}")

def work(uid):
    p=get(uid)
    if time.time()-p["last_work"]<WORK_CD:return "⏳ هنوز زمان شیفت بعدی نرسیده."
    if p["energy"]<20:return "⚡ انرژی کافی نداری؛ استراحت کن."
    salary,_=JOBS.get(p["job"],(500000,15)); inc=salary+random.randint(0,max(1,salary//5))
    update(uid,money=p["money"]+inc,energy=p["energy"]-20,happiness=max(0,p["happiness"]-1),last_work=time.time()); xp(uid,15); log_action(uid,"work",inc,p["job"])
    return f"💼 شیفت تمام شد!\n💰 +{fmt(inc)} تومان\n⚡ -۲۰ انرژی\n⭐ +۱۵ XP"

def rest(uid):
    p=get(uid)
    if time.time()-p["last_rest"]<REST_CD:return "⏳ کمی صبر کن."
    update(uid,energy=min(100,p["energy"]+40),health=min(100,p["health"]+5),happiness=min(100,p["happiness"]+5),last_rest=time.time())
    return "🛌 استراحت کردی!\n⚡ +۴۰ انرژی\n❤️ +۵ سلامت\n😊 +۵ شادی"

def train(uid):
    p=get(uid)
    if time.time()-p["last_train"]<TRAIN_CD:return "⏳ تمرین بعدی هنوز آماده نیست."
    if p["energy"]<15:return "⚡ انرژی کافی نداری."
    stat=random.choice(["intelligence","strength","charisma"]); update(uid,**{stat:p[stat]+2, "energy":p["energy"]-15,"last_train":time.time()}); xp(uid,10)
    names={"intelligence":"🧠 هوش","strength":"💪 قدرت","charisma":"🗣 کاریزما"}; return f"📚 تمرین موفق!\n{names[stat]} +۲\n⭐ XP +۱۰\n⚡ انرژی -۱۵"

def daily(uid):
    p=get(uid); day=datetime.now().strftime("%Y-%m-%d")
    if p["last_daily"]==day:return "🎁 جایزه امروز را قبلاً گرفتی."
    streak=p["streak"]+1; reward=500000+streak*100000; update(uid,money=p["money"]+reward,gems=p["gems"]+1,streak=streak,last_daily=day); xp(uid,25); return f"🎁 جایزه روزانه!\n💰 +{fmt(reward)}\n💎 +۱ جم\n🔥 استریک: {streak} روز"

def company_text(uid):
    with lock,con() as c:r=c.execute("SELECT * FROM companies WHERE owner=?",(str(uid),)).fetchone()
    if not r:return "🏢 شرکتی نداری. برای ساخت شرکت ۱ میلیارد تومان لازم است."
    return f"🏢 {r['name']}\nمحصول: {r['product']}\nارزش: {fmt(r['value'])}\n👷 کارمندان: {r['employees']}\n📈 سهام: {r['shares']}\nوضعیت: {'بورسی' if r['listed'] else 'خصوصی'}"

def create_company(uid):
    p=get(uid); cost=1_000_000_000
    if p["money"]<cost:return f"❌ سرمایه کافی نیست.\nلازم: {fmt(cost)}\nفعلی: {fmt(p['money'])}"
    with lock,con() as c:
        if c.execute("SELECT 1 FROM companies WHERE owner=?",(str(uid),)).fetchone():return "❌ قبلاً شرکت داری."
        name=f"شرکت {p['name'][:15]}"; product=random.choice(["فناوری","غذا","خودرو","انرژی","فین‌تک"]); c.execute("INSERT INTO companies(owner,name,product,value,employees) VALUES(?,?,?,?,1)",(str(uid),name,product,cost)); c.commit()
    update(uid,money=p["money"]-cost,company=name,company_value=cost); xp(uid,100); return f"🏢 شرکت ساخته شد!\nنام: {name}\nمحصول: {product}\nارزش: {fmt(cost)} تومان"

def hire(uid):
    p=get(uid)
    with lock,con() as c:r=c.execute("SELECT * FROM companies WHERE owner=?",(str(uid),)).fetchone()
    if not r:return "❌ اول شرکت بساز."
    cost=50_000_000*(r["employees"]+1)
    if p["money"]<cost:return f"💸 هزینه استخدام: {fmt(cost)} تومان"
    with lock,con() as c:c.execute("UPDATE companies SET employees=employees+1,value=value+? WHERE owner=?",(cost*3,str(uid)));c.commit()
    update(uid,money=p["money"]-cost,company_value=(p["company_value"] or 0)+cost*3); return f"👷 یک کارمند استخدام شد!\n💸 -{fmt(cost)}\n📈 ارزش شرکت افزایش یافت."

def list_company(uid):
    with lock,con() as c:r=c.execute("SELECT * FROM companies WHERE owner=?",(str(uid),)).fetchone()
    if not r:return "❌ شرکت نداری."
    if r["value"]<4_000_000_000:return f"🔒 ارزش شرکت باید حداقل ۴ میلیارد باشد.\nفعلی: {fmt(r['value'])}"
    with lock,con() as c:c.execute("UPDATE companies SET listed=1,shares=1000 WHERE owner=?",(str(uid),));c.commit()
    return "📈 شرکت وارد بورس شد! ۱۰۰۰ سهم ایجاد شد."

# ----------------------------- MARKET -----------------------------
def market_tick():
    with lock,con() as c:
        rows=c.execute("SELECT * FROM market").fetchall()
        if not rows:return
        if time.time()-rows[0]["updated"]<MARKET_CD:return
        for r in rows:
            price=max(1000,int(r["price"]*(1+random.uniform(-.08,.08)))); c.execute("UPDATE market SET prev=?,price=?,updated=? WHERE symbol=?",(r["price"],price,time.time(),r["symbol"]))
        c.commit()

def prices():
    market_tick()
    with lock,con() as c:rows=c.execute("SELECT * FROM market ORDER BY symbol").fetchall()
    return "📈 بازار شبیه‌سازی‌شده\n━━━━━━━━━━\n"+"\n".join(f"{r['symbol']} | {r['name']} | {fmt(r['price'])} تومان | {'📈' if r['price']>=r['prev'] else '📉'}" for r in rows)

def buy_stock(uid,sym,n):
    n=int(n); market_tick()
    with lock,con() as c:r=c.execute("SELECT * FROM market WHERE symbol=?",(sym.upper(),)).fetchone()
    if not r:return "❌ نماد پیدا نشد."
    p=get(uid); cost=int(r["price"]*n*1.02)
    if p["money"]<cost:return f"💸 سرمایه کافی نیست؛ نیاز: {fmt(cost)}"
    with lock,con() as c:
        old=c.execute("SELECT amount,avg_price FROM stocks WHERE uid=? AND symbol=?",(str(uid),sym.upper())).fetchone(); oldn=old["amount"] if old else 0; oldavg=old["avg_price"] if old else 0; total=oldn+n; avg=int(((oldn*oldavg)+(n*r["price"]))/total); c.execute("INSERT OR REPLACE INTO stocks VALUES(?,?,?,?)",(str(uid),sym.upper(),total,avg));c.commit()
    update(uid,money=p["money"]-cost); log_action(uid,"stock_buy",cost,sym.upper()); return f"🛒 خرید انجام شد!\n{sym.upper()} × {n}\n💸 -{fmt(cost)} تومان"

def sell_stock(uid,sym,n):
    n=int(n); sym=sym.upper()
    with lock,con() as c:r=c.execute("SELECT * FROM market WHERE symbol=?",(sym,)).fetchone(); h=c.execute("SELECT * FROM stocks WHERE uid=? AND symbol=?",(str(uid),sym)).fetchone()
    if not r or not h or h["amount"]<n:return "❌ سهام کافی نداری."
    gain=int(r["price"]*n*.98); left=h["amount"]-n
    with lock,con() as c:
        if left:c.execute("UPDATE stocks SET amount=? WHERE uid=? AND symbol=?",(left,str(uid),sym))
        else:c.execute("DELETE FROM stocks WHERE uid=? AND symbol=?",(str(uid),sym))
        c.commit()
    money(uid,gain,"stock_sell",sym); return f"💰 فروش انجام شد!\n{sym} × {n}\n💰 +{fmt(gain)} تومان"

def stocks(uid):
    with lock,con() as c:r=c.execute("SELECT symbol,amount,avg_price FROM stocks WHERE uid=? AND amount>0",(str(uid),)).fetchall()
    return "📦 سهام من\n\n"+("\n".join(f"{x['symbol']}: {x['amount']} سهم | میانگین {fmt(x['avg_price'])}" for x in r) if r else "هنوز سهمی نداری.")

# ----------------------------- BATTLE (تمرینی و غیرگرافیکی) -----------------------------
def battle(uid):
    p=get(uid)
    if p["energy"]<15:return "⚡ برای نبرد تمرینی ۱۵ انرژی لازم است."
    power=p["strength"]+p["charisma"]//2+p["level"]*5+random.randint(0,30); enemy=random.randint(40,150)
    update(uid,energy=p["energy"]-15)
    if power>=enemy:
        reward=200000+p["level"]*50000; money(uid,reward,"battle","training win"); xp(uid,20); return f"⚔️ نبرد تمرینی را بردی!\n💰 +{fmt(reward)}\n⭐ +۲۰ XP\n⚡ -۱۵ انرژی"
    xp(uid,5); return "⚔️ این دور را باختی، ولی تجربه گرفتی.\n⭐ +۵ XP"

# ----------------------------- ADMIN -----------------------------
def admin_stats():
    with lock,con() as c:n=c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]; total=c.execute("SELECT COALESCE(SUM(money),0) n FROM users").fetchone()["n"]; coo=c.execute("SELECT COUNT(*) n FROM companies").fetchone()["n"]
    return f"📊 آمار ربات\n👥 کاربران: {fmt(n)}\n💰 مجموع پول: {fmt(total)}\n🏢 شرکت‌ها: {fmt(coo)}"

def backup():
    target=DB_PATH+".backup"; shutil.copy2(DB_PATH,target); return target

def broadcast(text):
    with lock,con() as c:ids=[r[0] for r in c.execute("SELECT uid FROM users WHERE banned=0").fetchall()]
    ok=fail=0
    for uid in ids:
        if api.send(uid,text):ok+=1
        else:fail+=1
        time.sleep(.05)
    return ok,fail,len(ids)

# ----------------------------- COMMANDS + NORMAL KEYBOARD -----------------------------
def help_text():
    return (f"ℹ️ Life Simulator روبیکا — {VERSION}\n━━━━━━━━━━\nبا ۱۰۰ میلیون تومان شروع می‌کنی. شغل بگیر، کار کن، مهارت بساز، شرکت ایجاد کن و در بازار مجازی معامله کن.\n\nفرمان‌ها:\n/start\n/profile\n/job نام شغل\n/pay شناسه مبلغ\n/buy SYMBOL تعداد\n/sell SYMBOL تعداد\n/hire\n/admin (فقط ادمین)\n\nتمام منوها با دکمه معمولی کار می‌کنند.")

def process(uid,text,name="بازیکن",username=""):
    ensure(uid,name,username); text=(text or "").strip(); p=get(uid)
    if p["banned"]:return "⛔ دسترسی شما مسدود است.",MAIN
    if text in ("/start","شروع","/شروع"):return "🤖 به Life Simulator روبیکا خوش آمدی!\n\n💰 سرمایه شروع: ۱۰۰٬۰۰۰٬۰۰۰ تومان\nاز منوی زیر شروع کن 👇",MAIN
    if text in ("/profile","👤 پروفایل"):return profile_text(uid),MAIN
    if text=="💰 اقتصاد":return "💰 اقتصاد — یکی را انتخاب کن:",ECON
    if text=="💵 موجودی":return f"💰 نقد: {fmt(p['money'])}\n🏦 بانک: {fmt(p['bank'])}",ECON
    if text=="🏦 بانک":return "🏦 بانک\n\nفرمان سپرده: /deposit مبلغ\nفرمان برداشت: /withdraw مبلغ",ECON
    if text=="💸 انتقال":return "💸 انتقال\nفرمت: /pay شناسه مبلغ",ECON
    if text=="💼 کار و شغل":return "💼 شغل و کار — انتخاب کن:",JOBS_KB
    if text in ("🔎 شغل‌ها","/jobs"):
        return "🔎 شغل‌ها\n\n"+"\n".join(f"• {j} — {fmt(v[0])} تومان" for j,v in JOBS.items())+"\n\nانتخاب: /job نام شغل",JOBS_KB
    if text=="💼 کار کردن":return work(uid),JOBS_KB
    if text in ("📚 آموزش","📚 تمرین"):return train(uid),JOBS_KB
    if text=="🛌 استراحت":return rest(uid),JOBS_KB
    if text=="🏢 شرکت":return company_text(uid),COMP
    if text=="🏗 ساخت شرکت":return create_company(uid),COMP
    if text=="📊 شرکت من":return company_text(uid),COMP
    if text=="👷 استخدام":return hire(uid),COMP
    if text=="📈 عرضه سهام":return list_company(uid),COMP
    if text in ("📈 بازار بورس","📊 قیمت‌ها"):return prices(),MARKET
    if text=="🛒 خرید سهم":return "🛒 خرید سهم\nفرمت: /buy TECH 2",MARKET
    if text=="💰 فروش سهم":return "💰 فروش سهم\nفرمت: /sell TECH 2",MARKET
    if text=="📦 سهام من":return stocks(uid),MARKET
    if text=="⚔️ نبرد":return "⚔️ نبرد تمرینی\n\nبدون محتوای گرافیکی؛ برای بردن XP و جایزه داخل بازی.",BATTLE
    if text=="⚔️ حمله تمرینی":return battle(uid),BATTLE
    if text=="🏆 رکورد نبرد":
        with lock,con() as c:r=c.execute("SELECT COUNT(*) n,COALESCE(SUM(amount),0) s FROM logs WHERE uid=? AND kind='battle' AND amount>0",(str(uid),)).fetchone()
        return f"🏆 رکورد نبرد\nبردها: {r['n']}\nجوایز: {fmt(r['s'])}",BATTLE
    if text=="🎁 روزانه":return daily(uid),MAIN
    if text=="🎒 دارایی‌ها":return f"🎒 دارایی‌ها\n💎 جم: {p['gems']}\n🏢 شرکت: {p['company'] or 'نداری'}\n📈 سهام:\n{stocks(uid)}",MAIN
    if text=="🏆 رتبه‌بندی":
        with lock,con() as c:rs=c.execute("SELECT name,money,level FROM users ORDER BY money DESC LIMIT 10").fetchall()
        return "🏆 رتبه‌بندی\n\n"+"\n".join(f"{i}. {r['name']} — {fmt(r['money'])} — Lv.{r['level']}" for i,r in enumerate(rs,1)),MAIN
    if text=="ℹ️ راهنما":return help_text(),MAIN
    if text=="🔙 بازگشت":return "🔙 برگشتی به منوی اصلی.",MAIN
    if text=="/admin" and admin(uid):return "🛠 پنل مدیریت",ADMIN
    if admin(uid) and text=="👥 آمار":return admin_stats(),ADMIN
    if admin(uid) and text=="💾 بکاپ":
        path=backup(); return f"💾 بکاپ ساخته شد: {os.path.basename(path)}\nبرای ارسال فایل از پنل هاست استفاده کن.",ADMIN
    if admin(uid) and text=="📢 پیام همگانی":return "📢 پیام همگانی\nفرمت: /broadcast متن",ADMIN
    if admin(uid) and text=="💰 جایزه همگانی":return "💰 جایزه همگانی\nفرمت: /grant مبلغ",ADMIN
    if admin(uid) and text=="🔙 خروج":return "از پنل مدیریت خارج شدی.",MAIN
    parts=text.split()
    if parts and parts[0]=="/job":
        job=" ".join(parts[1:]);
        if job not in JOBS:return "❌ شغل پیدا نشد. /jobs را ببین.",JOBS_KB
        update(uid,job=job); return f"✅ شغل انتخاب شد: {job}\n💰 حقوق پایه: {fmt(JOBS[job][0])}",JOBS_KB
    if parts and parts[0]=="/pay" and len(parts)>=3:
        try:target=str(parts[1]);amt=int(parts[2])
        except:return "❌ مبلغ نامعتبر.",ECON
        if amt<=0 or target==str(uid):return "❌ انتقال نامعتبر.",ECON
        q=get(target)
        if not q:return "❌ کاربر مقصد پیدا نشد.",ECON
        if p["money"]<amt:return "❌ موجودی کافی نیست.",ECON
        money(uid,-amt,"transfer",target);money(target,amt,"transfer",str(uid));return f"✅ {fmt(amt)} تومان منتقل شد.",ECON
    if parts and parts[0]=="/buy" and len(parts)>=3:
        try:return buy_stock(uid,parts[1],int(parts[2])),MARKET
        except:return "❌ فرمت: /buy TECH 2",MARKET
    if parts and parts[0]=="/sell" and len(parts)>=3:
        try:return sell_stock(uid,parts[1],int(parts[2])),MARKET
        except:return "❌ فرمت: /sell TECH 2",MARKET
    if parts and parts[0]=="/hire":return hire(uid),COMP
    if parts and parts[0]=="/deposit" and len(parts)==2:
        try:a=int(parts[1])
        except:return "❌ مبلغ نامعتبر.",ECON
        if a<=0 or p["money"]<a:return "❌ موجودی کافی نیست.",ECON
        update(uid,money=p["money"]-a,bank=p["bank"]+a);return f"🏦 {fmt(a)} تومان به بانک رفت.",ECON
    if parts and parts[0]=="/withdraw" and len(parts)==2:
        try:a=int(parts[1])
        except:return "❌ مبلغ نامعتبر.",ECON
        if a<=0 or p["bank"]<a:return "❌ موجودی بانک کافی نیست.",ECON
        update(uid,money=p["money"]+a,bank=p["bank"]-a);return f"💵 {fmt(a)} تومان برداشت شد.",ECON
    if admin(uid) and parts and parts[0]=="/grant" and len(parts)==2:
        try:a=int(parts[1])
        except:return "❌ مبلغ نامعتبر.",ADMIN
        with lock,con() as c:ids=[x[0] for x in c.execute("SELECT uid FROM users WHERE banned=0").fetchall()]
        for x in ids:money(x,a,"admin_grant","broadcast reward")
        return f"💰 {fmt(a)} تومان به {len(ids)} کاربر اهدا شد.",ADMIN
    if admin(uid) and parts and parts[0]=="/broadcast" and len(parts)>=2:
        text=" ".join(parts[1:]);ok=fail=0
        with lock,con() as c:ids=[x[0] for x in c.execute("SELECT uid FROM users WHERE banned=0").fetchall()]
        for x in ids:
            if api.send(x,text):ok+=1
            else:fail+=1
        return f"📢 ارسال شد: ✅ {ok} | ❌ {fail}",ADMIN
    return "🤔 این گزینه را نشناختم. از دکمه‌های منو استفاده کن یا /help را بفرست.",MAIN

# ----------------------------- UPDATE PARSER -----------------------------
def parse_update(u):
    if not isinstance(u,dict):return None,None,"",""
    chat=u.get("chat_id") or u.get("chat",{}).get("chat_id")
    m=u.get("new_message") or u.get("message") or {}
    if not isinstance(m,dict):m={}
    text=m.get("text") or ""
    sender=m.get("sender_id") or m.get("sender",{}).get("user_id") or m.get("sender",{}).get("id")
    if not sender:sender=chat
    name=m.get("sender",{}).get("first_name") or m.get("sender",{}).get("name") or "بازیکن"
    username=m.get("sender",{}).get("username") or ""
    return chat or sender,sender,text,name,username

def run():
    init_db(); offset=None; log.info("Life Simulator Rubika %s started",VERSION)
    if TOKEN=="TEST_TOKEN_REPLACE_ME":log.warning("RUBIKA_BOT_TOKEN هنوز تستی است؛ توکن واقعی را در کد/متغیر محیطی قرار بده.")
    while True:
        try:
            res=api.get_updates(offset); updates=res.get("updates",[]) if isinstance(res,dict) else []
            if updates:
                nxt=res.get("next_offset_id")
                if nxt:offset=str(nxt)
                for u in updates:
                    parsed=parse_update(u)
                    if not parsed:continue
                    chat,uid,text,name,username=parsed
                    if not chat:continue
                    reply,k=process(uid,text,name,username); api.send(chat,reply,k)
            time.sleep(1)
        except KeyboardInterrupt:break
        except Exception as e:log.exception("loop error: %s",e);time.sleep(4)

if __name__=="__main__":run()
