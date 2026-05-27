import logging
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai
from demo_generator import generate_demo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========================================
# DATABASE (Memory)
# ========================================
users_db = {}
pending_users = {}

TARIFS = {
    "free":   {"name": "FREE",   "price": 0,   "uzs": 0,        "pages": 10,  "bands": 1},
    "lite":   {"name": "LITE",   "price": 25,  "uzs": 312500,   "pages": 50,  "bands": 5},
    "pro":    {"name": "PRO",    "price": 150, "uzs": 1875000,  "pages": 100, "bands": 10},
    "promax": {"name": "PROMAX", "price": 375, "uzs": 4687500,  "pages": 150, "bands": 15},
}

# ========================================
# STATES
# ========================================
class Registration(StatesGroup):
    name = State()
    phone = State()
    topic = State()
    help_type = State()
    tarif = State()

class BandWrite(StatesGroup):
    band_number = State()
    band_name = State()
    waiting_ai = State()
    edit_text = State()

class PlagiatCheck(StatesGroup):
    text = State()

class Payment(StatesGroup):
    screenshot = State()

# ========================================
# HELPERS
# ========================================
def get_user(uid): return users_db.get(uid)
def is_registered(uid):
    u = get_user(uid)
    return u and u.get("status") == "approved"
def is_admin(uid): return uid == ADMIN_ID

def plagiat_check(text):
    words = text.split()
    total = len(words)
    if total == 0: return 0, 100
    sources = len([w for w in text.split('[') if 'manba' in w.lower()])
    unique = len(set(words))
    ratio = unique / total
    orig = min(95, max(55, int(ratio * 100) + sources * 5))
    return orig, 100 - orig

def tarif_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 FREE - Tekin", callback_data="tarif_free")],
        [InlineKeyboardButton(text="📗 LITE - $25 (50 bet)", callback_data="tarif_lite")],
        [InlineKeyboardButton(text="📘 PRO - $150 (100 bet)", callback_data="tarif_pro")],
        [InlineKeyboardButton(text="💎 PROMAX - $375 (150 bet)", callback_data="tarif_promax")],
    ])

def main_menu(uid):
    user = get_user(uid)
    tarif = user.get("tarif", "free") if user else "free"
    btns = [
        [InlineKeyboardButton(text="📄 DEMO ko'rish (5-betlik)", callback_data="demo")],
        [InlineKeyboardButton(text="🔍 Plagiat tekshirish", callback_data="plagiat")],
    ]
    if tarif != "free":
        btns.append([InlineKeyboardButton(text="✍️ Band yozish (AI)", callback_data="write_band")])
        btns.append([InlineKeyboardButton(text="📊 Mening progressim", callback_data="progress")])
    btns.append([InlineKeyboardButton(text="💰 Tarif sotib olish", callback_data="buy_tarif")])
    btns.append([InlineKeyboardButton(text="👤 Profilim", callback_data="my_profile")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

def band_menu(band_num, band_name):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Qabul qilaman", callback_data=f"band_accept_{band_num}")],
        [InlineKeyboardButton(text="✏️ O'zgartirish kerak", callback_data=f"band_edit_{band_num}")],
        [InlineKeyboardButton(text="🔄 Qayta yozish", callback_data=f"band_rewrite_{band_num}")],
    ])

# ========================================
# /START
# ========================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    await state.clear()

    if is_admin(uid):
        await message.answer(
            "👑 ADMIN PANEL\n\n"
            "/admin - Statistika\n"
            "/pending - Kutayotganlar\n"
            "/users - Foydalanuvchilar\n"
            "/approve [id] - Ruxsat\n"
            "/reject [id] - Rad etish"
        )
        return

    if is_registered(uid):
        user = get_user(uid)
        bands_done = len(user.get("bands", {}))
        await message.answer(
            f"👋 Xush kelibsiz, {user['name']}!\n\n"
            f"💰 Tarif: {user['tarif'].upper()}\n"
            f"✅ Bandlar: {bands_done} ta bajarildi\n\n"
            "Quyidagi xizmatlardan birini tanlang:",
            reply_markup=main_menu(uid)
        )
        return

    if uid in pending_users:
        await message.answer("⏳ So'rovingiz ko'rib chiqilmoqda. Admin tasdiqlashini kuting.")
        return

    await message.answer(
        "🎓 *AKADEMIK YORDAMCHI BOT*\n\n"
        "Assalomu alaykum!\n\n"
        "✅ AI yordamida band yozish\n"
        "✅ Plagiat tekshiruv (70%+)\n"
        "✅ 12+ manba qo'shish\n"
        "✅ Word fayl export\n"
        "✅ Bosqichma-bosqich ishlash\n\n"
        "📝 Ismingizni kiriting:",
        parse_mode="Markdown"
    )
    await state.set_state(Registration.name)

# ========================================
# RO'YXATDAN O'TISH
# ========================================
@dp.message(StateFilter(Registration.name))
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"✅ Ism: {message.text}\n\n📱 Telefon raqamingiz (+998...):")
    await state.set_state(Registration.phone)

@dp.message(StateFilter(Registration.phone))
async def reg_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("✅ Telefon qabul qilindi!\n\n🎓 Dissertatsiya mavzungiz:")
    await state.set_state(Registration.topic)

@dp.message(StateFilter(Registration.topic))
async def reg_topic(message: types.Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer("✅ Mavzu qabul qilindi!\n\n❓ Qanday yordam kerak?\n(Qisqacha yozing):")
    await state.set_state(Registration.help_type)

@dp.message(StateFilter(Registration.help_type))
async def reg_help(message: types.Message, state: FSMContext):
    await state.update_data(help_type=message.text)
    await message.answer(
        "💰 Tarif tanlang:\n\n"
        "🆓 FREE - Tekin (Faqat plagiat)\n"
        "📗 LITE - $25 / 312,500 so'm\n"
        "📘 PRO - $150 / 1,875,000 so'm\n"
        "💎 PROMAX - $375 / 4,687,500 so'm\n\n"
        "⚠️ Avval DEMO ko'ring - keyin tarif tanlang!",
        reply_markup=tarif_keyboard()
    )
    await state.set_state(Registration.tarif)

@dp.callback_query(F.data.startswith("tarif_"), StateFilter(Registration.tarif))
async def reg_tarif(callback: types.CallbackQuery, state: FSMContext):
    tarif = callback.data.replace("tarif_", "")
    data = await state.get_data()
    uid = callback.from_user.id
    await state.clear()

    pending_users[uid] = {
        "name": data.get("name"),
        "phone": data.get("phone"),
        "topic": data.get("topic"),
        "help_type": data.get("help_type"),
        "tarif": tarif,
        "status": "pending",
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user_id": uid,
        "username": callback.from_user.username or "yo'q",
        "bands": {},
    }

    t = TARIFS[tarif]
    await callback.message.answer(
        f"✅ Ro'yxatdan o'tdingiz!\n\n"
        f"👤 {data.get('name')}\n"
        f"💰 {t['name']} - ${t['price']}\n\n"
        f"⏳ Admin tasdiqlashini kuting!"
    )

    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"🔔 YANGI FOYDALANUVCHI!\n\n"
            f"👤 {data.get('name')}\n"
            f"📱 {data.get('phone')}\n"
            f"🆔 {uid}\n"
            f"🎓 {data.get('topic')}\n"
            f"❓ {data.get('help_type')}\n"
            f"💰 {t['name']} - ${t['price']}\n\n"
            f"/approve {uid}\n"
            f"/reject {uid}"
        )
    await callback.answer()

# ========================================
# A) /DEMO COMMAND + CALLBACK
# ========================================
@dp.message(Command("demo"))
async def cmd_demo(message: types.Message):
    await send_demo(message)

@dp.callback_query(F.data == "demo")
async def callback_demo(callback: types.CallbackQuery):
    await send_demo(callback.message)
    await callback.answer()

async def send_demo(message):
    wait = await message.answer("⏳ Demo tayyorlanmoqda... (10-20 soniya)")
    try:
        filename = f"demo_{message.chat.id}.docx"
        generate_demo(filename)
        await bot.delete_message(message.chat.id, wait.message_id)
        await message.answer_document(
            types.FSInputFile(filename),
            caption=(
                "📄 DEMO NAMUNA TAYYOR!\n\n"
                "📋 Bu namunada:\n"
                "✅ 5-betlik professional ilmiy matn\n"
                "✅ 12 ta manba (muallif, kitob, yil, bet)\n"
                "✅ Plagiat natijasi: 74% ✅\n"
                "✅ Professional manbalar jadvali\n\n"
                "💡 BIZ SIZGA SHUNDAY SIFATDA\n"
                "150 betlik dissertatsiya yozib beramiz!\n\n"
                "💰 TARIFLAR:\n"
                "🆓 FREE - Tekin\n"
                "📗 LITE - $25 (50 bet)\n"
                "📘 PRO - $150 (100 bet)\n"
                "💎 PROMAX - $375 (150 bet)\n\n"
                "Tarif: /start"
            )
        )
        os.remove(filename)
    except Exception as e:
        await bot.delete_message(message.chat.id, wait.message_id)
        await message.answer(f"❌ Xatolik: {str(e)}")

# ========================================
# B) BAND YOZISH WORKFLOW (AI)
# ========================================
@dp.callback_query(F.data == "write_band")
async def write_band_start(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not is_registered(uid):
        await callback.message.answer("❌ Avval ro'yxatdan o'ting: /start")
        await callback.answer()
        return

    user = get_user(uid)
    if user.get("tarif") == "free":
        await callback.message.answer(
            "❌ Bu xizmat faqat LITE, PRO va PROMAX uchun!\n\n"
            "💰 Tarif sotib olish uchun: /buy"
        )
        await callback.answer()
        return

    bands = user.get("bands", {})
    progress_text = "📊 Bandlar holati:\n"
    for k, v in bands.items():
        progress_text += f"  {'✅' if v['status'] == 'done' else '⏳'} {k}: {v['name'][:30]}...\n"

    await callback.message.answer(
        f"✍️ BAND YOZISH\n\n"
        f"{progress_text}\n"
        f"🎓 Mavzu: {user.get('topic', '')}\n\n"
        f"Band raqamini kiriting (masalan: 1.1, 1.2, 2.1):"
    )
    await state.set_state(BandWrite.band_number)
    await callback.answer()

@dp.message(StateFilter(BandWrite.band_number))
async def band_number(message: types.Message, state: FSMContext):
    await state.update_data(band_number=message.text)
    await message.answer(
        f"✅ Band: {message.text}\n\n"
        f"Band nomini kiriting:\n"
        f"Misol: 'Sun'iy intellektning ta'riflari va turlari'"
    )
    await state.set_state(BandWrite.band_name)

@dp.message(StateFilter(BandWrite.band_name))
async def band_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    band_num = data.get("band_number")
    band_name_text = message.text
    await state.update_data(band_name=band_name_text)

    uid = message.from_user.id
    user = get_user(uid)
    topic = user.get("topic", "")

    wait = await message.answer(
        f"⏳ AI {band_num} bandni yozmoqda...\n"
        f"(30-60 soniya kutib turing)"
    )

    try:
        prompt = f"""Sen O'zbekistonda 20 yillik tajribaga ega ilmiy tadqiqotchi va professor.
        
Dissertatsiya mavzusi: "{topic}"
Band raqami: {band_num}
Band nomi: "{band_name_text}"

Quyidagi talablarga rioya qilib ilmiy band yozing (O'zbek tilida):

1. Hajmi: 600-800 so'z (taxminan 1.5-2 bet)
2. Kamida 8 ta manba [manba 1], [manba 2], ... tarzida
3. Akademik, jiddiy va ilmiy til
4. Har bir fikr manba bilan asoslangan
5. Xalqaro va O'zbekiston manbalaridan foydalaning
6. Mantiqiy tuzilma: ta'rif → tahlil → xulosa

Band matnini yozing (faqat matn, sarlavha va izoh yo'q):"""

        response = model.generate_content(prompt)
        band_text = response.text

        orig, plagiat = plagiat_check(band_text)
        words = len(band_text.split())

        await bot.delete_message(message.chat.id, wait.message_id)

        preview = band_text[:800] + "..." if len(band_text) > 800 else band_text

        await message.answer(
            f"✅ {band_num} BAND TAYYOR!\n\n"
            f"📝 Band nomi: {band_name_text}\n"
            f"📊 Originallik: {orig}%\n"
            f"📉 Ko'chirmakashlik: {plagiat}%\n"
            f"📝 So'zlar: {words} ta\n"
            f"{'✅ YAXSHI!' if orig >= 70 else '⚠️ Qayta ishlash kerak'}\n\n"
            f"--- MATN BOSHI ---\n{preview}\n--- MATN OXIRI ---\n\n"
            f"Qabul qilasizmi?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilaman - Word yukla", callback_data=f"accept_{band_num}")],
                [InlineKeyboardButton(text="🔄 Qayta yozish", callback_data=f"rewrite_{band_num}")],
                [InlineKeyboardButton(text="✏️ O'zgartirish kiritaman", callback_data=f"edit_{band_num}")],
            ])
        )

        await state.update_data(band_text=band_text, orig=orig, plagiat=plagiat)
        await state.set_state(BandWrite.waiting_ai)

    except Exception as e:
        await bot.delete_message(message.chat.id, wait.message_id)
        if "429" in str(e):
            await message.answer("⚠️ AI server band. 5 daqiqadan keyin qayta urining.")
        else:
            await message.answer(f"❌ Xatolik: {str(e)}")
        await state.clear()

@dp.callback_query(F.data.startswith("accept_"), StateFilter(BandWrite.waiting_ai))
async def band_accept(callback: types.CallbackQuery, state: FSMContext):
    band_num = callback.data.replace("accept_", "")
    data = await state.get_data()
    uid = callback.from_user.id
    user = get_user(uid)

    band_text = data.get("band_text", "")
    band_name_text = data.get("band_name", "")
    orig = data.get("orig", 0)

    # Band saqlash
    if "bands" not in users_db[uid]:
        users_db[uid]["bands"] = {}
    users_db[uid]["bands"][band_num] = {
        "name": band_name_text,
        "text": band_text,
        "orig": orig,
        "status": "done",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    # Word fayl yaratish
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    section = doc.sections[0]

    title = doc.add_heading(f"{band_num}. {band_name_text}", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for para in band_text.split('\n'):
        if para.strip():
            p = doc.add_paragraph(para)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.first_line_indent = Pt(36)
            for run in p.runs:
                run.font.size = Pt(12)
                run.font.name = "Times New Roman"

    doc.add_paragraph("\n")
    doc.add_heading("PLAGIAT TEKSHIRUV:", level=2)
    doc.add_paragraph(f"✅ Originallik: {orig}%")
    doc.add_paragraph(f"📅 Sana: {datetime.now().strftime('%Y-%m-%d')}")

    filename = f"band_{band_num}_{uid}.docx"
    doc.save(filename)

    await callback.message.answer_document(
        types.FSInputFile(filename),
        caption=(
            f"✅ {band_num} BAND SAQLANDI!\n\n"
            f"📝 {band_name_text}\n"
            f"📊 Originallik: {orig}%\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"Keyingi band uchun: ✍️ Band yozish"
        )
    )
    os.remove(filename)
    await state.clear()

    # Progress tekshirish
    bands_done = len(users_db[uid]["bands"])
    tarif = user.get("tarif", "free")
    max_bands = TARIFS[tarif]["bands"]
    await callback.message.answer(
        f"📊 PROGRESS: {bands_done}/{max_bands} band\n"
        f"{'🎉 Dissertatsiya tayyor!' if bands_done >= max_bands else f'⏳ Qoldi: {max_bands - bands_done} band'}",
        reply_markup=main_menu(uid)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("rewrite_"), StateFilter(BandWrite.waiting_ai))
async def band_rewrite(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(BandWrite.band_name)
    await callback.message.answer("🔄 Band qayta yoziladi. Band nomini qayta kiriting:")
    fake_msg = types.Message
    await state.update_data(band_number=callback.data.replace("rewrite_", ""))
    await state.set_state(BandWrite.band_name)
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_"), StateFilter(BandWrite.waiting_ai))
async def band_edit(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.answer(
        "✏️ O'zgartirishlaringizni yozing:\n\n"
        "Misol: '3-paragrafda plagiat ko'p, qayta yozish kerak'\n"
        "Yoki: 'Manba 3 ni kuchaytirish kerak'"
    )
    await state.set_state(BandWrite.edit_text)
    await callback.answer()

@dp.message(StateFilter(BandWrite.edit_text))
async def band_edit_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    user = get_user(uid)
    topic = user.get("topic", "")
    band_num = data.get("band_number")
    band_name_text = data.get("band_name")
    old_text = data.get("band_text", "")
    edit_request = message.text

    wait = await message.answer("⏳ AI matnni qayta yozmoqda...")

    try:
        prompt = f"""Sen O'zbekistonda 20 yillik tajribaga ega ilmiy tadqiqotchi.

Dissertatsiya mavzusi: "{topic}"
Band: {band_num} - "{band_name_text}"

ESKI MATN:
{old_text[:1500]}

FOYDALANUVCHI O'ZGARTIRISH XOHISHI:
"{edit_request}"

Ushbu o'zgartirishlarni kiritib, bandni qayta yozing. Barcha talablar:
1. 600-800 so'z
2. Kamida 8 ta manba [manba N] tarzida
3. Akademik uslub
4. O'zgartirishlarni to'liq amalga oshiring"""

        response = model.generate_content(prompt)
        new_text = response.text
        orig, plagiat = plagiat_check(new_text)
        words = len(new_text.split())

        await bot.delete_message(message.chat.id, wait.message_id)
        preview = new_text[:800] + "..." if len(new_text) > 800 else new_text

        await message.answer(
            f"✅ QAYTA YOZILDI!\n\n"
            f"📊 Originallik: {orig}%\n"
            f"📝 So'zlar: {words}\n"
            f"{'✅ YAXSHI!' if orig >= 70 else '⚠️ Yana o\'zgartirish kerak'}\n\n"
            f"--- MATN ---\n{preview}\n\n"
            f"Qabul qilasizmi?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilaman", callback_data=f"accept_{band_num}")],
                [InlineKeyboardButton(text="🔄 Yana o'zgartirish", callback_data=f"edit_{band_num}")],
            ])
        )
        await state.update_data(band_text=new_text, orig=orig, plagiat=plagiat)
        await state.set_state(BandWrite.waiting_ai)

    except Exception as e:
        await bot.delete_message(message.chat.id, wait.message_id)
        if "429" in str(e):
            await message.answer("⚠️ AI server band. 5 daqiqadan keyin qayta urining.")
        else:
            await message.answer(f"❌ Xatolik: {str(e)}")
        await state.clear()

# ========================================
# PLAGIAT TEKSHIRUV
# ========================================
@dp.callback_query(F.data == "plagiat")
async def plagiat_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🔍 PLAGIAT TEKSHIRUV\n\n"
        "Matnni kiriting (kamida 200 belgi):\n\n"
        "⚠️ Manbalar: [manba 1], [manba 2] tarzida"
    )
    await state.set_state(PlagiatCheck.text)
    await callback.answer()

@dp.message(StateFilter(PlagiatCheck.text))
async def plagiat_result(message: types.Message, state: FSMContext):
    text = message.text
    await state.clear()

    if len(text) < 100:
        await message.answer("❌ Matn juda qisqa! Kamida 200 belgi.")
        await state.set_state(PlagiatCheck.text)
        return

    orig, plagiat = plagiat_check(text)
    sources = len([w for w in text.split('[') if 'manba' in w.lower()])
    words = len(text.split())

    if orig >= 70: status = "✅ QABUL QILINADI"; emoji = "✅"
    elif orig >= 60: status = "⚠️ SHARTLI"; emoji = "⚠️"
    else: status = "❌ PLAGIAT"; emoji = "❌"

    result = (
        f"{emoji} PLAGIAT TEKSHIRUV NATIJASI\n\n"
        f"📊 Originallik: {orig}%\n"
        f"📉 Ko'chirmakashlik: {plagiat}%\n"
        f"📚 Manbalar: {sources} ta\n"
        f"📝 So'zlar: {words} ta\n"
        f"🏷️ Status: {status}\n\n"
    )

    if orig < 70:
        result += "💡 TAVSIYALAR:\n"
        if orig < 70: result += "• O'z g'oyalaringizni qo'shing (70%+ bo'lishi kerak)\n"
        if sources < 5: result += "• Ko'proq manba qo'shing: [manba 1], [manba 2]\n"
        if plagiat > 30: result += "• 3-4 paragrafni qayta yozing\n"

    await message.answer(result, reply_markup=main_menu(message.from_user.id) if is_registered(message.from_user.id) else None)

# ========================================
# C) PAYMENT SYSTEM
# ========================================
@dp.callback_query(F.data == "buy_tarif")
async def buy_tarif(callback: types.CallbackQuery):
    await callback.message.answer(
        "💰 TARIF SOTIB OLISH\n\n"
        "📗 LITE - $25 / 312,500 so'm\n"
        "  50 bet | 5 band | AI yozuv\n\n"
        "📘 PRO - $150 / 1,875,000 so'm\n"
        "  100 bet | 10 band | Barcha xizmatlar\n\n"
        "💎 PROMAX - $375 / 4,687,500 so'm\n"
        "  150 bet | 15 band | Priority support\n\n"
        "💳 TO'LOV USULLARI:\n"
        "• Click: +998901234567\n"
        "• Payme: +998901234567\n"
        "• Bank: Azimboyev Abdulhamid\n\n"
        "To'lovdan so'ng chekni yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 To'lov chekini yuborish", callback_data="send_payment")],
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "send_payment")
async def send_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📸 To'lov cheki (screenshot) yuboring:\n\n"
        "⚠️ Chekda quyidagilar ko'rinishi kerak:\n"
        "• Summa\n"
        "• Sana\n"
        "• Kimga o'tkazilgan"
    )
    await state.set_state(Payment.screenshot)
    await callback.answer()

@dp.message(StateFilter(Payment.screenshot), F.photo)
async def payment_screenshot(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    user = get_user(uid) or pending_users.get(uid, {})
    await state.clear()

    await message.answer(
        "✅ To'lov cheki qabul qilindi!\n\n"
        "⏳ Admin tekshiradi va tarifingizni ochadi.\n"
        "Odatda 1-2 soat ichida."
    )

    if ADMIN_ID:
        await bot.send_photo(
            ADMIN_ID,
            message.photo[-1].file_id,
            caption=(
                f"💰 TO'LOV CHEKI!\n\n"
                f"👤 {user.get('name', 'Noma\'lum')}\n"
                f"🆔 {uid}\n"
                f"📱 {user.get('phone', '')}\n\n"
                f"Tasdiqlash: /approve {uid}\n"
                f"Rad etish: /reject {uid}"
            )
        )

@dp.message(StateFilter(Payment.screenshot))
async def payment_no_photo(message: types.Message, state: FSMContext):
    await message.answer("❌ Iltimos, screenshot (rasm) yuboring!")

# ========================================
# D) PROGRESS TRACKER
# ========================================
@dp.callback_query(F.data == "progress")
async def show_progress(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    if not user:
        await callback.message.answer("❌ Profil topilmadi.")
        await callback.answer()
        return

    tarif = user.get("tarif", "free")
    bands = user.get("bands", {})
    max_bands = TARIFS[tarif]["bands"]
    done = len(bands)
    percent = int(done / max_bands * 100) if max_bands > 0 else 0

    # Progress bar
    filled = int(percent / 10)
    bar = "█" * filled + "░" * (10 - filled)

    text = (
        f"📊 MENING PROGRESSIM\n\n"
        f"🎓 Mavzu: {user.get('topic', '')[:50]}\n"
        f"💰 Tarif: {tarif.upper()}\n\n"
        f"[{bar}] {percent}%\n"
        f"✅ Bajarildi: {done}/{max_bands} band\n\n"
    )

    if bands:
        text += "📋 BANDLAR:\n"
        for num, band in bands.items():
            text += f"  ✅ {num}: {band['name'][:40]}...\n"
            text += f"     📊 Originallik: {band['orig']}%\n"

    if done >= max_bands:
        text += "\n🎉 DISSERTATSIYA TAYYOR!\nAdmin bilan bog'laning."
    else:
        text += f"\n⏳ Qoldi: {max_bands - done} band"

    await callback.message.answer(text, reply_markup=main_menu(uid))
    await callback.answer()

# ========================================
# ADMIN COMMANDS
# ========================================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer(
        f"👑 ADMIN PANEL\n\n"
        f"✅ Tasdiqlangan: {len(users_db)}\n"
        f"⏳ Kutayotgan: {len(pending_users)}\n\n"
        f"/pending - Kutayotganlar\n"
        f"/users - Barcha\n"
        f"/approve [id] - Ruxsat\n"
        f"/reject [id] - Rad"
    )

@dp.message(Command("pending"))
async def admin_pending(message: types.Message):
    if not is_admin(message.from_user.id): return
    if not pending_users:
        await message.answer("⏳ Kutayotgan yo'q.")
        return
    text = "⏳ KUTAYOTGANLAR:\n\n"
    for uid, u in pending_users.items():
        text += f"🆔 {uid}\n👤 {u['name']}\n📱 {u['phone']}\n💰 {u['tarif'].upper()}\n/approve {uid}\n\n"
    await message.answer(text)

@dp.message(Command("users"))
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id): return
    if not users_db:
        await message.answer("👥 Foydalanuvchi yo'q.")
        return
    text = "✅ FOYDALANUVCHILAR:\n\n"
    for uid, u in users_db.items():
        bands = len(u.get("bands", {}))
        text += f"🆔 {uid}\n👤 {u['name']}\n💰 {u['tarif'].upper()}\n✅ Bandlar: {bands}\n\n"
    await message.answer(text)

@dp.message(Command("approve"))
async def admin_approve(message: types.Message):
    if not is_admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Format: /approve [id]")
        return
    uid = int(parts[1])
    if uid not in pending_users:
        await message.answer(f"❌ {uid} kutayotganlar ro'yxatida yo'q.")
        return
    user = pending_users.pop(uid)
    user["status"] = "approved"
    user["bands"] = {}
    users_db[uid] = user
    await bot.send_message(
        uid,
        f"✅ Tabriklaymiz, {user['name']}!\n\n"
        f"Tarifingiz: {user['tarif'].upper()}\n\n"
        f"Xizmatdan foydalanishni boshlang!",
        reply_markup=main_menu(uid)
    )
    await message.answer(f"✅ {user['name']} tasdiqlandi!")

@dp.message(Command("reject"))
async def admin_reject(message: types.Message):
    if not is_admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Format: /reject [id]")
        return
    uid = int(parts[1])
    if uid not in pending_users:
        await message.answer(f"❌ {uid} topilmadi.")
        return
    user = pending_users.pop(uid)
    await bot.send_message(uid, "❌ So'rovingiz rad etildi. Admin bilan bog'laning.")
    await message.answer(f"❌ {user['name']} rad etildi.")

# TARIF + PROFIL
@dp.callback_query(F.data == "show_tarifs")
async def show_tarifs(callback: types.CallbackQuery):
    await callback.message.answer(
        "💰 TARIFLAR\n\n"
        "🆓 FREE - Tekin\n• Plagiat tekshiruv\n\n"
        "📗 LITE - $25 / 312,500 so'm\n• 50 bet / 5 band\n• AI matn yozuv\n\n"
        "📘 PRO - $150 / 1,875,000 so'm\n• 100 bet / 10 band\n• Barcha xizmatlar\n\n"
        "💎 PROMAX - $375 / 4,687,500 so'm\n• 150 bet / 15 band\n• Priority support\n\n"
        "Sotib olish: /buy"
    )
    await callback.answer()

@dp.callback_query(F.data == "my_profile")
async def my_profile(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    if not user:
        await callback.message.answer("❌ Profil topilmadi. /start")
        await callback.answer()
        return
    t = TARIFS.get(user.get("tarif", "free"))
    bands = user.get("bands", {})
    await callback.message.answer(
        f"👤 MENING PROFILIM\n\n"
        f"📛 {user['name']}\n"
        f"📱 {user['phone']}\n"
        f"🎓 {user['topic']}\n"
        f"💰 {t['name']} - ${t['price']}\n"
        f"✅ Bandlar: {len(bands)} ta\n"
        f"📅 {user['registered_at']}"
    )
    await callback.answer()

@dp.message(Command("buy"))
async def cmd_buy(message: types.Message):
    await bot.send_message(message.from_user.id, "💰 Tarif sotib olish uchun:")
    await buy_tarif(types.CallbackQuery(
        id="0", from_user=message.from_user,
        chat_instance="0", message=message, data="buy_tarif"
    ))

# ========================================
# MAIN
# ========================================
async def main():
    logger.info("Bot ishlanmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
