import aiosqlite, logging, time, secrets, string
from config import DB_PATH

log = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, username TEXT,
            full_name TEXT, language TEXT DEFAULT 'uz',
            role TEXT DEFAULT 'user', wallet TEXT,
            kyc_status TEXT DEFAULT 'none',
            gtr_balance REAL DEFAULT 0.0,
            referral_code TEXT UNIQUE, referred_by INTEGER,
            referral_count INTEGER DEFAULT 0, last_daily TEXT,
            is_banned INTEGER DEFAULT 0, ban_reason TEXT,
            phone TEXT, city TEXT, country TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS kyc_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL, doc_type TEXT NOT NULL,
            front_fid TEXT NOT NULL, back_fid TEXT,
            selfie_fid TEXT, enc_name TEXT, enc_docnum TEXT,
            birth_date TEXT, status TEXT DEFAULT 'pending',
            reject_note TEXT, reviewed_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS wifi_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL, title TEXT NOT NULL,
            description TEXT, speed_plan TEXT NOT NULL,
            gtr_per_hour REAL NOT NULL, location_lat REAL,
            location_lon REAL, location_name TEXT,
            city TEXT, country TEXT, is_active INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0, rating_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS wifi_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL, buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL, hours REAL NOT NULL,
            gtr_amount REAL NOT NULL, status TEXT DEFAULT 'pending',
            rating INTEGER, review TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL, title TEXT NOT NULL,
            description TEXT NOT NULL, category TEXT NOT NULL,
            channel_link TEXT, image_fid TEXT,
            tariff TEXT NOT NULL, ton_amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            views INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0,
            start_date TEXT, end_date TEXT, reject_note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL, ad_id INTEGER,
            order_id INTEGER, amount_ton REAL, amount_gtr REAL,
            method TEXT, status TEXT DEFAULT 'pending',
            tx_hash TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS bonus_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL, type TEXT NOT NULL,
            amount REAL NOT NULL, detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referred_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS weekly_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL, tg_id INTEGER NOT NULL,
            rank INTEGER NOT NULL, referrals INTEGER DEFAULT 0,
            reward_gtr REAL DEFAULT 0.0, paid INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS memberships (
            tg_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            bonus_given INTEGER DEFAULT 0,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(tg_id, chat_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS security_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER, action TEXT NOT NULL,
            detail TEXT, blocked INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit (
            tg_id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0,
            window_start INTEGER DEFAULT 0,
            blocked_until INTEGER DEFAULT 0
        )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_wifi_city ON wifi_listings(city)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bonus_tg ON bonus_log(tg_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_refs_ref ON referrals(referrer_id)")
        await db.commit()
    log.info("DB tayyor")

def _gen_ref():
    return ''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(8))

async def get_user(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as c:
            return await c.fetchone()

async def upsert_user(tg_id, username, full_name, lang="uz", referred_by=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (tg_id,username,full_name,language,referral_code,referred_by)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(tg_id) DO UPDATE SET
            username=excluded.username,full_name=excluded.full_name
        """, (tg_id, username or "", full_name or "", lang, _gen_ref(), referred_by))
        await db.commit()

async def update_user(tg_id, **kw):
    if not kw: return
    cols = ", ".join(f"{k}=?" for k in kw)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {cols} WHERE tg_id=?", list(kw.values())+[tg_id])
        await db.commit()

async def get_user_by_ref(code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE referral_code=?", (code,)) as c:
            return await c.fetchone()

async def ban_user(tg_id, reason):
    await update_user(tg_id, is_banned=1, ban_reason=reason)

async def add_bonus(tg_id, amount, btype, detail=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET gtr_balance=gtr_balance+? WHERE tg_id=?", (amount,tg_id))
        await db.execute("INSERT INTO bonus_log (tg_id,type,amount,detail) VALUES (?,?,?,?)", (tg_id,btype,amount,detail))
        await db.commit()
        async with db.execute("SELECT gtr_balance FROM users WHERE tg_id=?", (tg_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0.0

async def deduct_balance(tg_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT gtr_balance FROM users WHERE tg_id=?", (tg_id,)) as c:
            row = await c.fetchone()
        if not row or row[0] < amount: return False
        await db.execute("UPDATE users SET gtr_balance=gtr_balance-? WHERE tg_id=?", (amount,tg_id))
        await db.commit()
        return True

async def check_daily_bonus(tg_id):
    from datetime import date
    u = await get_user(tg_id)
    return bool(u and u["last_daily"] == date.today().isoformat())

async def claim_daily_bonus(tg_id):
    from datetime import date
    from config import DAILY_BONUS
    today = date.today().isoformat()
    bal = await add_bonus(tg_id, DAILY_BONUS, "daily_login", today)
    await update_user(tg_id, last_daily=today)
    return bal

async def give_ad_view_bonus(tg_id, ad_id):
    from config import AD_VIEW_BONUS
    return await add_bonus(tg_id, AD_VIEW_BONUS, "ad_view", f"ad={ad_id}")

async def give_join_bonus(tg_id, chat_id, name):
    from config import JOIN_BONUS
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT bonus_given FROM memberships WHERE tg_id=? AND chat_id=?", (tg_id,chat_id)) as c:
            row = await c.fetchone()
        if row and row[0]: return 0.0
        if row:
            await db.execute("UPDATE memberships SET bonus_given=1 WHERE tg_id=? AND chat_id=?", (tg_id,chat_id))
        else:
            await db.execute("INSERT INTO memberships (tg_id,chat_id,bonus_given) VALUES (?,?,1)", (tg_id,chat_id))
        await db.commit()
    return await add_bonus(tg_id, JOIN_BONUS, "join_chat", name)

async def add_referral(referrer_id, referred_id):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT OR IGNORE INTO referrals (referrer_id,referred_id) VALUES (?,?)", (referrer_id,referred_id))
            await db.execute("UPDATE users SET referral_count=referral_count+1 WHERE tg_id=?", (referrer_id,))
            await db.commit()
            return True
        except: return False

async def get_referral_count(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (tg_id,)) as c:
            return (await c.fetchone())[0]

async def get_top_referrers(limit=100):
    from datetime import date, timedelta
    week_start = (date.today()-timedelta(days=date.today().weekday())).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.referrer_id, u.username, u.full_name, COUNT(r.id) as ref_count
            FROM referrals r JOIN users u ON r.referrer_id=u.tg_id
            WHERE r.created_at >= ? GROUP BY r.referrer_id
            ORDER BY ref_count DESC LIMIT ?
        """, (week_start,limit)) as c:
            return await c.fetchall()

def calc_weekly_rewards(count):
    from config import WEEKLY_POOL, WEEKLY_TOP
    weights = [max(1, WEEKLY_TOP+1-r) for r in range(1,count+1)]
    total_w = sum(weights)
    return [round(WEEKLY_POOL*w/total_w, 3) for w in weights]

async def distribute_weekly_rewards(bot):
    from datetime import date, timedelta
    top = await get_top_referrers(100)
    if not top: return
    week_start = (date.today()-timedelta(days=date.today().weekday())).isoformat()
    rewards = calc_weekly_rewards(len(top))
    async with aiosqlite.connect(DB_PATH) as db:
        for i, row in enumerate(top):
            reward = rewards[i]
            tg_id = row["referrer_id"]
            await db.execute("INSERT INTO weekly_rewards (week_start,tg_id,rank,referrals,reward_gtr) VALUES (?,?,?,?,?)",
                             (week_start,tg_id,i+1,row["ref_count"],reward))
            await db.execute("UPDATE users SET gtr_balance=gtr_balance+? WHERE tg_id=?", (reward,tg_id))
            await db.execute("INSERT INTO bonus_log (tg_id,type,amount,detail) VALUES (?,?,?,?)",
                             (tg_id,"weekly_reward",reward,f"rank={i+1}"))
            try:
                await bot.send_message(tg_id,
                    f"🏆 *Haftalik Mukofot!*\n\n🥇 {i+1}-o'rin\n👥 {row['ref_count']} ta\n💰 +{reward} GTR",
                    parse_mode="Markdown")
            except: pass
        await db.commit()

async def submit_kyc(tg_id, doc_type, front_fid, back_fid, selfie_fid, enc_name, enc_docnum, birth_date):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO kyc_docs (tg_id,doc_type,front_fid,back_fid,selfie_fid,enc_name,enc_docnum,birth_date) VALUES (?,?,?,?,?,?,?,?)",
                         (tg_id,doc_type,front_fid,back_fid,selfie_fid,enc_name,enc_docnum,birth_date))
        await db.execute("UPDATE users SET kyc_status='pending' WHERE tg_id=?", (tg_id,))
        await db.commit()

async def get_pending_kyc():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM kyc_docs WHERE status='pending'") as c:
            return await c.fetchall()

async def approve_kyc(kyc_id, admin_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT tg_id FROM kyc_docs WHERE id=?", (kyc_id,)) as c:
            row = await c.fetchone()
        if row:
            await db.execute("UPDATE kyc_docs SET status='approved',reviewed_by=? WHERE id=?", (admin_id,kyc_id))
            await db.execute("UPDATE users SET kyc_status='verified' WHERE tg_id=?", (row[0],))
            await db.commit()
            return row[0]

async def reject_kyc(kyc_id, admin_id, note):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT tg_id FROM kyc_docs WHERE id=?", (kyc_id,)) as c:
            row = await c.fetchone()
        if row:
            await db.execute("UPDATE kyc_docs SET status='rejected',reviewed_by=?,reject_note=? WHERE id=?", (admin_id,note,kyc_id))
            await db.execute("UPDATE users SET kyc_status='rejected' WHERE tg_id=?", (row[0],))
            await db.commit()
            return row[0]

async def create_wifi_listing(seller_id, data):
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("INSERT INTO wifi_listings (seller_id,title,description,speed_plan,gtr_per_hour,location_name,city,country) VALUES (?,?,?,?,?,?,?,?)",
                             (seller_id,data["title"],data.get("description"),data["speed_plan"],data["gtr_per_hour"],data.get("location_name"),data.get("city"),data.get("country")))
        await db.commit()
        return c.lastrowid

async def get_wifi_listings(city=None, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT w.*,u.full_name as seller_name,u.username as seller_username FROM wifi_listings w JOIN users u ON w.seller_id=u.tg_id WHERE w.is_active=1"
        p = []
        if city: q += " AND (w.city=? OR w.city IS NULL)"; p.append(city)
        q += " ORDER BY w.rating DESC,w.total_sales DESC LIMIT ?"; p.append(limit)
        async with db.execute(q, p) as c:
            return await c.fetchall()

async def get_listing(listing_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT w.*,u.full_name as seller_name FROM wifi_listings w JOIN users u ON w.seller_id=u.tg_id WHERE w.id=?", (listing_id,)) as c:
            return await c.fetchone()

async def create_wifi_order(listing_id, buyer_id, seller_id, hours, gtr_amount):
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("INSERT INTO wifi_orders (listing_id,buyer_id,seller_id,hours,gtr_amount) VALUES (?,?,?,?,?)",
                             (listing_id,buyer_id,seller_id,hours,gtr_amount))
        await db.commit()
        return c.lastrowid

async def complete_wifi_order(order_id):
    from config import WIFI_SELL_FEE
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM wifi_orders WHERE id=?", (order_id,)) as c:
            order = await c.fetchone()
        if not order: return
        order = dict(order)
        seller_earn = order["gtr_amount"] * (1 - WIFI_SELL_FEE)
        await db.execute("UPDATE wifi_orders SET status='completed',completed_at=CURRENT_TIMESTAMP WHERE id=?", (order_id,))
        await db.execute("UPDATE wifi_listings SET total_sales=total_sales+1 WHERE id=?", (order["listing_id"],))
        await db.commit()
    await add_bonus(order["seller_id"], seller_earn, "wifi_sale", f"order={order_id}")

async def get_my_wifi_listings(seller_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM wifi_listings WHERE seller_id=? ORDER BY created_at DESC", (seller_id,)) as c:
            return await c.fetchall()

async def get_my_wifi_orders(buyer_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT o.*,w.title as wifi_title,w.speed_plan FROM wifi_orders o JOIN wifi_listings w ON o.listing_id=w.id WHERE o.buyer_id=? ORDER BY o.created_at DESC", (buyer_id,)) as c:
            return await c.fetchall()

async def create_ad(owner_id, data):
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("INSERT INTO ads (owner_id,title,description,category,channel_link,image_fid,tariff,ton_amount) VALUES (?,?,?,?,?,?,?,?)",
                             (owner_id,data["title"],data["description"],data["category"],data.get("channel_link"),data.get("image_fid"),data["tariff"],data["ton_amount"]))
        await db.commit()
        return c.lastrowid

async def get_active_ads(category=None, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT * FROM ads WHERE status='active'"
        p = []
        if category and category != "all": q += " AND category=?"; p.append(category)
        q += " ORDER BY CASE tariff WHEN 'premium' THEN 1 WHEN 'standard' THEN 2 ELSE 3 END LIMIT ?"; p.append(limit)
        async with db.execute(q, p) as c:
            return await c.fetchall()

async def get_pending_ads():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ads WHERE status='pending'") as c:
            return await c.fetchall()

async def update_ad_status(ad_id, status, note=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if status == "active":
            await db.execute("UPDATE ads SET status='active',start_date=CURRENT_TIMESTAMP,end_date=datetime(CURRENT_TIMESTAMP,'+30 days') WHERE id=?", (ad_id,))
        else:
            await db.execute("UPDATE ads SET status=?,reject_note=? WHERE id=?", (status,note,ad_id))
        await db.commit()

async def get_my_ads(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ads WHERE owner_id=? ORDER BY created_at DESC", (tg_id,)) as c:
            return await c.fetchall()

async def increment_ad_views(ad_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE ads SET views=views+1 WHERE id=?", (ad_id,))
        await db.commit()

async def check_rate_limit(tg_id, max_msgs=25, window=60):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT count,window_start,blocked_until FROM rate_limit WHERE tg_id=?", (tg_id,)) as c:
            row = await c.fetchone()
        if row:
            count, win_start, blocked_until = row
            if now < blocked_until: return False
            if now - win_start > window:
                await db.execute("UPDATE rate_limit SET count=1,window_start=? WHERE tg_id=?", (now,tg_id))
            elif count >= max_msgs:
                await db.execute("UPDATE rate_limit SET blocked_until=? WHERE tg_id=?", (now+1800,tg_id))
                return False
            else:
                await db.execute("UPDATE rate_limit SET count=count+1 WHERE tg_id=?", (tg_id,))
        else:
            await db.execute("INSERT INTO rate_limit (tg_id,count,window_start) VALUES (?,1,?)", (tg_id,now))
        await db.commit()
        return True

async def sec_log(tg_id, action, detail="", blocked=False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO security_log (tg_id,action,detail,blocked) VALUES (?,?,?,?)", (tg_id,action,detail,int(blocked)))
        await db.commit()

async def get_system_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async def cnt(q):
            async with db.execute(q) as c: return (await c.fetchone())[0]
        return {
            "users":       await cnt("SELECT COUNT(*) FROM users"),
            "kyc":         await cnt("SELECT COUNT(*) FROM users WHERE kyc_status='verified'"),
            "active_ads":  await cnt("SELECT COUNT(*) FROM ads WHERE status='active'"),
            "pending_ads": await cnt("SELECT COUNT(*) FROM ads WHERE status='pending'"),
            "pending_kyc": await cnt("SELECT COUNT(*) FROM kyc_docs WHERE status='pending'"),
            "wifi_total":  await cnt("SELECT COUNT(*) FROM wifi_listings WHERE is_active=1"),
            "wifi_orders": await cnt("SELECT COUNT(*) FROM wifi_orders WHERE status='completed'"),
            "total_gtr":   await cnt("SELECT COALESCE(SUM(amount),0) FROM bonus_log"),
      } import aiosqlite, logging, time, secrets, string
from config import DB_PATH

log = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, username TEXT,
            full_name TEXT, language TEXT DEFAULT 'uz',
            role TEXT DEFAULT 'user', wallet TEXT,
            kyc_status TEXT DEFAULT 'none',
            gtr_balance REAL DEFAULT 0.0,
            referral_code TEXT UNIQUE, referred_by INTEGER,
            referral_count INTEGER DEFAULT 0, last_daily TEXT,
            is_banned INTEGER DEFAULT 0, ban_reason TEXT,
            phone TEXT, city TEXT, country TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS kyc_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL, doc_type TEXT NOT NULL,
            front_fid TEXT NOT NULL, back_fid TEXT,
            selfie_fid TEXT, enc_name TEXT, enc_docnum TEXT,
            birth_date TEXT, status TEXT DEFAULT 'pending',
            reject_note TEXT, reviewed_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS wifi_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL, title TEXT NOT NULL,
            description TEXT, speed_plan TEXT NOT NULL,
            gtr_per_hour REAL NOT NULL, location_lat REAL,
            location_lon REAL, location_name TEXT,
            city TEXT, country TEXT, is_active INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0, rating_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS wifi_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL, buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL, hours REAL NOT NULL,
            gtr_amount REAL NOT NULL, status TEXT DEFAULT 'pending',
            rating INTEGER, review TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL, title TEXT NOT NULL,
            description TEXT NOT NULL, category TEXT NOT NULL,
            channel_link TEXT, image_fid TEXT,
            tariff TEXT NOT NULL, ton_amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            views INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0,
            start_date TEXT, end_date TEXT, reject_note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL, ad_id INTEGER,
            order_id INTEGER, amount_ton REAL, amount_gtr REAL,
            method TEXT, status TEXT DEFAULT 'pending',
            tx_hash TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS bonus_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL, type TEXT NOT NULL,
            amount REAL NOT NULL, detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referred_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS weekly_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL, tg_id INTEGER NOT NULL,
            rank INTEGER NOT NULL, referrals INTEGER DEFAULT 0,
            reward_gtr REAL DEFAULT 0.0, paid INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS memberships (
            tg_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            bonus_given INTEGER DEFAULT 0,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(tg_id, chat_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS security_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER, action TEXT NOT NULL,
            detail TEXT, blocked INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit (
            tg_id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0,
            window_start INTEGER DEFAULT 0,
            blocked_until INTEGER DEFAULT 0
        )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_wifi_city ON wifi_listings(city)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bonus_tg ON bonus_log(tg_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_refs_ref ON referrals(referrer_id)")
        await db.commit()
    log.info("DB tayyor")

def _gen_ref():
    return ''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(8))

async def get_user(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as c:
            return await c.fetchone()

async def upsert_user(tg_id, username, full_name, lang="uz", referred_by=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (tg_id,username,full_name,language,referral_code,referred_by)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(tg_id) DO UPDATE SET
            username=excluded.username,full_name=excluded.full_name
        """, (tg_id, username or "", full_name or "", lang, _gen_ref(), referred_by))
        await db.commit()

async def update_user(tg_id, **kw):
    if not kw: return
    cols = ", ".join(f"{k}=?" for k in kw)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {cols} WHERE tg_id=?", list(kw.values())+[tg_id])
        await db.commit()

async def get_user_by_ref(code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE referral_code=?", (code,)) as c:
            return await c.fetchone()

async def ban_user(tg_id, reason):
    await update_user(tg_id, is_banned=1, ban_reason=reason)

async def add_bonus(tg_id, amount, btype, detail=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET gtr_balance=gtr_balance+? WHERE tg_id=?", (amount,tg_id))
        await db.execute("INSERT INTO bonus_log (tg_id,type,amount,detail) VALUES (?,?,?,?)", (tg_id,btype,amount,detail))
        await db.commit()
        async with db.execute("SELECT gtr_balance FROM users WHERE tg_id=?", (tg_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0.0

async def deduct_balance(tg_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT gtr_balance FROM users WHERE tg_id=?", (tg_id,)) as c:
            row = await c.fetchone()
        if not row or row[0] < amount: return False
        await db.execute("UPDATE users SET gtr_balance=gtr_balance-? WHERE tg_id=?", (amount,tg_id))
        await db.commit()
        return True

async def check_daily_bonus(tg_id):
    from datetime import date
    u = await get_user(tg_id)
    return bool(u and u["last_daily"] == date.today().isoformat())

async def claim_daily_bonus(tg_id):
    from datetime import date
    from config import DAILY_BONUS
    today = date.today().isoformat()
    bal = await add_bonus(tg_id, DAILY_BONUS, "daily_login", today)
    await update_user(tg_id, last_daily=today)
    return bal

async def give_ad_view_bonus(tg_id, ad_id):
    from config import AD_VIEW_BONUS
    return await add_bonus(tg_id, AD_VIEW_BONUS, "ad_view", f"ad={ad_id}")

async def give_join_bonus(tg_id, chat_id, name):
    from config import JOIN_BONUS
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT bonus_given FROM memberships WHERE tg_id=? AND chat_id=?", (tg_id,chat_id)) as c:
            row = await c.fetchone()
        if row and row[0]: return 0.0
        if row:
            await db.execute("UPDATE memberships SET bonus_given=1 WHERE tg_id=? AND chat_id=?", (tg_id,chat_id))
        else:
            await db.execute("INSERT INTO memberships (tg_id,chat_id,bonus_given) VALUES (?,?,1)", (tg_id,chat_id))
        await db.commit()
    return await add_bonus(tg_id, JOIN_BONUS, "join_chat", name)

async def add_referral(referrer_id, referred_id):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT OR IGNORE INTO referrals (referrer_id,referred_id) VALUES (?,?)", (referrer_id,referred_id))
            await db.execute("UPDATE users SET referral_count=referral_count+1 WHERE tg_id=?", (referrer_id,))
            await db.commit()
            return True
        except: return False

async def get_referral_count(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (tg_id,)) as c:
            return (await c.fetchone())[0]

async def get_top_referrers(limit=100):
    from datetime import date, timedelta
    week_start = (date.today()-timedelta(days=date.today().weekday())).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.referrer_id, u.username, u.full_name, COUNT(r.id) as ref_count
            FROM referrals r JOIN users u ON r.referrer_id=u.tg_id
            WHERE r.created_at >= ? GROUP BY r.referrer_id
            ORDER BY ref_count DESC LIMIT ?
        """, (week_start,limit)) as c:
            return await c.fetchall()

def calc_weekly_rewards(count):
    from config import WEEKLY_POOL, WEEKLY_TOP
    weights = [max(1, WEEKLY_TOP+1-r) for r in range(1,count+1)]
    total_w = sum(weights)
    return [round(WEEKLY_POOL*w/total_w, 3) for w in weights]

async def distribute_weekly_rewards(bot):
    from datetime import date, timedelta
    top = await get_top_referrers(100)
    if not top: return
    week_start = (date.today()-timedelta(days=date.today().weekday())).isoformat()
    rewards = calc_weekly_rewards(len(top))
    async with aiosqlite.connect(DB_PATH) as db:
        for i, row in enumerate(top):
            reward = rewards[i]
            tg_id = row["referrer_id"]
            await db.execute("INSERT INTO weekly_rewards (week_start,tg_id,rank,referrals,reward_gtr) VALUES (?,?,?,?,?)",
                             (week_start,tg_id,i+1,row["ref_count"],reward))
            await db.execute("UPDATE users SET gtr_balance=gtr_balance+? WHERE tg_id=?", (reward,tg_id))
            await db.execute("INSERT INTO bonus_log (tg_id,type,amount,detail) VALUES (?,?,?,?)",
                             (tg_id,"weekly_reward",reward,f"rank={i+1}"))
            try:
                await bot.send_message(tg_id,
                    f"🏆 *Haftalik Mukofot!*\n\n🥇 {i+1}-o'rin\n👥 {row['ref_count']} ta\n💰 +{reward} GTR",
                    parse_mode="Markdown")
            except: pass
        await db.commit()

async def submit_kyc(tg_id, doc_type, front_fid, back_fid, selfie_fid, enc_name, enc_docnum, birth_date):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO kyc_docs (tg_id,doc_type,front_fid,back_fid,selfie_fid,enc_name,enc_docnum,birth_date) VALUES (?,?,?,?,?,?,?,?)",
                         (tg_id,doc_type,front_fid,back_fid,selfie_fid,enc_name,enc_docnum,birth_date))
        await db.execute("UPDATE users SET kyc_status='pending' WHERE tg_id=?", (tg_id,))
        await db.commit()

async def get_pending_kyc():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM kyc_docs WHERE status='pending'") as c:
            return await c.fetchall()

async def approve_kyc(kyc_id, admin_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT tg_id FROM kyc_docs WHERE id=?", (kyc_id,)) as c:
            row = await c.fetchone()
        if row:
            await db.execute("UPDATE kyc_docs SET status='approved',reviewed_by=? WHERE id=?", (admin_id,kyc_id))
            await db.execute("UPDATE users SET kyc_status='verified' WHERE tg_id=?", (row[0],))
            await db.commit()
            return row[0]

async def reject_kyc(kyc_id, admin_id, note):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT tg_id FROM kyc_docs WHERE id=?", (kyc_id,)) as c:
            row = await c.fetchone()
        if row:
            await db.execute("UPDATE kyc_docs SET status='rejected',reviewed_by=?,reject_note=? WHERE id=?", (admin_id,note,kyc_id))
            await db.execute("UPDATE users SET kyc_status='rejected' WHERE tg_id=?", (row[0],))
            await db.commit()
            return row[0]

async def create_wifi_listing(seller_id, data):
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("INSERT INTO wifi_listings (seller_id,title,description,speed_plan,gtr_per_hour,location_name,city,country) VALUES (?,?,?,?,?,?,?,?)",
                             (seller_id,data["title"],data.get("description"),data["speed_plan"],data["gtr_per_hour"],data.get("location_name"),data.get("city"),data.get("country")))
        await db.commit()
        return c.lastrowid

async def get_wifi_listings(city=None, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT w.*,u.full_name as seller_name,u.username as seller_username FROM wifi_listings w JOIN users u ON w.seller_id=u.tg_id WHERE w.is_active=1"
        p = []
        if city: q += " AND (w.city=? OR w.city IS NULL)"; p.append(city)
        q += " ORDER BY w.rating DESC,w.total_sales DESC LIMIT ?"; p.append(limit)
        async with db.execute(q, p) as c:
            return await c.fetchall()

async def get_listing(listing_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT w.*,u.full_name as seller_name FROM wifi_listings w JOIN users u ON w.seller_id=u.tg_id WHERE w.id=?", (listing_id,)) as c:
            return await c.fetchone()

async def create_wifi_order(listing_id, buyer_id, seller_id, hours, gtr_amount):
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("INSERT INTO wifi_orders (listing_id,buyer_id,seller_id,hours,gtr_amount) VALUES (?,?,?,?,?)",
                             (listing_id,buyer_id,seller_id,hours,gtr_amount))
        await db.commit()
        return c.lastrowid

async def complete_wifi_order(order_id):
    from config import WIFI_SELL_FEE
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM wifi_orders WHERE id=?", (order_id,)) as c:
            order = await c.fetchone()
        if not order: return
        order = dict(order)
        seller_earn = order["gtr_amount"] * (1 - WIFI_SELL_FEE)
        await db.execute("UPDATE wifi_orders SET status='completed',completed_at=CURRENT_TIMESTAMP WHERE id=?", (order_id,))
        await db.execute("UPDATE wifi_listings SET total_sales=total_sales+1 WHERE id=?", (order["listing_id"],))
        await db.commit()
    await add_bonus(order["seller_id"], seller_earn, "wifi_sale", f"order={order_id}")

async def get_my_wifi_listings(seller_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM wifi_listings WHERE seller_id=? ORDER BY created_at DESC", (seller_id,)) as c:
            return await c.fetchall()

async def get_my_wifi_orders(buyer_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT o.*,w.title as wifi_title,w.speed_plan FROM wifi_orders o JOIN wifi_listings w ON o.listing_id=w.id WHERE o.buyer_id=? ORDER BY o.created_at DESC", (buyer_id,)) as c:
            return await c.fetchall()

async def create_ad(owner_id, data):
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("INSERT INTO ads (owner_id,title,description,category,channel_link,image_fid,tariff,ton_amount) VALUES (?,?,?,?,?,?,?,?)",
                             (owner_id,data["title"],data["description"],data["category"],data.get("channel_link"),data.get("image_fid"),data["tariff"],data["ton_amount"]))
        await db.commit()
        return c.lastrowid

async def get_active_ads(category=None, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT * FROM ads WHERE status='active'"
        p = []
        if category and category != "all": q += " AND category=?"; p.append(category)
        q += " ORDER BY CASE tariff WHEN 'premium' THEN 1 WHEN 'standard' THEN 2 ELSE 3 END LIMIT ?"; p.append(limit)
        async with db.execute(q, p) as c:
            return await c.fetchall()

async def get_pending_ads():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ads WHERE status='pending'") as c:
            return await c.fetchall()

async def update_ad_status(ad_id, status, note=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if status == "active":
            await db.execute("UPDATE ads SET status='active',start_date=CURRENT_TIMESTAMP,end_date=datetime(CURRENT_TIMESTAMP,'+30 days') WHERE id=?", (ad_id,))
        else:
            await db.execute("UPDATE ads SET status=?,reject_note=? WHERE id=?", (status,note,ad_id))
        await db.commit()

async def get_my_ads(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ads WHERE owner_id=? ORDER BY created_at DESC", (tg_id,)) as c:
            return await c.fetchall()

async def increment_ad_views(ad_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE ads SET views=views+1 WHERE id=?", (ad_id,))
        await db.commit()

async def check_rate_limit(tg_id, max_msgs=25, window=60):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT count,window_start,blocked_until FROM rate_limit WHERE tg_id=?", (tg_id,)) as c:
            row = await c.fetchone()
        if row:
            count, win_start, blocked_until = row
            if now < blocked_until: return False
            if now - win_start > window:
                await db.execute("UPDATE rate_limit SET count=1,window_start=? WHERE tg_id=?", (now,tg_id))
            elif count >= max_msgs:
                await db.execute("UPDATE rate_limit SET blocked_until=? WHERE tg_id=?", (now+1800,tg_id))
                return False
            else:
                await db.execute("UPDATE rate_limit SET count=count+1 WHERE tg_id=?", (tg_id,))
        else:
            await db.execute("INSERT INTO rate_limit (tg_id,count,window_start) VALUES (?,1,?)", (tg_id,now))
        await db.commit()
        return True

async def sec_log(tg_id, action, detail="", blocked=False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO security_log (tg_id,action,detail,blocked) VALUES (?,?,?,?)", (tg_id,action,detail,int(blocked)))
        await db.commit()

async def get_system_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async def cnt(q):
            async with db.execute(q) as c: return (await c.fetchone())[0]
        return {
            "users":       await cnt("SELECT COUNT(*) FROM users"),
            "kyc":         await cnt("SELECT COUNT(*) FROM users WHERE kyc_status='verified'"),
            "active_ads":  await cnt("SELECT COUNT(*) FROM ads WHERE status='active'"),
            "pending_ads": await cnt("SELECT COUNT(*) FROM ads WHERE status='pending'"),
            "pending_kyc": await cnt("SELECT COUNT(*) FROM kyc_docs WHERE status='pending'"),
            "wifi_total":  await cnt("SELECT COUNT(*) FROM wifi_listings WHERE is_active=1"),
            "wifi_orders": await cnt("SELECT COUNT(*) FROM wifi_orders WHERE status='completed'"),
            "total_gtr":   await cnt("SELECT COALESCE(SUM(amount),0) FROM bonus_log"),
  }
