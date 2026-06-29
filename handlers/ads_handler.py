from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db
from locales import t
from config import CATEGORIES, TARIFFS, ADMIN_IDS

router = Router()

class AdPost(StatesGroup):
    category    = State()
    title       = State()
    description = State()
    channel     = State()
    image       = State()
    tariff      = State()

async def _lang(tg_id):
    u = await db.get_user(tg_id)
    return u["language"] if u else "uz"

@router.callback_query(F.data == "post_ad")
async def post_ad(cb: CallbackQuery, state: FSMContext):
    tg_id = cb.from_user.id
    lang  = await _lang(tg_id)
    user  = await db.get_user(tg_id)
    if not user or user["kyc_status"] != "verified":
        await cb.answer(t("kyc_required", lang), show_alert=True)
        return
    await state.set_state(AdPost.category)
    from utils.keyboards import categories_kb
    await cb.message.edit_text("📁 *Kategoriya tanlang:*",
                               parse_mode="Markdown",
                               reply_markup=categories_kb(lang, "ad"))
    await cb.answer()

@router.callback_query(AdPost.category, F.data.startswith("ad_cat:"))
async def got_cat(cb: CallbackQuery, state: FSMContext):
    await state.update_data(category=cb.data.split(":")[1])
    await state.set_state(AdPost.title)
    await cb.message.edit_text("📌 Sarlavha (max 60 belgi):",
                               parse_mode="Markdown")
    await cb.answer()

@router.message(AdPost.title)
async def got_title(msg: Message, state: FSMContext):
    from utils.helpers import sanitize, has_banned
    title = sanitize(msg.text, 60)
    if has_banned(title):
        await msg.answer("🚫 Taqiqlangan so'z.")
        return
    if len(title) < 3:
        await msg.answer("❌ Kamida 3 belgi.")
        return
    await state.update_data(title=title)
    await state.set_state(AdPost.description)
    await msg.answer("📝 Tavsif (max 300 belgi):",
                     parse_mode="Markdown")

@router.message(AdPost.description)
async def got_desc(msg: Message, state: FSMContext):
    from utils.helpers import sanitize, has_banned
    desc = sanitize(msg.text, 300)
    if has_banned(desc):
        await msg.answer("🚫 Taqiqlangan so'z.")
        return
    await state.update_data(description=desc)
    await state.set_state(AdPost.channel)
    await msg.answer("📢 Kanal/guruh linki (@kanalim):",
                     parse_mode="Markdown")

@router.message(AdPost.channel)
async def got_channel(msg: Message, state: FSMContext):
    from utils.helpers import sanitize
    await state.update_data(channel_link=sanitize(msg.text, 100))
    await state.set_state(AdPost.image)
    await msg.answer("🖼 Rasm yuboring (yoki /skip):",
                     parse_mode="Markdown")

@router.message(AdPost.image, F.photo)
async def got_image(msg: Message, state: FSMContext):
    await state.update_data(image_fid=msg.photo[-1].file_id)
    await _show_tariff(msg, state)

@router.message(AdPost.image, F.text.startswith("/skip"))
async def skip_image(msg: Message, state: FSMContext):
    await state.update_data(image_fid=None)
    await _show_tariff(msg, state)

async def _show_tariff(msg, state):
    lang = await _lang(msg.from_user.id)
    await state.set_state(AdPost.tariff)
    from utils.keyboards import tariff_kb
    await msg.answer(t("tariff_info", lang),
                     parse_mode="Markdown",
                     reply_markup=tariff_kb(lang))

@router.callback_query(AdPost.tariff, F.data.startswith("tariff:"))
async def got_tariff(cb: CallbackQuery, state: FSMContext):
    tkey   = cb.data.split(":")[1]
    tg_id  = cb.from_user.id
    lang   = await _lang(tg_id)
    data   = await state.get_data()
    tariff = TARIFFS[tkey]
    ad_id  = await db.create_ad(tg_id, {
        "title":        data.get("title"),
        "description":  data.get("description"),
        "category":     data.get("category"),
        "channel_link": data.get("channel_link"),
        "image_fid":    data.get("image_fid"),
        "tariff":       tkey,
        "ton_amount":   tariff["ton"],
    })
    await db.sec_log(tg_id, "AD_CREATED", f"ad_id={ad_id}")
    await state.clear()
    from utils.keyboards import main_menu_kb, admin_ad_kb
    await cb.message.edit_text(t("ad_submitted", lang),
                               parse_mode="Markdown",
                               reply_markup=main_menu_kb(lang))
    review = (
        f"📢 *Yangi Reklama #{ad_id}*\n"
        f"👤 @{cb.from_user.username or tg_id}\n"
        f"📁 {CATEGORIES.get(data.get('category',''), '—')}\n"
        f"📌 {data.get('title')}\n"
        f"📝 {(data.get('description') or '')[:100]}\n"
        f"📢 {data.get('channel_link','—')}\n"
        f"💎 {tariff['name']} — {tariff['ton']} TON"
    )
    for aid in ADMIN_IDS:
        try:
            if data.get("image_fid"):
                await cb.bot.send_photo(
                    aid, data["image_fid"],
                    caption=review, parse_mode="Markdown",
                    reply_markup=admin_ad_kb(ad_id))
            else:
                await cb.bot.send_message(
                    aid, review, parse_mode="Markdown",
                    reply_markup=admin_ad_kb(ad_id))
        except: pass
    await cb.answer("✅")

@router.callback_query(F.data == "search_ads")
async def search_ads(cb: CallbackQuery):
    lang = await _lang(cb.from_user.id)
    from utils.keyboards import categories_kb
    await cb.message.edit_text("🔍 *Kategoriya tanlang:*",
                               parse_mode="Markdown",
                               reply_markup=categories_kb(lang, "search"))
    await cb.answer()

@router.callback_query(F.data.startswith("search_cat:"))
async def show_ads(cb: CallbackQuery):
    cat   = cb.data.split(":")[1]
    tg_id = cb.from_user.id
    lang  = await _lang(tg_id)
    ads   = await db.get_active_ads(category=cat, limit=10)
    if not ads:
        from utils.keyboards import main_menu_kb
        await cb.message.edit_text(t("no_ads", lang),
                                   parse_mode="Markdown",
                                   reply_markup=main_menu_kb(lang))
        await cb.answer()
        return
    await cb.message.edit_text(
        f"📢 *{len(ads)} ta reklama:*",
        parse_mode="Markdown")
    from utils.helpers import fmt_ad
    from utils.keyboards import ad_view_kb
    for ad in ads:
        ad_d = dict(ad)
        await db.increment_ad_views(ad_d["id"])
        await db.give_ad_view_bonus(tg_id, ad_d["id"])
        try:
            if ad_d.get("image_fid"):
                await cb.message.answer_photo(
                    ad_d["image_fid"],
                    caption=fmt_ad(ad_d, lang),
                    parse_mode="Markdown",
                    reply_markup=ad_view_kb(ad_d["id"], lang))
            else:
                await cb.message.answer(
                    fmt_ad(ad_d, lang),
                    parse_mode="Markdown",
                    reply_markup=ad_view_kb(ad_d["id"], lang))
        except: pass
    await cb.answer()

@router.callback_query(F.data.startswith("ad_contact:"))
async def ad_contact(cb: CallbackQuery):
    await cb.answer("📢 Kanal linkiga kiring!", show_alert=True)

@router.callback_query(F.data.startswith("ad_report:"))
async def ad_report(cb: CallbackQuery):
    await db.sec_log(cb.from_user.id, "AD_REPORT",
                     f"ad={cb.data.split(':')[1]}")
    await cb.answer("🚩 Shikoyat qabul qilindi.", show_alert=True)

@router.callback_query(F.data == "my_ads")
async def my_ads(cb: CallbackQuery):
    tg_id = cb.from_user.id
    lang  = await _lang(tg_id)
    ads   = await db.get_my_ads(tg_id)
    if not ads:
        kb = InlineKeyboardBuilder()
        kb.button(text="📢 Reklama berish", callback_data="post_ad")
        kb.button(text="◀️ Orqaga",          callback_data="back_main")
        kb.adjust(1)
        await cb.message.edit_text("📋 Reklamalar yo'q.",
                                   reply_markup=kb.as_markup())
        await cb.answer()
        return
    st_e = {"pending":"⏳","active":"✅",
            "rejected":"❌","payment_pending":"💳"}
    text = "📋 *Reklamalarim:*\n\n"
    for ad in ads:
        ad = dict(ad)
        text += (f"{st_e.get(ad['status'],'❓')} "
                 f"*{ad['title']}* — {ad.get('views',0)} 👁\n")
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Yangi reklama", callback_data="post_ad")
    kb.button(text="◀️ Orqaga",        callback_data="back_main")
    kb.adjust(1)
    await cb.message.edit_text(text, parse_mode="Markdown",
                               reply_markup=kb.as_markup())
    await cb.answer()
