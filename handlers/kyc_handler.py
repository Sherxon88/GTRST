from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from locales import t
from config import ADMIN_IDS

router = Router()

class KYC(StatesGroup):
    doc_type   = State()
    full_name  = State()
    birth_date = State()
    doc_number = State()
    front      = State()
    back       = State()
    selfie     = State()
    confirm    = State()

async def _lang(tg_id):
    u = await db.get_user(tg_id)
    return u["language"] if u else "uz"

@router.message(Command("kyc"))
@router.callback_query(F.data == "start_kyc")
async def start_kyc(event, state: FSMContext):
    tg_id = event.from_user.id
    send  = event.message.edit_text if isinstance(event, CallbackQuery) else event.answer
    ans   = event.answer if isinstance(event, CallbackQuery) else None
    user  = await db.get_user(tg_id)
    lang  = user["language"] if user else "uz"
    if user and user["kyc_status"] == "verified":
        msg = "✅ KYC allaqachon tasdiqlangan!"
        if ans: await ans(msg, show_alert=True)
        else: await send(msg)
        return
    if user and user["kyc_status"] == "pending":
        msg = "⏳ KYC hujjatlaringiz tekshirilmoqda..."
        if ans: await ans(msg, show_alert=True)
        else: await send(msg)
        return
    await state.set_state(KYC.doc_type)
    from utils.keyboards import kyc_doc_kb
    await send(t("kyc_intro", lang), parse_mode="Markdown",
               reply_markup=kyc_doc_kb(lang))
    if ans: await ans()

@router.callback_query(KYC.doc_type, F.data.startswith("kyc_doc:"))
async def got_doc_type(cb: CallbackQuery, state: FSMContext):
    await state.update_data(doc_type=cb.data.split(":")[1])
    await state.set_state(KYC.full_name)
    await cb.message.edit_text(
        "✍️ *1/4* — To'liq ism-sharifingizni kiriting:",
        parse_mode="Markdown")
    await cb.answer()

@router.message(KYC.full_name)
async def got_name(msg: Message, state: FSMContext):
    from utils.helpers import sanitize
    name = sanitize(msg.text, 80)
    if len(name) < 3:
        await msg.answer("❌ Kamida 3 belgi."); return
    await state.update_data(full_name=name)
    await state.set_state(KYC.birth_date)
    await msg.answer("🎂 *2/4* — Tug'ilgan sana (15.08.1990):",
                     parse_mode="Markdown")

@router.message(KYC.birth_date)
async def got_birth(msg: Message, state: FSMContext):
    import re
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", msg.text.strip()):
        await msg.answer("❌ Format: 15.08.1990"); return
    await state.update_data(birth_date=msg.text.strip())
    await state.set_state(KYC.doc_number)
    await msg.answer("🔢 *3/4* — Hujjat raqami (AA1234567):",
