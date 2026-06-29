from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db
from locales import t
from config import WIFI_SPEEDS

router = Router()

class WifiSell(StatesGroup):
    title       = State()
    description = State()
    speed       = State()
    location    = State()

class WifiBuy(StatesGroup):
    hours   = State()
    confirm = State()

async def _lang(tg_id):
    u = await db.get_user(tg_id)
    return u["language"] if u else "uz"

@router.callback_query(F.data == "wifi_market")
async def wifi_market(cb: CallbackQuery):
    tg_id = cb.from_user.id
    lang  = await _lang(tg_id)
    user  = await db.get_user(tg_id)
    city  = user["city"] if user else None
    listings = await db.get_wifi_listings(city=city, limit=10)
    if not listings:
        listings = await db.get_wifi_listings(limit=10)
    if not listings:
        kb = InlineKeyboardBuilder()
        kb.button(text="📡 WiFi qo'shish", callback_data="wifi_sell")
        kb.button(text="◀️ Orqaga",         callback_data="back_main")
        kb.adjust(1)
        await cb.message.edit_text(t("no_wifi", lang),
                                   parse_mode="Markdown",
                                   reply_markup=kb.as_markup())
        await cb.answer()
        return
    await cb.message.edit_text(t("wifi_market", lang),
                               parse_mode="Markdown")
    from utils.helpers import fmt_wifi
    from utils.keyboards import wifi_listing_kb
    for lst in listings:
        lst_d = dict(lst)
        kb = wifi_listing_kb(lst_d["id"], lang)
        await cb.message.answer(fmt_wifi(lst_d, lang),
                                parse_mode="Markdown",
                                reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data.startswith("wifi_buy:"))
async def wifi_buy_start(cb: CallbackQuery, state: FSMContext):
    tg_id      = cb.from_user.id
    lang       = await _lang(tg_id)
    listing_id = int(cb.data.split(":")[1])
    user       = await db.get_user(tg_id)
    if not user or user["kyc_status"] != "verified":
        await cb.answer(t("kyc_required", lang), show_alert=True)
        return
    listing = await db.get_listing(listing_id)
    if not listing or not listing["is_active"]:
        await cb.answer("❌ Bu WiFi hozir mavjud emas.", show_alert=True)
        return
    await state.update_data(listing_id=listing_id,
                            gtr_per_hour=listing["gtr_per_hour"],
                            seller_id=listing["seller_id"],
                            title=listing["title"])
    await state.set_state(WifiBuy.hours)
    from utils.keyboards import wifi_hours_kb
    await cb.message.edit_text(
        f"📡 *{listing['title']}*\n\n"
        f"💰 Narx: *{listing['gtr_per_hour']} GTR/soat*\n\n"
        f"⏱ Necha soat?",
        parse_mode="Markdown",
        reply_markup=wifi_hours_kb(lang))
    await cb.answer()

@router.callback_query(WifiBuy.hours, F.data.startswith("wifi_hours:"))
async def wifi_buy_confirm(cb: CallbackQuery, state: FSMContext):
    hours     = float(cb.data.split(":")[1])
    lang      = await _lang(cb.from_user.id)
    data      = await state.get_data()
    gtr_total = round(hours * data["gtr_per_hour"], 4)
    user      = await db.get_user(cb.from_user.id)
    bal       = user["gtr_balance"] if user else 0
    if bal < gtr_total:
        await cb.answer(
            t("no_balance", lang,
              bal=f"{bal:.3f}", need=f"{gtr_total:.3f}"),
            show_alert=True)
        return
    await state.update_data(hours=hours, gtr_total=gtr_total)
    await state.set_state(WifiBuy.confirm)
    kb = InlineKeyboardBuilder()
    kb.button(text=f"✅ To'lash — {gtr_total} GTR",
              callback_data="wifi_pay_confirm")
    kb.button(text="❌ Bekor", callback_data="wifi_market")
    kb.adjust(1)
    await cb.message.edit_text(
        f"📡 *Buyurtma:*\n\n"
        f"🔌 {data['title']}\n"
        f"⏱ {hours} soat\n"
        f"💰 *{gtr_total} GTR*\n\n"
        f"💎 Sizning balansingiz: {bal:.3f} GTR",
        parse_mode="Markdown",
        reply_markup=kb.as_markup())
    await cb.answer()

@router.callback_query(WifiBuy.confirm, F.data == "wifi_pay_confirm")
async def wifi_pay(cb: CallbackQuery, state: FSMContext):
    tg_id = cb.from_user.id
    lang  = await _lang(tg_id)
    data  = await state.get_data()
    await state.clear()
    ok = await db.deduct_balance(tg_id, data["gtr_total"])
    if not ok:
        await cb.answer("❌ Balans yetarli emas!", show_alert=True)
        return
    order_id = await db.create_wifi_order(
        data["listing_id"], tg_id,
        data["seller_id"], data["hours"], data["gtr_total"])
    await db.complete_wifi_order(order_id)
    await db.sec_log(tg_id, "WIFI_ORDER", f"order={order_id}")
    user = await db.get_user(tg_id)
    bal  = user["gtr_balance"] if user else 0
    from utils.keyboards import main_menu_kb
    await cb.message.edit_text(
        f"✅ *Buyurtma bajarildi!*\n\n"
        f"📡 {data['title']}\n"
        f"⏱ {data['hours']} soat\n"
        f"💰 To'landi: *{data['gtr_total']} GTR*\n"
        f"💎 Qolgan: *{bal:.3f} GTR*",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(lang))
    try:
        await cb.bot.send_message(
            data["seller_id"],
            f"🎉 *Yangi buyurtma!*\n\n"
            f"⏱ {data['hours']} soat\n"
            f"💰 *+{round(data['gtr_total']*0.95,4)} GTR*",
            parse_mode="Markdown")
    except: pass
    await cb.answer("✅ Buyurtma tasdiqlandi!")

@router.callback_query(F.data == "wifi_sell")
async def wifi_sell_start(cb: CallbackQuery, state: FSMContext):
    tg_id = cb.from_user.id
    lang  = await _lang(tg_id)
    user  = await db.get_user(tg_id)
    if not user or user["kyc_status"] != "verified":
        await cb.answer(t("kyc_required", lang), show_alert=True)
        return
    await state.set_state(WifiSell.title)
    await cb.message.edit_text(
        t("wifi_sell_intro", lang), parse_mode="Markdown")
    await cb.answer()

@router.message(WifiSell.title)
async def wifi_sell_title(msg: Message, state: FSMContext):
    from utils.helpers import sanitize, has_banned
    title = sanitize(msg.text, 60)
    if has_banned(title):
        await msg.answer("🚫 Taqiqlangan so'z.")
        return
    if len(title) < 3:
        await msg.answer("❌ Kamida 3 belgi.")
        return
    await state.update_data(title=title)
    await state.set_state(WifiSell.description)
    await msg.answer("📝 Qisqacha tavsif (/skip o'tkazib yuborish):")

@router.message(WifiSell.description)
async def wifi_sell_desc(msg: Message, state: FSMContext):
    from utils.helpers import sanitize
    desc = "" if msg.text.startswith("/skip") else sanitize(msg.text, 200)
    await state.update_data(description=desc)
    await state.set_state(WifiSell.speed)
    lang = await _lang(msg.from_user.id)
    from utils.keyboards import wifi_speed_kb
    await msg.answer("⚡ Tezlik rejimini tanlang:",
                     reply_markup=wifi_speed_kb(lang))

@router.callback_query(WifiSell.speed, F.data.startswith("wifi_speed:"))
async def wifi_sell_speed(cb: CallbackQuery, state: FSMContext):
    speed_key = cb.data.split(":")[1]
    speed     = WIFI_SPEEDS[speed_key]
    await state.update_data(speed_plan=speed_key,
                            gtr_per_hour=speed["gtr_per_hour"])
    await state.set_state(WifiSell.location)
    await cb.message.edit_text("📍 Joylashuv nomini kiriting (shahar, ko'cha):")
    await cb.answer()

@router.message(WifiSell.location)
async def wifi_sell_location(msg: Message, state: FSMContext):
    from utils.helpers import sanitize
    tg_id = msg.from_user.id
    lang  = await _lang(tg_id)
    loc   = sanitize(msg.text, 100)
    await state.update_data(location_name=loc)
    data  = await state.get_data()
    await state.clear()
    user  = await db.get_user(tg_id)
    listing_id = await db.create_wifi_listing(tg_id, {
        "title":         data["title"],
        "description":   data.get("description"),
        "speed_plan":    data["speed_plan"],
        "gtr_per_hour":  data["gtr_per_hour"],
        "location_name": loc,
        "city":          user["city"] if user else None,
        "country":       user["country"] if user else None,
    })
    await db.sec_log(tg_id, "WIFI_LISTING_CREATED", f"id={listing_id}")
    speed = WIFI_SPEEDS[data["speed_plan"]]
    from utils.keyboards import main_menu_kb
    await msg.answer(
        f"✅ *WiFi qo'shildi!*\n\n"
        f"📡 {data['title']}\n"
        f"⚡ {speed['name']} — {speed['mbps']} Mbps\n"
        f"💰 {data['gtr_per_hour']} GTR/soat\n"
        f"📍 {loc}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(lang))

@router.callback_query(F.data == "my_wifi")
async def my_wifi(cb: CallbackQuery):
    tg_id    = cb.from_user.id
    lang     = await _lang(tg_id)
    listings = await db.get_my_wifi_listings(tg_id)
    if not listings:
        kb = InlineKeyboardBuilder()
        kb.button(text="📡 WiFi qo'shish", callback_data="wifi_sell")
        kb.button(text="◀️ Orqaga",         callback_data="back_main")
        kb.adjust(1)
        await cb.message.edit_text("📡 Sizda hali WiFi yo'q.",
                                   reply_markup=kb.as_markup())
        await cb.answer()
        return
    text = "📡 *Mening WiFi larim:*\n\n"
    for lst in listings:
        lst = dict(lst)
        st  = "🟢" if lst["is_active"] else "🔴"
        text += (f"{st} *{lst['title']}* — "
                 f"{lst['gtr_per_hour']} GTR/soat | "
                 f"🛒 {lst['total_sales']}\n")
    kb = InlineKeyboardBuilder()
    kb.button(text="📡 Yangi qo'shish", callback_data="wifi_sell")
    kb.button(text="◀️ Orqaga",          callback_data="back_main")
    kb.adjust(1)
    await cb.message.edit_text(text, parse_mode="Markdown",
                               reply_markup=kb.as_markup())
    await cb.answer()

@router.callback_query(F.data == "my_orders")
async def my_orders(cb: CallbackQuery):
    tg_id  = cb.from_user.id
    lang   = await _lang(tg_id)
    orders = await db.get_my_wifi_orders(tg_id)
    from utils.keyboards import main_menu_kb
    if not orders:
        await cb.message.edit_text("📋 Buyurtmalar yo'q.",
                                   reply_markup=main_menu_kb(lang))
        await cb.answer()
        return
    text = "📋 *Buyurtmalarim:*\n\n"
    for o in orders:
        o  = dict(o)
        st = {"pending":"⏳","completed":"✅","cancelled":"❌"}.get(o["status"],"❓")
        text += (f"{st} *{o['wifi_title']}* — "
                 f"{o['hours']}h — {o['gtr_amount']} GTR\n")
    await cb.message.edit_text(text, parse_mode="Markdown",
                               reply_markup=main_menu_kb(lang))
    await cb.answer()
