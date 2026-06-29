from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db
from locales import t
from config import GTR_GROUP_ID, GTR_CHANNEL_ID, BOT_USERNAME

router = Router()

async def _lang(tg_id):
    u = await db.get_user(tg_id)
    return u["language"] if u else "uz"

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    tg_id = msg.from_user.id
    args  = msg.text.split()
    ref_code = args[1] if len(args) > 1 else None
    ref_by = None
    if ref_code:
        referrer = await db.get_user_by_ref(ref_code)
        if referrer and referrer["tg_id"] != tg_id:
            ref_by = referrer["tg_id"]
    existing = await db.get_user(tg_id)
    await db.upsert_user(tg_id, msg.from_user.username,
                         msg.from_user.full_name,
                         referred_by=ref_by if not existing else None)
    if not existing and ref_by:
        await db.add_referral(ref_by, tg_id)
        new_bal = await db.add_bonus(ref_by, 0.01, "referral_join", f"ref={tg_id}")
        try:
            await msg.bot.send_message(ref_by,
                f"🎉 *Yangi taklif!*\n💰 *+0.01 GTR*\n💎 Balans: *{new_bal:.3f} GTR*",
                parse_mode="Markdown")
        except: pass
    if not existing:
        from utils.keyboards import lang_kb
        await msg.answer(t("welcome", "uz"), parse_mode="Markdown",
                         reply_markup=lang_kb())
    else:
        lang = existing["language"] or "uz"
        from utils.keyboards import main_menu_kb
        await msg.answer(t("main_menu", lang), parse_mode="Markdown",
                         reply_markup=main_menu_kb(lang))

@router.callback_query(F.data.startswith("lang:"))
async def set_lang(cb: CallbackQuery):
    lang = cb.data.split(":")[1]
    await db.update_user(cb.from_user.id, language=lang)
    from utils.keyboards import main_menu_kb
    await cb.message.edit_text(t("main_menu", lang), parse_mode="Markdown",
                               reply_markup=main_menu_kb(lang))
    await cb.answer()

@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await _lang(cb.from_user.id)
    from utils.keyboards import main_menu_kb
    await cb.message.edit_text(t("main_menu", lang), parse_mode="Markdown",
                               reply_markup=main_menu_kb(lang))
    await cb.answer()

@router.callback_query(F.data == "settings")
async def settings(cb: CallbackQuery):
    lang = await _lang(cb.from_user.id)
    from utils.keyboards import settings_kb
    await cb.message.edit_text("⚙️ *Til tanlang:*", parse_mode="Markdown",
                               reply_markup=settings_kb(lang))
    await cb.answer()

@router.callback_query(F.data.startswith("set_lang:"))
async def update_lang(cb: CallbackQuery):
    lang = cb.data.split(":")[1]
    await db.update_user(cb.from_user.id, language=lang)
    from utils.keyboards import settings_kb
    await cb.message.edit_text("✅ Til o'zgartirildi",
                               reply_markup=settings_kb(lang))
    await cb.answer()

@router.callback_query(F.data == "daily_bonus")
async def daily_bonus(cb: CallbackQuery):
    tg_id = cb.from_user.id
    lang  = await _lang(tg_id)
    if await db.check_daily_bonus(tg_id):
        await cb.answer(t("daily_already", lang), show_alert=True)
        return
    bal = await db.claim_daily_bonus(tg_id)
    from utils.keyboards import main_menu_kb
    await cb.message.edit_text(t("daily_ok", lang, bal=f"{bal:.3f}"),
                               parse_mode="Markdown",
                               reply_markup=main_menu_kb(lang))
    await cb.answer("💰 +0.1 GTR!")

@router.callback_query(F.data == "my_ref")
async def my_ref(cb: CallbackQuery):
    tg_id = cb.from_user.id
    lang  = await _lang(tg_id)
    user  = await db.get_user(tg_id)
    if not user:
        await cb.answer("❌ /start bosing", show_alert=True)
        return
    total = await db.get_referral_count(tg_id)
    top   = await db.get_top_referrers(100)
    week  = next((r["
