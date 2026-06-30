from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db
from config import ADMIN_IDS, TARIFFS, CATEGORIES, GTR_MASTER_WALLET
from utils.helpers import fmt_bal

router = Router()

def is_admin(tg_id):
    return tg_id in ADMIN_IDS

def _admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🪪 KYC",        callback_data="adm_kyc")
    kb.button(text="📢 Reklamalar", callback_data="adm_ads")
    kb.button(text="📊 Statistika", callback_data="adm_stats")
    kb.button(text="🏆 TOP taqsim", callback_data="adm_weekly")
    kb.adjust(2, 2)
    return kb.as_markup()

@router.message(Command("admin"))
async def admin_panel(msg: Message):
    if not is_admin(msg.from_user.id): return
    s = await db.get_system_stats()
    await msg.answer(
        f"👑 *G-TRUST Admin Panel*\n\n"
        f"👥 Foydalanuvchilar: *{s['users']}*\n"
        f"🪪 KYC tasdiqlangan: *{s['kyc']}*\n"
        f"📢 Faol reklamalar: *{s['active_ads']}*\n"
        f"⏳ KYC kutmoqda: *{s['pending_kyc']}*\n"
        f"⏳ Reklama kutmoqda: *{s['pending_ads']}*\n"
        f"📡 Faol WiFi: *{s['wifi_total']}*\n"
        f"🛒 WiFi buyurtmalar: *{s['wifi_orders']}*\n"
        f"💰 GTR tarqatildi: *{fmt_bal(s['total_gtr'])}*",
        parse_mode="Markdown",
        reply_markup=_admin_kb())

@router.callback_query(F.data == "adm_stats")
async def adm_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    s = await db.get_system_stats()
    await cb.message.edit_text(
        f"📊 *Statistika*\n\n"
        f"👥 Foydalanuvchilar: *{s['users']}*\n"
        f"🪪 KYC: *{s['kyc']}*\n"
        f"📢 Faol reklamalar: *{s['active_ads']}*\n"
        f"📡 WiFi listinglar: *{s['wifi_total']}*\n"
        f"🛒 WiFi buyurtmalar: *{s['wifi_orders']}*\n"
        f"💰 GTR tarqatildi: *{fmt_bal(s['total_gtr'])}*",
        parse_mode="Markdown",
        reply_markup=_admin_kb())
    await cb.answer()

@router.callback_query(F.data == "adm_kyc")
async def adm_kyc(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    docs = await db.get_pending_kyc()
    if not docs:
        await cb.answer("✅ KYC kutayotgan yo'q", show_alert=True)
        return
    from utils.keyboards import admin_kyc_kb
    for doc in docs[:5]:
        doc = dict(doc)
        txt = (f"🪪 *KYC Ariza*\n"
               f"👤 ID: `{doc['tg_id']}`\n"
               f"📄 {doc['doc_type']}\n"
               f"📅 {(doc.get('created_at') or '')[:16]}")
        try:
            fid = doc.get("selfie_fid") or doc.get("front_fid")
            if fid:
                await cb.message.answer_photo(
                    fid, caption=txt,
                    parse_mode="Markdown",
                    reply_markup=admin_kyc_kb(doc["tg_id"]))
            else:
                await cb.message.answer(
                    txt, parse_mode="Markdown",
                    reply_markup=admin_kyc_kb(doc["tg_id"]))
        except: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin_kyc_ok:"))
async def kyc_ok(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌"); return
    tg_id = int(cb.data.split(":")[1])
    docs  = await db.get_pending_kyc()
    doc   = next((d for d in docs if d["tg_id"] == tg_id), None)
    if doc:
        await db.approve_kyc(doc["id"], cb.from_user.id)
    else:
        await db.update_user(tg_id, kyc_status="verified")
    try:
        u = await db.get_user(tg_id)
        from locales import t
        await cb.bot.send_message(
            tg_id,
            t("kyc_approved", u["language"] if u else "uz"),
            parse_mode="Markdown")
    except: pass
    try:
        await cb.message.edit_caption(
            (cb.message.caption or "") + "\n\n✅ TASDIQLANDI",
            parse_mode="Markdown")
    except:
        try:
            await cb.message.edit_text(
                (cb.message.text or "") + "\n\n✅ TASDIQLANDI",
                parse_mode="Markdown")
        except: pass
    await cb.answer("✅")

@router.callback_query(F.data.startswith("admin_kyc_no:"))
async def kyc_no(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌"); return
    tg_id = int(cb.data.split(":")[1])
    docs  = await db.get_pending_kyc()
    doc   = next((d for d in docs if d["tg_id"] == tg_id), None)
    note  = "Hujjat aniq emas"
    if doc:
        await db.reject_kyc(doc["id"], cb.from_user.id, note)
    else:
        await db.update_user(tg_id, kyc_status="rejected")
    try:
        u = await db.get_user(tg_id)
        from locales import t
        await cb.bot.send_message(
            tg_id,
            t("kyc_rejected", u["language"] if u else "uz",
              reason=note),
            parse_mode="Markdown")
    except: pass
    try:
        await cb.message.edit_caption(
            (cb.message.caption or "") + "\n\n❌ RAD ETILDI",
            parse_mode="Markdown")
    except:
        try:
            await cb.message.edit_text(
                (cb.message.text or "") + "\n\n❌ RAD ETILDI",
                parse_mode="Markdown")
        except: pass
    await cb.answer("❌")

@router.callback_query(F.data == "adm_ads")
async def adm_ads(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    ads = await db.get_pending_ads()
    if not ads:
        await cb.answer("✅ Reklama kutayotgan yo'q", show_alert=True)
        return
    from utils.keyboards import admin_ad_kb
    for ad in ads[:5]:
        ad = dict(ad)
        txt = (f"📢 *Reklama #{ad['id']}*\n"
               f"👤 `{ad['owner_id']}`\n"
               f"📁 {CATEGORIES.get(ad.get('category',''),'—')}\n"
               f"📌 {ad['title']}\n"
               f"📝 {(ad.get('description') or '')[:80]}\n"
               f"💎 {TARIFFS.get(ad['tariff'],{}).get('name','—')} "
               f"— {ad['ton_amount']} TON")
        try:
            if ad.get("image_fid"):
                await cb.message.answer_photo(
                    ad["image_fid"], caption=txt,
                    parse_mode="Markdown",
                    reply_markup=admin_ad_kb(ad["id"]))
            else:
                await cb.message.answer(
                    txt, parse_mode="Markdown",
                    reply_markup=admin_ad_kb(ad["id"]))
        except: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin_ad_ok:"))
async def ad_ok(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌"); return
    ad_id = int(cb.data.split(":")[1])
    ads   = await db.get_pending_ads()
    ad    = next((dict(a) for a in ads if a["id"] == ad_id), None)
    if not ad:
        await cb.answer("❌ Topilmadi", show_alert=True); return
    await db.update_ad_status(ad_id, "payment_pending")
    try:
        u    = await db.get_user(ad["owner_id"])
        lang = u["language"] if u else "uz"
        from locales import t
        from utils.keyboards import payment_kb
        await cb.bot.send_message(
            ad["owner_id"],
            t("ad_approved_pay", lang, ton=ad["ton_amount"]),
            parse_mode="Markdown",
            reply_markup=payment_kb(
                ad_id, ad["ton_amount"],
                GTR_MASTER_WALLET, lang))
    except: pass
    try:
        txt = (cb.message.caption or cb.message.text or "")
        txt += "\n\n✅ TASDIQLANDI"
        if cb.message.caption:
            await cb.message.edit_caption(txt, parse_mode="Markdown")
        else:
            await cb.message.edit_text(txt, parse_mode="Markdown")
    except: pass
    await cb.answer("✅")

@router.callback_query(F.data.startswith("admin_ad_no:"))
async def ad_no(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌"); return
    ad_id = int(cb.data.split(":")[1])
    ads   = await db.get_pending_ads()
    ad    = next((dict(a) for a in ads if a["id"] == ad_id), None)
    if not ad:
        await cb.answer("❌", show_alert=True); return
    await db.update_ad_status(ad_id, "rejected", "Admin rad etdi")
    try:
        u = await db.get_user(ad["owner_id"])
        from utils.keyboards import main_menu_kb
        await cb.bot.send_message(
            ad["owner_id"],
            "❌ Reklamangiz rad etildi.",
            reply_markup=main_menu_kb(
                u["language"] if u else "uz"))
    except: pass
    try:
        txt = (cb.message.caption or cb.message.text or "")
        txt += "\n\n❌ RAD ETILDI"
        if cb.message.caption:
            await cb.message.edit_caption(txt, parse_mode="Markdown")
        else:
            await cb.message.edit_text(txt, parse_mode="Markdown")
    except: pass
    await cb.answer("❌")

@router.callback_query(F.data.startswith("paid_confirm:"))
async def paid_confirm(cb: CallbackQuery):
    tg_id = cb.from_user.id
    ad_id = int(cb.data.split(":")[1])
    u     = await db.get_user(tg_id)
    lang  = u["language"] if u else "uz"
    await db.update_ad_status(ad_id, "payment_pending")
    await db.sec_log(tg_id, "PAYMENT_CLAIMED", f"ad={ad_id}")
    for aid in ADMIN_IDS:
        try:
            await cb.bot.send_message(
                aid,
                f"💰 *To'lov da'vosi*\n"
                f"👤 `{tg_id}` | @{cb.from_user.username or '—'}\n"
                f"📢 Reklama #{ad_id}",
                parse_mode="Markdown")
        except: pass
    from locales import t
    from utils.keyboards import main_menu_kb
    await cb.message.edit_text(
        t("pay_pending", lang),
        parse_mode="Markdown",
        reply_markup=main_menu_kb(lang))
    await cb.answer("✅")

@router.callback_query(F.data == "adm_weekly")
async def adm_weekly(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    top     = await db.get_top_referrers(100)
    rewards = db.calc_weekly_rewards(len(top))
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Taqsimlashni boshlash",
              callback_data="adm_weekly_go")
    kb.button(text="◀️ Orqaga", callback_data="adm_stats")
    kb.adjust(1)
    txt = (f"🏆 *Haftalik Taqsimlash*\n\n"
           f"👥 {len(top)} ishtirokchi\n"
           f"💰 500 GTR\n\n")
    for i, r in enumerate(top[:10]):
        txt += (f"{i+1}. @{r['username'] or r['referrer_id']} "
                f"— {r['ref_count']} → {rewards[i]:.2f} GTR\n")
    await cb.message.edit_text(txt, parse_mode="Markdown",
                               reply_markup=kb.as_markup())
    await cb.answer()

@router.callback_query(F.data == "adm_weekly_go")
async def adm_weekly_go(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    await db.distribute_weekly_rewards(cb.bot)
    await cb.message.edit_text(
        "✅ *500 GTR tarqatildi!*",
        parse_mode="Markdown")
    await cb.answer("✅ Bajarildi!")

@router.message(Command("broadcast"))
async def broadcast(msg: Message):
    if not is_admin(msg.from_user.id): return
    text = msg.text.replace("/broadcast", "").strip()
    if not text:
        await msg.answer("❌ /broadcast <matn>"); return
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as dbc:
        async with dbc.execute(
            "SELECT tg_id FROM users WHERE is_banned=0"
        ) as c:
            users = await c.fetchall()
    sent = 0
    for (uid,) in users:
        try:
            await msg.bot.send_message(
                uid,
                f"📣 *GTR Yangilik:*\n\n{text}",
                parse_mode="Markdown")
            sent += 1
        except: pass
    await msg.answer(f"✅ {sent} ta foydalanuvchiga yuborildi.")
