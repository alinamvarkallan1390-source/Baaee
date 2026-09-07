#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Life Simulator — Rubika full game edition.
UI is intentionally Reply Keyboard only: no inline/glass buttons.
"""
import os,time,random,sqlite3,threading,logging,shutil
from datetime import datetime
import requests

TOKEN=os.getenv("RUBIKA_BOT_TOKEN","TEST_TOKEN_REPLACE_ME")
ADMIN_IDS={1975639269,558945434}
ADMIN_IDS|={int(x) for x in os.getenv("RUBIKA_ADMIN_IDS","").replace(" ","").split(",") if x.isdigit()}
DB=os.getenv("LIFE_SIM_DB",os.path.join(os.path.dirname(os.path.abspath(__file__)),"life_simulator_rubika.db"))
LOCK=threading.RLock(); logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s"); log=logging.getLogger("life-rubika")
WORK_CD=45; REST_CD=60; TRAIN_CD=30; DAILY_CD=86400; MARKET_CD=1200
JOBS={"کارگر":(800000,15),"راننده":(1200000,18),"فروشنده":(1500000,20),"برنامه‌نویس":(2500000,25),"مهندس":(3500000,25),"پزشک":(5000000,30),"کارآفرین":(7000000,30)}
PRODUCTS=["فناوری","غذا","خودرو","انرژی","فین‌تک","پوشاک"]

class Rubika:
    BASE="https://botapi.rubika.ir/v3"
    def __init__(self,t): self.t=t; self.s=requests.Session()
    def call(self,m,p=None,timeout=45):
        try:
            r=self.s.post(f"{self.BASE}/{self.t}/{m}",json=p or {},timeout=timeout); r.raise_for_status(); x=r.json(); return x.get("data",x) if isinstance(x,dict) else {}
        except Exception as e: log.warning("%s: %s",m,e); return {}
    def updates(self,offset=None):
        p={"limit":100};
        if offset:p["offset_id"]=offset
        return self.call("getUpdates",p)
    def send(self,chat,text,kb=None):
        p={"chat_id":str(chat),"text":str(text)[:4096]}
        if kb:
            p["chat_keypad_type"]="New"; p["chat_keypad"]={"rows":[{"buttons":[{"id":b,"type":"Simple","button_text":b} for b in row]} for row in kb],"resize_keyboard":True}
        return bool(self.call("sendMessage",p))
api=Rubika(TOKEN)

def db():
    c=sqlite3.connect(DB,timeout=30,check_same_thread=False); c.row_factory=sqlite3.Row; return c

def init():
    os.makedirs(os.path.dirname(DB) or ".",exist_ok=True)
    with LOCK,db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS users(uid TEXT PRIMARY KEY,name TEXT,username TEXT DEFAULT '',money INTEGER DEFAULT 100000000,bank INTEGER DEFAULT 0,energy INTEGER DEFAULT 100,health INTEGER DEFAULT 100,happiness INTEGER DEFAULT 70,intelligence INTEGER DEFAULT 50,strength INTEGER DEFAULT 50,charisma INTEGER DEFAULT 50,job TEXT DEFAULT 'بیکار',level INTEGER DEFAULT 1,xp INTEGER DEFAULT 0,gems INTEGER DEFAULT 0,streak INTEGER DEFAULT 0,last_daily TEXT DEFAULT '',last_work REAL DEFAULT 0,last_rest REAL DEFAULT 0,last_train REAL DEFAULT 0,ref_by TEXT DEFAULT '',ref_count INTEGER DEFAULT 0,ref_earned INTEGER DEFAULT 0,banned INTEGER DEFAULT 0,created REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS inventory(uid TEXT,item TEXT,amount INTEGER DEFAULT 0,PRIMARY KEY(uid,item));
CREATE TABLE IF NOT EXISTS market(symbol TEXT PRIMARY KEY,name TEXT,price INTEGER,prev INTEGER,updated REAL,trend REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS stocks(uid TEXT,symbol TEXT,amount INTEGER DEFAULT 0,avg_price INTEGER DEFAULT 0,PRIMARY KEY(uid,symbol));
CREATE TABLE IF NOT EXISTS companies(owner TEXT PRIMARY KEY,name TEXT,product TEXT,value INTEGER DEFAULT 0,employees INTEGER DEFAULT 1,shares INTEGER DEFAULT 0,listed INTEGER DEFAULT 0,share_price INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,uid TEXT,kind TEXT,amount INTEGER DEFAULT 0,description TEXT,created REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT);''')
        for s,n,p in [("TECH","فناوری",120000000),("FOOD","غذا",80000000),("AUTO","خودرو",150000000),("BANK","بانک",110000000),("ENERGY","انرژی",95000000)]: c.execute("INSERT OR IGNORE INTO market(symbol,name,price,prev,updated) VALUES(?,?,?,?,?)",(s,n,p,p,time.time()))
        c.commit()

def q(sql,args=()):
    with LOCK,db() as c:return c.execute(sql,args).fetchall()
def one(sql,args=()):
    with LOCK,db() as c:r=c.execute(sql,args).fetchone(); return dict(r) if r else None

def ensure(uid,name="بازیکن",username=""):
    uid=str(uid); r=one("SELECT uid FROM users WHERE uid=?",(uid,))
    with LOCK,db() as c:
        if not r:c.execute("INSERT INTO users(uid,name,username,created) VALUES(?,?,?,?,?)"[:0],())
    # explicit insert avoids schema-dependent shortcuts
    if not r:
        with LOCK,db() as c:c.execute("INSERT INTO users(uid,name,username,created) VALUES(?,?,?,?)",(uid,name[:80],username[:80],time.time()));c.commit()
    else:
        with LOCK,db() as c:c.execute("UPDATE users SET name=?,username=? WHERE uid=?",(name[:80],username[:80],uid));c.commit()

def get(uid): return one("SELECT * FROM users WHERE uid=?",(str(uid),))
def upd(uid,**kw):
    if not kw:return
    with LOCK,db() as c:c.execute("UPDATE users SET "+",".join(k+"=?" for k in kw)+" WHERE uid=?",(*kw.values(),str(uid)));c.commit()
def logit(uid,kind,amount=0,desc=""):
    with LOCK,db() as c:c.execute("INSERT INTO logs(uid,kind,amount,description,created) VALUES(?,?,?,?,?)",(str(uid),kind,int(amount),desc,time.time()));c.commit()
def addmoney(uid,n,kind="system",desc=""):
    p=get(uid); 
    if p: upd(uid,money=max(0,p["money"]+int(n)));logit(uid,kind,n,desc)
def fmt(n):return f"{int(n):,}".replace(",","٬")
def admin(uid):return int(uid) in ADMIN_IDS

def gainxp(uid,n):
    p=get(uid); xp=p["xp"]+int(n); lvl=p["level"]
    while xp>=lvl*100:xp-=lvl*100;lvl+=1;addmoney(uid,lvl*100000,"level",str(lvl))
    upd(uid,xp=xp,level=lvl)

def keys(*rows):return [list(x) for x in rows]
MAIN=keys(("👤 پروفایل","💰 اقتصاد"),("💼 کار و شغل","🏢 شرکت"),("📈 بازار بورس","⚔️ نبرد"),("🎁 روزانه","🎒 دارایی‌ها"),("👥 دعوت دوستان","🏆 رتبه‌بندی"),("🎲 رویداد","ℹ️ راهنما"))
ECON=keys(("💵 موجودی","🏦 بانک"),("💸 انتقال","🎁 موجودی هدیه"),("🔙 بازگشت",))
JOB=keys(("🔎 شغل‌ها","💼 کار کردن"),("📚 آموزش","🛌 استراحت"),("🔙 بازگشت",))
COMP=keys(("🏗 ساخت شرکت","📊 شرکت من"),("👷 استخدام","📈 عرضه سهام"),("💼 درآمد شرکت","🔙 بازگشت"))
MKT=keys(("📊 قیمت‌ها","🛒 خرید سهم"),("💰 فروش سهم","📦 سهام من"),("🔙 بازگشت",))
BAT=keys(("⚔️ نبرد تمرینی","👹 باس روزانه"),("🏆 رکورد نبرد","🔙 بازگشت",))
ADM=keys(("👥 آمار","📢 پیام همگانی"),("💰 جایزه همگانی","💾 بکاپ"),("🚫 مدیریت مسدودی","🔙 خروج"))

def profile(uid):
 p=get(uid);return f"👤 پروفایل\n━━━━━━━━━━\nنام: {p['name']}\n💰 پول: {fmt(p['money'])}\n🏦 بانک: {fmt(p['bank'])}\n⚡ انرژی: {p['energy']}/100\n❤️ سلامت: {p['health']}/100\n😊 شادی: {p['happiness']}/100\n🧠 هوش: {p['intelligence']}\n💪 قدرت: {p['strength']}\n🗣 کاریزما: {p['charisma']}\n💼 شغل: {p['job']}\n⭐ سطح: {p['level']} | XP: {p['xp']}\n💎 جم: {p['gems']}\n👥 دعوت موفق: {p['ref_count']}"

def work(uid):
 p=get(uid)
 if time.time()-p["last_work"]<WORK_CD:return "⏳ هنوز زمان کار بعدی نرسیده."
 if p["energy"]<20:return "⚡ انرژی کافی نداری."
 salary,_=JOBS.get(p["job"],(500000,15));inc=salary+random.randint(0,salary//5);upd(uid,money=p["money"]+inc,energy=p["energy"]-20,happiness=max(0,p["happiness"]-1),last_work=time.time());gainxp(uid,15);logit(uid,"work",inc,p["job"]);return f"💼 شیفت تمام شد!\n💰 +{fmt(inc)} تومان\n⚡ -۲۰ انرژی\n⭐ +۱۵ XP"

def rest(uid):
 p=get(uid)
 if time.time()-p["last_rest"]<REST_CD:return "⏳ کمی صبر کن."
 upd(uid,energy=min(100,p["energy"]+40),health=min(100,p["health"]+5),happiness=min(100,p["happiness"]+5),last_rest=time.time());return "🛌 استراحت کردی!\n⚡ +۴۰ انرژی\n❤️ +۵ سلامت\n😊 +۵ شادی"

def train(uid):
 p=get(uid)
 if time.time()-p["last_train"]<TRAIN_CD:return "⏳ تمرین بعدی آماده نیست."
 if p["energy"]<15:return "⚡ انرژی کافی نداری."
 st=random.choice(["intelligence","strength","charisma"]);upd(uid,**{st:p[st]+2,"energy":p["energy"]-15,"last_train":time.time()});gainxp(uid,10);return f"📚 تمرین موفق!\n📈 {st} +۲\n⭐ XP +۱۰"

def daily(uid):
 p=get(uid);d=datetime.now().strftime("%Y-%m-%d")
 if p["last_daily"]==d:return "🎁 جایزه امروز را قبلاً گرفتی."
 streak=p["streak"]+1;reward=500000+streak*100000;upd(uid,money=p["money"]+reward,gems=p["gems"]+1,streak=streak,last_daily=d);gainxp(uid,25);return f"🎁 جایزه روزانه!\n💰 +{fmt(reward)}\n💎 +۱ جم\n🔥 استریک: {streak}"

def company(uid):
 r=one("SELECT * FROM companies WHERE owner=?",(str(uid),))
 if not r:return "🏢 شرکتی نداری.\n\nساخت شرکت: ۱ میلیارد تومان"
 return f"🏢 {r['name']}\nمحصول: {r['product']}\nارزش: {fmt(r['value'])}\n👷 کارکنان: {r['employees']}\n📈 سهام: {r['shares']}\n💹 قیمت سهم: {fmt(r['share_price']) if r['share_price'] else 'ثبت نشده'}\nوضعیت: {'بورسی' if r['listed'] else 'خصوصی'}"

def make_company(uid):
 p=get(uid);cost=1000000000
 if p["money"]<cost:return f"❌ سرمایه کافی نیست.\nلازم: {fmt(cost)}"
 if one("SELECT owner FROM companies WHERE owner=?",(str(uid),)):return "❌ شرکت داری."
 name=f"شرکت {p['name'][:18]}";prod=random.choice(PRODUCTS)
 with LOCK,db() as c:c.execute("INSERT INTO companies(owner,name,product,value,employees) VALUES(?,?,?,?,1)",(str(uid),name,prod,cost));c.commit()
 upd(uid,money=p["money"]-cost);gainxp(uid,100);return f"🏢 شرکت ساخته شد!\n{name}\nمحصول: {prod}\nارزش: {fmt(cost)}"

def hire(uid):
 c=one("SELECT * FROM companies WHERE owner=?",(str(uid),));p=get(uid)
 if not c:return "❌ اول شرکت بساز."
 cost=50000000*(c["employees"]+1)
 if p["money"]<cost:return f"❌ هزینه استخدام: {fmt(cost)}"
 with LOCK,db() as x:x.execute("UPDATE companies SET employees=employees+1,value=value+? WHERE owner=?",(cost*3,str(uid)));x.commit()
 upd(uid,money=p["money"]-cost);return f"👷 استخدام موفق!\n💸 -{fmt(cost)}\n📈 ارزش شرکت +{fmt(cost*3)}"

def list_company(uid):
 c=one("SELECT * FROM companies WHERE owner=?",(str(uid),))
 if not c:return "❌ شرکت نداری."
 if c["value"]<4000000000:return f"🔒 حداقل ارزش برای بورس: ۴ میلیارد\nفعلی: {fmt(c['value'])}"
 price=max(100000,int(c["value"]//1000))
 with LOCK,db() as x:x.execute("UPDATE companies SET listed=1,shares=1000,share_price=? WHERE owner=?",(price,str(uid)));x.commit()
 return f"📈 شرکت وارد بورس شد!\n۱۰۰۰ سهم\nقیمت اولیه: {fmt(price)} تومان"

def company_income(uid):
 c=one("SELECT * FROM companies WHERE owner=?",(str(uid),))
 if not c:return "❌ شرکت نداری."
 inc=c["employees"]*random.randint(1000000,3000000);addmoney(uid,inc,"company_income",c["name"]);return f"💼 درآمد شرکت دریافت شد!\n💰 +{fmt(inc)} تومان"

def tick():
 with LOCK,db() as c:
  rs=c.execute("SELECT * FROM market").fetchall()
  if not rs:return
  if time.time()-rs[0]["updated"]<MARKET_CD:return
  for r in rs:
   ch=random.uniform(-.12,.12);price=max(1000,int(r["price"]*(1+ch)));c.execute("UPDATE market SET prev=?,price=?,updated=?,trend=? WHERE symbol=?",(r["price"],price,time.time(),ch,r["symbol"]))
  c.commit()

def market():
 tick();rs=q("SELECT * FROM market ORDER BY symbol");return "📈 بازار مجازی\n━━━━━━━━━━\n"+"\n".join(f"{r['symbol']} | {r['name']} | {fmt(r['price'])} | {'📈' if r['price']>=r['prev'] else '📉'}" for r in rs)

def buy(uid,sym,n):
 try:n=int(n)
 except:return "❌ تعداد نامعتبر."
 if n<=0 or n>100000:return "❌ تعداد نامعتبر."
 tick();r=one("SELECT * FROM market WHERE symbol=?",(sym.upper(),))
 if not r:return "❌ نماد پیدا نشد."
 p=get(uid);cost=int(r["price"]*n*1.02)
 if p["money"]<cost:return f"❌ موجودی کافی نیست: {fmt(cost)}"
 h=one("SELECT * FROM stocks WHERE uid=? AND symbol=?",(str(uid),sym.upper()));old=h["amount"] if h else 0;avg=h["avg_price"] if h else 0;total=old+n;newavg=((old*avg)+(n*r["price"]))//total
 with LOCK,db() as c:c.execute("INSERT OR REPLACE INTO stocks VALUES(?,?,?,?)",(str(uid),sym.upper(),total,newavg));c.commit()
 upd(uid,money=p["money"]-cost);logit(uid,"buy",-cost,sym.upper());return f"🛒 خرید انجام شد!\n{sym.upper()} × {n}\n💸 -{fmt(cost)} تومان"

def sell(uid,sym,n):
 try:n=int(n)
 except:return "❌ تعداد نامعتبر."
 sym=sym.upper();r=one("SELECT * FROM market WHERE symbol=?",(sym,));h=one("SELECT * FROM stocks WHERE uid=? AND symbol=?",(str(uid),sym))
 if not r or not h or h["amount"]<n or n<=0:return "❌ سهام کافی نیست."
 gain=int(r["price"]*n*.98);left=h["amount"]-n
 with LOCK,db() as c:
  if left:c.execute("UPDATE stocks SET amount=? WHERE uid=? AND symbol=?",(left,str(uid),sym))
  else:c.execute("DELETE FROM stocks WHERE uid=? AND symbol=?",(str(uid),sym))
  c.commit()
 addmoney(uid,gain,"sell",sym);return f"💰 فروش موفق!\n{sym} × {n}\n💰 +{fmt(gain)}"

def my_stocks(uid):
 rs=q("SELECT * FROM stocks WHERE uid=? AND amount>0",(str(uid),));return "📦 سهام من\n\n"+("\n".join(f"{r['symbol']}: {r['amount']} سهم | میانگین {fmt(r['avg_price'])}" for r in rs) if rs else "سهامی نداری.")

def battle(uid,boss=False):
 p=get(uid)
 if p["energy"]<15:return "⚡ ۱۵ انرژی لازم است."
 enemy=(120+p["level"]*20) if boss else random.randint(40,150);power=p["strength"]+p["charisma"]//2+p["level"]*5+random.randint(0,30);upd(uid,energy=p["energy"]-15)
 if power>=enemy:
  reward=(1000000+p["level"]*100000) if boss else (200000+p["level"]*50000);addmoney(uid,reward,"battle","boss" if boss else "training");gainxp(uid,40 if boss else 20);return f"⚔️ پیروزی!\n💰 +{fmt(reward)}\n⭐ XP +{40 if boss else 20}"
 gainxp(uid,5);return "⚔️ این نبرد را باختی، اما XP گرفتی."

def referrals(uid):
 return f"👥 دعوت دوستان\n\nلینک/کد دعوت تو: REF-{uid}\n🎁 پاداش دعوت: ۱ میلیون تومان\n💎 پاداش دعوت‌شده: ۱ جم\n\nکد را هنگام شروع با /start REF-{uid} بفرست."

def apply_ref(uid,code):
 if not code.startswith("REF-"):return
 ref=code[4:];p=get(uid)
 if not ref or ref==str(uid) or p["ref_by"]:return
 parent=get(ref)
 if not parent:return
 upd(uid,ref_by=ref,gems=p["gems"]+1);upd(ref,ref_count=parent["ref_count"]+1,ref_earned=parent["ref_earned"]+1000000);addmoney(ref,1000000,"referral",str(uid))

def event(uid):
 p=get(uid);kind=random.choice(["bonus","market","work","training"])
 if kind=="bonus":n=random.randint(100000,1000000);addmoney(uid,n,"event","bonus");return f"🎲 رویداد ویژه!\n💰 +{fmt(n)} تومان"
 if kind=="market":return "📰 خبر بازار: نوسان شدید امروز فعال است؛ قیمت‌ها در معامله بعدی تغییر می‌کنند."
 if kind=="work":upd(uid,happiness=min(100,p["happiness"]+10));return "🎲 رویداد کاری مثبت! 😊 شادی +۱۰"
 upd(uid,intelligence=p["intelligence"]+3);return "🎲 رویداد آموزشی! 🧠 هوش +۳"

def leaderboard():
 rs=q("SELECT name,money,level FROM users WHERE banned=0 ORDER BY money DESC LIMIT 10");return "🏆 ثروتمندترین‌ها\n\n"+"\n".join(f"{i}. {r['name']} — {fmt(r['money'])} — Lv.{r['level']}" for i,r in enumerate(rs,1))

def helptext():return "ℹ️ Life Simulator روبیکا\n━━━━━━━━━━\nبا ۱۰۰ میلیون تومان شروع می‌کنی. شغل بگیر، پول جمع کن، بانک و سرمایه‌گذاری داشته باش، شرکت بساز و وارد بازار سهام شو.\n\nفرمان‌ها:\n/start [کد دعوت]\n/profile\n/jobs\n/job نام شغل\n/pay شناسه مبلغ\n/deposit مبلغ\n/withdraw مبلغ\n/buy SYMBOL تعداد\n/sell SYMBOL تعداد\n/hire\n/admin\n/broadcast متن\n/grant مبلغ\n\nهمه منوها دکمه معمولی دارند."

def admin_stats():
 a=one("SELECT COUNT(*) n FROM users");m=one("SELECT COALESCE(SUM(money),0) n FROM users");c=one("SELECT COUNT(*) n FROM companies");return f"📊 آمار\n👥 کاربران: {fmt(a['n'])}\n💰 پول کاربران: {fmt(m['n'])}\n🏢 شرکت‌ها: {fmt(c['n'])}"

def backup():
 target=DB+".backup";shutil.copy2(DB,target);return target

def process(uid,text,name="بازیکن",username=""):
 ensure(uid,name,username);p=get(uid);text=(text or "").strip()
 if p["banned"]:return "⛔ دسترسی شما مسدود است.",MAIN
 if text.startswith("/start"):
  z=text.split(maxsplit=1);apply_ref(uid,z[1] if len(z)>1 else "");return "🤖 به Life Simulator روبیکا خوش آمدی!\n\n💰 سرمایه شروع: ۱۰۰٬۰۰۰٬۰۰۰ تومان\nاز منوی زیر شروع کن 👇",MAIN
 if text in ("👤 پروفایل","/profile"):return profile(uid),MAIN
 if text=="💰 اقتصاد":return "💰 اقتصاد",ECON
 if text=="💵 موجودی":return f"💰 نقد: {fmt(p['money'])}\n🏦 بانک: {fmt(p['bank'])}",ECON
 if text=="🏦 بانک":return "🏦 بانک\n/deposit مبلغ\n/withdraw مبلغ",ECON
 if text=="💸 انتقال":return "💸 /pay شناسه مبلغ",ECON
 if text=="🎁 موجودی هدیه":return "🎁 جوایز و جم‌ها در پروفایل نمایش داده می‌شوند.\n💎 جم: "+str(p["gems"]),ECON
 if text=="💼 کار و شغل":return "💼 شغل و کار",JOB
 if text in ("🔎 شغل‌ها","/jobs"):return "🔎 شغل‌ها\n\n"+"\n".join(f"• {j}: {fmt(v[0])}" for j,v in JOBS.items())+"\n\n/job نام شغل",JOB
 if text=="💼 کار کردن":return work(uid),JOB
 if text=="📚 آموزش":return train(uid),JOB
 if text=="🛌 استراحت":return rest(uid),JOB
 if text=="🏢 شرکت":return company(uid),COMP
 if text=="🏗 ساخت شرکت":return make_company(uid),COMP
 if text=="📊 شرکت من":return company(uid),COMP
 if text=="👷 استخدام":return hire(uid),COMP
 if text=="📈 عرضه سهام":return list_company(uid),COMP
 if text=="💼 درآمد شرکت":return company_income(uid),COMP
 if text in ("📈 بازار بورس","📊 قیمت‌ها"):return market(),MKT
 if text=="🛒 خرید سهم":return "🛒 /buy TECH 2",MKT
 if text=="💰 فروش سهم":return "💰 /sell TECH 2",MKT
 if text=="📦 سهام من":return my_stocks(uid),MKT
 if text=="⚔️ نبرد":return "⚔️ بخش نبرد\n\nنبرد تمرینی و باس روزانه برای گرفتن XP و پاداش داخل بازی.",BAT
 if text=="⚔️ نبرد تمرینی":return battle(uid),BAT
 if text=="👹 باس روزانه":return battle(uid,True),BAT
 if text=="🏆 رکورد نبرد":
  r=one("SELECT COUNT(*) n,COALESCE(SUM(amount),0) s FROM logs WHERE uid=? AND kind='battle' AND amount>0",(str(uid),));return f"🏆 رکورد\nبردها: {r['n']}\nجوایز: {fmt(r['s'])}",BAT
 if text=="🎁 روزانه":return daily(uid),MAIN
 if text=="🎒 دارایی‌ها":return f"🎒 دارایی‌ها\n💎 جم: {p['gems']}\n🏢 شرکت: {company(uid)}\n\n{my_stocks(uid)}",MAIN
 if text=="👥 دعوت دوستان":return referrals(uid),MAIN
 if text=="🏆 رتبه‌بندی":return leaderboard(),MAIN
 if text=="🎲 رویداد":return event(uid),MAIN
 if text=="ℹ️ راهنما" or text=="/help":return helptext(),MAIN
 if text=="🔙 بازگشت":return "🔙 منوی اصلی",MAIN
 if text=="/admin" and admin(uid):return "🛠 پنل مدیریت",ADM
 if admin(uid) and text=="👥 آمار":return admin_stats(),ADM
 if admin(uid) and text=="💾 بکاپ":return "💾 بکاپ ساخته شد: "+os.path.basename(backup()),ADM
 if admin(uid) and text=="📢 پیام همگانی":return "📢 /broadcast متن",ADM
 if admin(uid) and text=="💰 جایزه همگانی":return "💰 /grant مبلغ",ADM
 if admin(uid) and text=="🚫 مدیریت مسدودی":return "🚫 /ban شناسه یا /unban شناسه",ADM
 if admin(uid) and text=="🔙 خروج":return "خروج از پنل.",MAIN
 a=text.split()
 if a and a[0]=="/job":
  j=" ".join(a[1:]);
  if j not in JOBS:return "❌ شغل پیدا نشد.",JOB
  upd(uid,job=j);return f"✅ شغل: {j}\n💰 حقوق پایه: {fmt(JOBS[j][0])}",JOB
 if a and a[0]=="/pay" and len(a)>=3:
  try:t=str(a[1]);n=int(a[2])
  except:return "❌ فرمت: /pay شناسه مبلغ",ECON
  if n<=0 or t==str(uid):return "❌ انتقال نامعتبر.",ECON
  to=get(t)
  if not to:return "❌ مقصد پیدا نشد.",ECON
  if p["money"]<n:return "❌ موجودی کافی نیست.",ECON
  addmoney(uid,-n,"transfer",t);addmoney(t,n,"transfer",str(uid));return f"✅ {fmt(n)} تومان منتقل شد.",ECON
 if a and a[0]=="/deposit" and len(a)==2:
  try:n=int(a[1])
  except:return "❌ مبلغ نامعتبر.",ECON
  if n<=0 or p["money"]<n:return "❌ موجودی کافی نیست.",ECON
  upd(uid,money=p["money"]-n,bank=p["bank"]+n);return f"🏦 +{fmt(n)} به بانک واریز شد.",ECON
 if a and a[0]=="/withdraw" and len(a)==2:
  try:n=int(a[1])
  except:return "❌ مبلغ نامعتبر.",ECON
  if n<=0 or p["bank"]<n:return "❌ موجودی بانک کافی نیست.",ECON
  upd(uid,money=p["money"]+n,bank=p["bank"]-n);return f"💵 {fmt(n)} برداشت شد.",ECON
 if a and a[0]=="/buy" and len(a)>=3:
  return buy(uid,a[1],a[2]),MKT
 if a and a[0]=="/sell" and len(a)>=3:return sell(uid,a[1],a[2]),MKT
 if a and a[0]=="/hire":return hire(uid),COMP
 if admin(uid) and a and a[0]=="/grant" and len(a)==2:
  try:n=int(a[1])
  except:return "❌ مبلغ نامعتبر.",ADM
  ids=[r["uid"] for r in q("SELECT uid FROM users WHERE banned=0")]
  for x in ids:addmoney(x,n,"admin_grant")
  return f"💰 {fmt(n)} به {len(ids)} کاربر داده شد.",ADM
 if admin(uid) and a and a[0]=="/broadcast" and len(a)>1:
  msg=" ".join(a[1:]);ids=[r["uid"] for r in q("SELECT uid FROM users WHERE banned=0")];ok=sum(api.send(x,msg,MAIN) for x in ids);return f"📢 ارسال: {ok}/{len(ids)}",ADM
 if admin(uid) and a and a[0] in ("/ban","/unban") and len(a)==2:
  target=a[1];exists=get(target)
  if not exists:return "❌ کاربر پیدا نشد.",ADM
  upd(target,banned=1 if a[0]=="/ban" else 0);return ("🚫 مسدود شد." if a[0]=="/ban" else "✅ رفع مسدودی شد."),ADM
 return "🤔 گزینه ناشناخته است. از دکمه‌ها یا /help استفاده کن.",MAIN

def parse(u):
 m=u.get("new_message") or u.get("message") or {};s=m.get("sender") or {};chat=u.get("chat_id") or m.get("chat_id");uid=m.get("sender_id") or s.get("user_id") or s.get("id") or chat;text=m.get("text") or "";name=s.get("first_name") or s.get("name") or "بازیکن";user=s.get("username") or "";return chat,uid,text,name,user

def run():
 init();offset=None;log.info("Life Simulator Rubika started")
 while True:
  try:
   r=api.updates(offset);us=r.get("updates",[]) if isinstance(r,dict) else []
   if r.get("next_offset_id") is not None:offset=str(r["next_offset_id"])
   for u in us:
    try:
     chat,uid,text,name,user=parse(u)
     if chat and uid:
      msg,k=process(uid,text,name,user);api.send(chat,msg,k)
    except Exception:log.exception("update failed")
   time.sleep(1)
  except KeyboardInterrupt:break
  except Exception:log.exception("poll failed");time.sleep(4)

if __name__=="__main__":run()
