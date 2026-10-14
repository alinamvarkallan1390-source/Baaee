"""Regression tests for the battle pass, football economy, and ad placements."""
import os
import tempfile
import unittest
import sys
import types
from pathlib import Path

# Importing main.py chooses a DB path at module load; keep this test-only path out of the repo.
os.environ["LIFE_SIM_DB"] = str(Path(tempfile.gettempdir()) / f"baaee-test-import-{os.getpid()}.sqlite3")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
# These tests use a fake API; provide a tiny requests stub instead of requiring network setup.
sys.modules.setdefault("requests", types.SimpleNamespace(Session=lambda: None))

import main


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.callbacks = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append({"chat_id": chat_id, "text": str(text), "reply_markup": reply_markup})
        return {"ok": True}

    def answer_callback(self, callback_id, text=None):
        self.callbacks.append((callback_id, text))
        return {"ok": True}

    def call(self, *args, **kwargs):
        return {"ok": True}


class V120FeatureTests(unittest.TestCase):
    def setUp(self):
        self.old_db = main.db
        self.old_api = main.api
        main.db = main.Database(":memory:")
        main.api = FakeAPI()
        self.api = main.api

    def tearDown(self):
        main.db.conn.close()
        main.db = self.old_db
        main.api = self.old_api

    def add_user(self, uid, name=None, money=25_000):
        name = name or f"بازیکن {uid}"
        stamp = main.now_iso()
        main.db.execute(
            "INSERT INTO users(user_id,username,first_name,created_at,last_seen) VALUES(?,?,?,?,?)",
            (uid, f"u{uid}", name, stamp, stamp),
        )
        main.db.execute(
            "INSERT INTO profiles(user_id,name,created_at,money) VALUES(?,?,?,?)",
            (uid, name, stamp, money),
        )

    def test_battle_pass_tracks_activity_and_claims_each_reward_once(self):
        uid = 101
        self.add_user(uid)
        for _ in range(2):
            main.log_action(uid, "job_work", "test")

        sid = main.battle_pass_season_info()[0]
        bp = main.battle_pass_ensure(uid, sid)
        mission = main.db.fetchone(
            "SELECT progress FROM battle_pass_missions WHERE user_id=? AND season_id=? AND mission_key='work_day'",
            (uid, sid),
        )
        self.assertEqual(bp["xp"], 20)
        self.assertEqual(mission["progress"], 2)

        claim = main.battle_pass_mission_claim(uid, "daily", "work_day")
        self.assertIn("+۶۰ XP", claim)
        self.assertIn("قبلاً گرفته", main.battle_pass_mission_claim(uid, "daily", "work_day"))

        main.db.execute("UPDATE battle_pass SET xp=250 WHERE user_id=? AND season_id=?", (uid, sid))
        before = main.profile(uid)["money"]
        self.assertIn("جایزه‌ی سطح", main.battle_pass_claim_tier(uid, "free", 1, sid))
        after_first_claim = main.profile(uid)["money"]
        self.assertEqual(after_first_claim - before, 1_100)
        self.assertIn("قبلاً دریافت", main.battle_pass_claim_tier(uid, "free", 1, sid))
        self.assertEqual(main.profile(uid)["money"], after_first_claim)
        self.assertIn("فقط برای بتل‌پس Premium", main.battle_pass_claim_tier(uid, "premium", 1, sid))

        self.assertIn("اعطا شد", main.battle_pass_admin_grant(999, uid, "premium"))
        self.assertTrue(main.battle_pass_ensure(uid, sid)["premium"])
        self.assertIn("جایزه‌ی سطح", main.battle_pass_claim_tier(uid, "premium", 1, sid))

    def test_daily_streak_claim_advances_battle_pass_mission(self):
        uid = 102
        self.add_user(uid)
        result = main.streak_claim(102, uid)
        self.assertIn("جایزه روزانه", result)
        sid = main.battle_pass_season_info()[0]
        row = main.db.fetchone(
            "SELECT progress FROM battle_pass_missions WHERE user_id=? AND season_id=? AND mission_key='daily_claim'",
            (uid, sid),
        )
        self.assertEqual(row["progress"], 1)
        main.streak_claim(102, uid)
        row = main.db.fetchone(
            "SELECT progress FROM battle_pass_missions WHERE user_id=? AND season_id=? AND mission_key='daily_claim'",
            (uid, sid),
        )
        self.assertEqual(row["progress"], 1)

    def test_premium_purchase_uses_manual_order_and_admin_approval(self):
        uid, admin_id = 201, 901
        self.add_user(uid)
        main.order_new(uid, uid, "bp-premium")
        order = main.db.fetchone("SELECT * FROM orders WHERE user_id=?", (uid,))
        self.assertEqual(order["pack"], main.BP_ORDER_PREFIX + main.battle_pass_season_info()[0])
        self.assertEqual(order["gems"], 0)
        self.assertEqual(order["price_toman"], main.BP_PREMIUM_PRICE_DEFAULT)

        payment_result = main.order_paid(uid, uid, order["id"])
        self.assertIn("پس از بررسی و تأیید ادمین", payment_result)
        self.assertEqual(main.db.fetchone("SELECT status FROM orders WHERE id=?", (order["id"],))["status"], "awaiting")
        before_gems = main.profile(uid)["gems"]
        approval = main.admin_order_decide(admin_id, admin_id, order["id"], True)
        self.assertIn("Premium بتل‌پس فعال شد", approval)
        self.assertTrue(main.battle_pass_ensure(uid)["premium"])
        self.assertEqual(main.profile(uid)["gems"], before_gems)
        self.assertEqual(main.db.fetchone("SELECT status FROM orders WHERE id=?", (order["id"],))["status"], "ok")
        self.assertIn("قبلاً رسیدگی", main.admin_order_decide(admin_id, admin_id, order["id"], True))

    def test_gem_orders_still_credit_gems_once(self):
        uid, admin_id = 202, 902
        self.add_user(uid)
        main.order_new(uid, uid, "p1")
        order = main.db.fetchone("SELECT * FROM orders WHERE user_id=?", (uid,))
        main.order_paid(uid, uid, order["id"])
        self.assertIn("سکه شارژ شد", main.admin_order_decide(admin_id, admin_id, order["id"], True))
        self.assertEqual(main.profile(uid)["gems"], 100)
        main.admin_order_decide(admin_id, admin_id, order["id"], True)
        self.assertEqual(main.profile(uid)["gems"], 100)

    def test_football_market_uses_only_in_game_coins_and_keeps_eleven_players(self):
        seller, buyer = 301, 302
        self.add_user(seller, money=50_000)
        self.add_user(buyer, money=75_000)
        seller_team = main.fc_ensure_team(seller)
        buyer_team = main.fc_ensure_team(buyer)
        self.assertEqual(main.db.fetchone("SELECT COUNT(*) c FROM fc_players WHERE owner_id=?", (seller,))["c"], 11)
        self.assertIn("بازیکن تازه", main.fc_scout_player(seller))
        player = main.db.fetchone("SELECT id FROM fc_players WHERE owner_id=? AND origin='scout'", (seller,))
        self.assertIsNotNone(player)

        self.assertIsNone(main.fc_start_listing(seller, player["id"], seller))
        state, form = main.get_state(seller)
        self.assertEqual(state, "fc_sell_price")
        main.fc_sell_price_done(seller, seller, "500", form)
        listing = main.db.fetchone("SELECT * FROM fc_listings WHERE seller_id=? AND status='active'", (seller,))
        self.assertIsNotNone(listing)

        seller_cash = main.profile(seller)["money"]
        buyer_cash = main.profile(buyer)["money"]
        result = main.fc_buy_listing(buyer, listing["id"])
        self.assertIn("خرید انجام شد", result)
        self.assertEqual(main.profile(seller)["money"], seller_cash)
        self.assertEqual(main.profile(buyer)["money"], buyer_cash)
        self.assertEqual(main.fc_team_power(buyer) > 0, True)
        self.assertEqual(main.db.fetchone("SELECT COUNT(*) c FROM fc_players WHERE owner_id=?", (seller,))["c"], 11)
        self.assertEqual(main.db.fetchone("SELECT coins FROM fc_teams WHERE user_id=?", (buyer,))["coins"], buyer_team["coins"] - 500)
        self.assertEqual(main.db.fetchone("SELECT coins FROM fc_teams WHERE user_id=?", (seller,))["coins"], seller_team["coins"] - 900 + 475)
        for uid in (seller, buyer):
            wallet = main.db.fetchone("SELECT coins FROM fc_teams WHERE user_id=?", (uid,))["coins"]
            ledger = main.db.fetchone("SELECT COALESCE(SUM(amount),0) total FROM fc_coin_ledger WHERE user_id=?", (uid,))["total"]
            self.assertEqual(wallet, ledger)
        self.assertEqual(main.db.fetchone("SELECT COUNT(*) c FROM fc_transfers WHERE buyer_id=?", (buyer,))["c"], 1)

        main.handle_callback({
            "from": {"id": buyer, "first_name": "buyer"},
            "message": {"chat": {"id": buyer, "type": "private"}, "message_id": 2},
            "data": "fc:match", "id": "fc-match-callback",
        })
        self.assertEqual(main.db.fetchone("SELECT COUNT(*) c FROM fc_matches WHERE user_id=?", (buyer,))["c"], 1)
        self.assertEqual(main.db.fetchone("SELECT COUNT(*) c FROM fc_coin_ledger WHERE user_id=? AND reason='match'", (buyer,))["c"], 1)
        wallet = main.db.fetchone("SELECT coins FROM fc_teams WHERE user_id=?", (buyer,))["coins"]
        ledger = main.db.fetchone("SELECT COALESCE(SUM(amount),0) total FROM fc_coin_ledger WHERE user_id=?", (buyer,))["total"]
        self.assertEqual(wallet, ledger)
        self.assertIn("قابل‌برداشت یا تبدیل به پول واقعی نیست", self.api.sent[-1]["text"])

    def test_ad_slot_default_and_admin_configuration(self):
        self.add_user(401)
        self.assertIsNone(main.ad_slot_get("main"))
        self.assertEqual(main.ad_slot_button("main"), ("📣 جایگاه تبلیغ شما", "adslot:open:main"))
        self.assertTrue(main.ad_slot_save("main", "پیشنهاد ویژه‌ی بازی", "https://example.com", actor=999))
        label, callback = main.ad_slot_button("main")
        self.assertEqual(label, "📣 پیشنهاد ویژه‌ی بازی")
        self.assertEqual(callback, "adslot:open:main")
        main.handle_callback({
            "from": {"id": 401, "first_name": "test"},
            "message": {"chat": {"id": 401, "type": "private"}, "message_id": 1},
            "data": "adslot:open:main", "id": "ad-callback",
        })
        self.assertIn("پیشنهاد ویژه‌ی بازی", self.api.sent[-1]["text"])
        self.assertEqual(self.api.sent[-1]["reply_markup"]["inline_keyboard"][0][0]["url"], "https://example.com")
        self.assertFalse(main.ad_slot_save("unknown", "ad"))
        self.assertFalse(main.ad_slot_save("main", "x" * 1201))

    def test_battle_pass_panel_shows_the_full_reward_table(self):
        uid = 450
        self.add_user(uid)
        main.handle_callback({
            "from": {"id": uid, "first_name": "test"},
            "message": {"chat": {"id": uid, "type": "private"}, "message_id": 1},
            "data": "bp:home", "id": "bp-callback",
        })
        message = self.api.sent[-1]
        self.assertIn("جدول کامل پاداش هر سطح", message["text"])
        self.assertIn("سطح ۳۰", message["text"])
        self.assertLess(len(message["text"]), 4096)
        callbacks = [button["callback_data"] for row in message["reply_markup"]["inline_keyboard"] for button in row]
        self.assertIn("bp:buy", callbacks)
        self.assertIn("fc:home", callbacks)

    def test_admin_can_configure_an_ad_through_the_existing_callback_and_state_router(self):
        admin_id = 601
        self.add_user(admin_id)
        main.db.execute("INSERT OR IGNORE INTO admins(user_id,added_at) VALUES(?,?)", (admin_id, main.now_iso()))
        self.assertTrue(main.admin_callback(admin_id, admin_id, "adm:adpanel", "admin-panel", None))
        self.assertIn("جایگاه‌های تبلیغ", self.api.sent[-1]["text"])

        self.assertTrue(main.admin_callback(admin_id, admin_id, "adm:adedit:main", "admin-edit", None))
        state, data = main.get_state(admin_id)
        self.assertEqual(state, "adm_ad_content")
        self.assertTrue(main.handle_state_text(admin_id, admin_id, "متن تبلیغ آزمایشی", state, data))
        state, data = main.get_state(admin_id)
        self.assertEqual(state, "adm_ad_link")
        self.assertTrue(main.handle_state_text(admin_id, admin_id, "https://example.com/ad", state, data))
        self.assertEqual(main.ad_slot_get("main")["text"], "متن تبلیغ آزمایشی")
        self.assertEqual(main.ad_slot_get("main")["url"], "https://example.com/ad")

    def test_existing_missions_panel_has_battle_pass_entry(self):
        uid = 501
        self.add_user(uid)
        main.panel_missions(uid, uid)
        markup = self.api.sent[-1]["reply_markup"]
        callbacks = [button["callback_data"] for row in markup["inline_keyboard"] for button in row]
        self.assertIn("bp:home", callbacks)
        self.assertIn("📣 جایگاه تبلیغ شما", [button["text"] for row in markup["inline_keyboard"] for button in row])


if __name__ == "__main__":
    unittest.main()
