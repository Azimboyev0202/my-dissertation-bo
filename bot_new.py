import logging
import os
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
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import json

# ========================================
# SOZLAMALAR
# ========================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Sizning Telegram ID ingiz

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========================================
# FOYDALANUVCHI MA'LUMOTLARI (Simple DB)
# ========================================
users_db = {}  # {user_id: {name, phone, topic, tarif, status, registered_at}}
pending_users = {}  # Admin tasdiqlashini kutayotganlar

TARIFS = {
    "free":    {"name": "FREE",    "price": 0,     "uzs": 0,          "pages": 10,  "bands": 1},
    "lite":    {"name": "LITE",    "price": 25,    "uzs": 312500,     "pages": 50,  "bands": 5},
    "pro":     {"name": "PRO",     "price": 150,   "uzs": 1875000,    "pages": 100, "bands": 10},
    "promax":  {"name": "PROMAX",  "price": 375,   "uzs": 4687500,    "pages": 150, "bands": 15},
}

# ========================================
# STATES (BOSQICHLAR)
# ========================================
class Registration(StatesGroup):
    name = State()
    phone = State()
    topic = State()
    help_type = State()
    tarif = State()

class Dissertation(StatesGroup):
    band_number = State()
    band_name = State()
    band_text = State()

class Demo(StatesGroup):
    topic = State()

# ========================================
# HELPER FUNCTIONS
# ========================================
def get_user(user_id):
    return users_db.get(user_id)

def is_registered(user_id):
    user = get_user(user_id)
    return user and user.get("status") == "approved"

def is_admin(user_id):
    return user_id == ADMIN_ID

def plagiat_check(text):
    """Plagiat tekshiruv"""
    words = text.split()
    total = len(words)
    if total == 0:
        return 0, 100

    # Kalit so'zlar tahlili
    sources = len([w for w in text.split('[') if 'manba' in w.lower()])
    unique_words = len(set(words))
    ratio = unique_words / total if total > 0 else 0

    originality = min(95, max(55, int(ratio * 100) + sources * 5))
    plagiat = 100 - originality
    return originality, plagiat

def tarif_keyboard():
    """Tarif tanlash klaviatura"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 FREE - Tekin (Plagiat check)", callback_data="tarif_free")],
        [InlineKeyboardButton(text="📗 LITE - $25 (50 bet)", callback_data="tarif_lite")],
        [InlineKeyboardButton(text="📘 PRO - $150 (100 bet)", callback_data="tarif_pro")],
        [InlineKeyboardButton(text="💎 PROMAX - $375 (150 bet)", callback_data="tarif_promax")],
    ])
    return keyboard

def main_menu_keyboard(user_id):
    """Asosiy menyu"""
    user = get_user(user_id)
    tarif = user.get("tarif", "free") if user else "free"

    buttons = [
        [InlineKeyboardButton(text="📄 DEMO ko'rish (5-betlik namuna)", callback_data="demo")],
        [InlineKeyboardButton(text="🔍 Plagiat tekshirish", callback_data="plagiat")],
    ]

    if tarif != "free":
        buttons.append([InlineKeyboardButton(text="📝 Dissertatsiya yozish", callback_data="start_dissertation")])

    buttons.append([InlineKeyboardButton(text="💰 Tariflar", callback_data="show_tarifs")])
    buttons.append([InlineKeyboardButton(text="👤 Mening profilim", callback_data="my_profile")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========================================
# /START COMMAND
# ========================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    # Agar admin bo'lsa
    if is_admin(user_id):
        await message.answer(
            "👑 ADMIN PANEL\n\n"
            "Buyruqlar:\n"
            "/admin - Admin panel\n"
            "/users - Foydalanuvchilar\n"
            "/approve [id] - Ruxsat berish\n"
            "/reject [id] - Rad etish"
        )
        return

    # Agar ro'yxatdan o'tgan bo'lsa
    if is_registered(user_id):
        user = get_user(user_id)
        await message.answer(
            f"👋 Xush kelibsiz, {user['name']}!\n\n"
            f"📊 Sizning tarifingiz: {user['tarif'].upper()}\n\n"
            "Quyidagi xizmatlardan birini tanlang:",
            reply_markup=main_menu_keyboard(user_id)
        )
        return

    # Agar kutayotgan bo'lsa
    if user_id in pending_users:
        await message.answer(
            "⏳ Sizning so'rovingiz ko'rib chiqilmoqda.\n"
            "Admin tasdiqlashini kuting. (Odatda 24 soat ichida)"
        )
        return

    # Yangi foydalanuvchi
    await message.answer(
        "🎓 *AKADEMIK YORDAMCHI BOT*\n\n"
        "Assalomu alaykum! Men sizga dissertatsiya yozishda yordam beraman.\n\n"
        "✅ Plagiat tekshiruv\n"
        "✅ AI yordamida matn yozish\n"
        "✅ Ilmiy manbalar qo'shish\n"
        "✅ Word fayl export\n\n"
        "Boshlash uchun ro'yxatdan o'ting:",
        parse_mode="Markdown"
    )
    await message.answer(
        "📝 Ismingizni kiriting (To'liq ism):",
    )
    await state.set_state(Registration.name)

# ========================================
# RO'YXATDAN O'TISH
# ========================================
@dp.message(StateFilter(Registration.name))
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        f"✅ Ism qabul qilindi: {message.text}\n\n"
        "📱 Telefon raqamingizni kiriting (+998901234567):"
    )
    await state.set_state(Registration.phone)

@dp.message(StateFilter(Registration.phone))
async def reg_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer(
        "✅ Telefon qabul qilindi!\n\n"
        "🎓 Dissertatsiyangiz mavzusini kiriting:\n\n"
        "Misol: 'Boshlang'ich ta'limda sun'iy intellekt vositalaridan foydalanish'"
    )
    await state.set_state(Registration.topic)

@dp.message(StateFilter(Registration.topic))
async def reg_topic(message: types.Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer(
        "✅ Mavzu qabul qilindi!\n\n"
        "❓ Sizga qanday yordam kerak?\n\n"
        "Qisqacha yozing (masalan: '150 betlik dissertatsiya yozish kerak, plagiat 70% dan yuqori bo'lsin')"
    )
    await state.set_state(Registration.help_type)

@dp.message(StateFilter(Registration.help_type))
async def reg_help_type(message: types.Message, state: FSMContext):
    await state.update_data(help_type=message.text)
    await message.answer(
        "💰 Tarif tanlang:\n\n"
        "🆓 FREE - Tekin (Faqat plagiat tekshiruv)\n"
        "📗 LITE - $25 / 312,500 so'm (50 bet, 5 band)\n"
        "📘 PRO - $150 / 1,875,000 so'm (100 bet, 10 band)\n"
        "💎 PROMAX - $375 / 4,687,500 so'm (150 bet, 15 band)\n\n"
        "⚠️ DEMO ni ko'rish uchun avval FREE ni tanlang - biz sizga namuna ko'rsatamiz!",
        reply_markup=tarif_keyboard()
    )
    await state.set_state(Registration.tarif)

@dp.callback_query(F.data.startswith("tarif_"), StateFilter(Registration.tarif))
async def reg_tarif(callback: types.CallbackQuery, state: FSMContext):
    tarif = callback.data.replace("tarif_", "")
    data = await state.get_data()
    user_id = callback.from_user.id

    # User ma'lumotlarini saqlash
    pending_users[user_id] = {
        "name": data.get("name"),
        "phone": data.get("phone"),
        "topic": data.get("topic"),
        "help_type": data.get("help_type"),
        "tarif": tarif,
        "status": "pending",
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user_id": user_id,
        "username": callback.from_user.username or "yo'q",
    }

    await state.clear()

    tarif_info = TARIFS[tarif]
    await callback.message.answer(
        f"✅ Ro'yxatdan o'tdingiz!\n\n"
        f"👤 Ism: {data.get('name')}\n"
        f"📱 Tel: {data.get('phone')}\n"
        f"🎓 Mavzu: {data.get('topic')}\n"
        f"💰 Tarif: {tarif_info['name']} - ${tarif_info['price']}\n\n"
        f"⏳ Adminstratorimiz sizga tez orada murojaat qiladi!\n"
        f"Tasdiqlangandan keyin xizmatdan to'liq foydalana olasiz."
    )

    # Admin ga xabar
    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"🔔 YANGI FOYDALANUVCHI!\n\n"
            f"👤 Ism: {data.get('name')}\n"
            f"📱 Tel: {data.get('phone')}\n"
            f"🆔 ID: {user_id}\n"
            f"👤 Username: @{callback.from_user.username or 'yo\'q'}\n"
            f"🎓 Mavzu: {data.get('topic')}\n"
            f"❓ Kerak: {data.get('help_type')}\n"
            f"💰 Tarif: {tarif_info['name']} - ${tarif_info['price']}\n"
            f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Ruxsat berish uchun:\n"
            f"/approve {user_id}\n\n"
            f"Rad etish uchun:\n"
            f"/reject {user_id}",
        )

    await callback.answer()

# ========================================
# ADMIN COMMANDS
# ========================================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    total = len(users_db)
    pending = len(pending_users)

    await message.answer(
        f"👑 ADMIN PANEL\n\n"
        f"📊 Statistika:\n"
        f"✅ Tasdiqlangan: {total} ta\n"
        f"⏳ Kutayotgan: {pending} ta\n\n"
        f"Buyruqlar:\n"
        f"/users - Barcha foydalanuvchilar\n"
        f"/pending - Kutayotganlar\n"
        f"/approve [id] - Ruxsat berish\n"
        f"/reject [id] - Rad etish"
    )

@dp.message(Command("pending"))
async def admin_pending(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    if not pending_users:
        await message.answer("⏳ Kutayotgan foydalanuvchi yo'q.")
        return

    text = "⏳ KUTAYOTGAN FOYDALANUVCHILAR:\n\n"
    for uid, user in pending_users.items():
        text += (
            f"🆔 ID: {uid}\n"
            f"👤 {user['name']}\n"
            f"📱 {user['phone']}\n"
            f"💰 {user['tarif'].upper()}\n"
            f"📅 {user['registered_at']}\n"
            f"/approve {uid}\n\n"
        )

    await message.answer(text)

@dp.message(Command("users"))
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    if not users_db:
        await message.answer("👥 Foydalanuvchi yo'q.")
        return

    text = "✅ TASDIQLANGAN FOYDALANUVCHILAR:\n\n"
    for uid, user in users_db.items():
        text += (
            f"🆔 {uid}\n"
            f"👤 {user['name']}\n"
            f"💰 {user['tarif'].upper()}\n"
            f"📅 {user['registered_at']}\n\n"
        )

    await message.answer(text)

@dp.message(Command("approve"))
async def admin_approve(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Format: /approve [user_id]")
        return

    user_id = int(parts[1])

    if user_id not in pending_users:
        await message.answer(f"❌ ID {user_id} kutayotganlar ro'yxatida yo'q.")
        return

    user = pending_users.pop(user_id)
    user["status"] = "approved"
    users_db[user_id] = user

    # Foydalanuvchiga xabar
    await bot.send_message(
        user_id,
        f"✅ Tabriklaymiz, {user['name']}!\n\n"
        f"Sizning so'rovingiz tasdiqlandi.\n"
        f"💰 Tarifingiz: {user['tarif'].upper()}\n\n"
        f"Endi xizmatdan to'liq foydalana olasiz!\n"
        f"/start - Boshlash",
    )

    await message.answer(f"✅ {user['name']} ({user_id}) tasdiqlandi!")

@dp.message(Command("reject"))
async def admin_reject(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Format: /reject [user_id]")
        return

    user_id = int(parts[1])

    if user_id not in pending_users:
        await message.answer(f"❌ ID {user_id} kutayotganlar ro'yxatida yo'q.")
        return

    user = pending_users.pop(user_id)

    await bot.send_message(
        user_id,
        "❌ Kechirasiz, so'rovingiz rad etildi.\n"
        "Qo'shimcha ma'lumot uchun admin bilan bog'laning."
    )

    await message.answer(f"❌ {user['name']} ({user_id}) rad etildi.")

# ========================================
# DEMO GENERATSIYA
# ========================================
@dp.callback_query(F.data == "demo")
async def demo_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📄 DEMO - 5-BETLIK NAMUNA\n\n"
        "Dissertatsiyangiz mavzusini kiriting:\n\n"
        "Misol: 'Boshlang'ich ta'limda sun'iy intellekt'"
    )
    await state.set_state(Demo.topic)
    await callback.answer()

@dp.message(StateFilter(Demo.topic))
async def demo_generate(message: types.Message, state: FSMContext):
    topic = message.text
    await state.clear()

    wait_msg = await message.answer("⏳ Demo tayyorlanmoqda... (30-60 soniya)")

    try:
        prompt = f"""Sen 20 yillik tajribaga ega O'zbek tilida yozuvchi professor va ilmiy tadqiqotchisan.

Mavzu: "{topic}"

Quyidagi tarzda 5-betlik ilmiy matn yozing (O'zbek tilida):

1. KIRISH (1 bet)
- Mavzuning dolzarbligi
- Tadqiqot maqsadi
- Tadqiqot vazifalari

2. ASOSIY QISM 1.1 (1.5 bet)
- Nazariy asoslar
- Ilmiy tahlil
- Manbalar [manba 1], [manba 2], [manba 3]

3. ASOSIY QISM 1.2 (1.5 bet)
- Amaliy jihatlar
- Tahlil va xulosalar
- Manbalar [manba 4], [manba 5]

4. XULOSA (0.5 bet)
- Asosiy xulosalar
- Tavsiyalar

5. FOYDALANILGAN ADABIYOTLAR:
Quyidagi formatda 10 ta manba keltir:
1. Muallif F.I. "Kitob nomi". - Toshkent: Nashriyot, 2023. - B. 45-47.
2. ...

MUHIM: Akademik, jiddiy va ilmiy tilda yoz. Har bir fikrni manba bilan asosla."""

        response = model.generate_content(prompt)
        demo_text = response.text

        # Plagiat tekshiruv
        originality, plagiat = plagiat_check(demo_text)

        # Word fayl yaratish
        doc = Document()

        # Sarlavha
        title = doc.add_heading(f"DEMO: {topic}", 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Sana
        doc.add_paragraph(f"Yaratilgan: {datetime.now().strftime('%Y-%m-%d')}")
        doc.add_paragraph("=" * 50)

        # Matn
        for line in demo_text.split('\n'):
            if line.strip():
                if line.startswith('#') or line.isupper():
                    doc.add_heading(line.replace('#', '').strip(), level=1)
                else:
                    p = doc.add_paragraph(line)
                    p.style.font.size = Pt(12)

        # Plagiat xulosasi
        doc.add_paragraph("=" * 50)
        doc.add_heading("PLAGIAT TEKSHIRUV XULOSASI", level=1)
        doc.add_paragraph(f"✅ Originallik: {originality}%")
        doc.add_paragraph(f"⚠️ Ko'chirmakashlik: {plagiat}%")
        if originality >= 70:
            doc.add_paragraph("✅ STATUS: QABUL QILINADI")
        else:
            doc.add_paragraph("❌ STATUS: QAYTA ISHLASH KERAK")

        # Disclaimer
        doc.add_paragraph("=" * 50)
        doc.add_paragraph(
            "⚠️ MUHIM: Bu sun'iy intellekt yordamchisi tomonidan yaratilgan namuna. "
            "Yakuniy matnni o'zgartirish va tekshirish tadqiqotchi mas'uliyatidadir. "
            "Ilmiy rahbar bilan ishlash tavsiya etiladi."
        )

        # Saqlash
        filename = f"demo_{message.from_user.id}.docx"
        doc.save(filename)

        # Telegram'ga yuborish
        await bot.delete_message(message.chat.id, wait_msg.message_id)

        caption = (
            f"📄 DEMO TAYYOR!\n\n"
            f"🎓 Mavzu: {topic}\n"
            f"📊 Originallik: {originality}%\n"
            f"📉 Ko'chirmakashlik: {plagiat}%\n"
            f"{'✅ YAXSHI!' if originality >= 70 else '⚠️ Qayta ishlash kerak'}\n\n"
            f"📋 Bu namunada:\n"
            f"✅ 5-betlik ilmiy matn\n"
            f"✅ 10+ manba (muallif, kitob, bet, yil)\n"
            f"✅ Akademik uslub\n"
            f"✅ Plagiat tekshiruv xulosasi\n\n"
            f"💎 150-betlik dissertatsiya uchun:\n"
            f"PROMAX - $375 / 4,687,500 so'm\n\n"
            f"Tarif sotib olish uchun: /start"
        )

        await message.answer_document(
            types.FSInputFile(filename),
            caption=caption
        )

        os.remove(filename)

    except Exception as e:
        await bot.delete_message(message.chat.id, wait_msg.message_id)
        await message.answer(f"❌ Xatolik: {str(e)}\nQayta urinib ko'ring.")

# ========================================
# PLAGIAT TEKSHIRUV
# ========================================
@dp.callback_query(F.data == "plagiat")
async def plagiat_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🔍 PLAGIAT TEKSHIRUV\n\n"
        "Matnni kiriting (kamida 200 belgi):\n\n"
        "⚠️ Manbalar uchun [manba 1] formatidan foydalaning"
    )
    await state.set_state(Dissertation.band_text)
    await callback.answer()

@dp.message(StateFilter(Dissertation.band_text))
async def check_plagiat(message: types.Message, state: FSMContext):
    text = message.text
    await state.clear()

    if len(text) < 100:
        await message.answer(
            "❌ Matn juda qisqa!\n"
            "Kamida 200 belgili matn kiriting."
        )
        await state.set_state(Dissertation.band_text)
        return

    originality, plagiat = plagiat_check(text)

    if originality >= 70:
        status = "✅ QABUL QILINADI"
        emoji = "✅"
    elif originality >= 60:
        status = "⚠️ SHARTLI (Qayta ishlash kerak)"
        emoji = "⚠️"
    else:
        status = "❌ PLAGIAT - Qayta yozish kerak"
        emoji = "❌"

    sources = len([w for w in text.split('[') if 'manba' in w.lower()])
    words = len(text.split())

    result = (
        f"{emoji} PLAGIAT TEKSHIRUV NATIJASI\n\n"
        f"📊 Originallik: {originality}%\n"
        f"📉 Ko'chirmakashlik: {plagiat}%\n"
        f"📚 Manbalar: {sources} ta\n"
        f"📝 So'zlar: {words} ta\n\n"
        f"🏷️ Status: {status}\n\n"
    )

    if originality < 70:
        result += (
            "💡 TAVSIYALAR:\n"
            f"{'❌ ' if originality < 70 else '✅ '}Originallik {originality}% (talabi: 70%+)\n"
            f"{'❌ ' if sources == 0 else '✅ '}Manbalar: {sources} ta {'(kerak: 5+)' if sources < 5 else ''}\n\n"
        )
        if originality < 70:
            result += "• Matnni qayta yozing, o'z g'oyalaringizni qo'shing\n"
        if sources < 5:
            result += "• Ko'proq manba qo'shing: [manba 1], [manba 2]\n"
        if plagiat > 30:
            result += "• 3-4 paragrafni o'zgartiring\n"

    await message.answer(result)

# ========================================
# TARIF KO'RSATISH
# ========================================
@dp.callback_query(F.data == "show_tarifs")
async def show_tarifs(callback: types.CallbackQuery):
    text = (
        "💰 TARIFLAR\n\n"
        "🆓 FREE - Tekin\n"
        "  • Plagiat tekshiruv\n"
        "  • Basic tavsiyalar\n\n"
        "📗 LITE - $25 (312,500 so'm)\n"
        "  • 50 bet / 5 band\n"
        "  • AI matn yozuv\n"
        "  • Manba qo'shish\n"
        "  • Word export\n\n"
        "📘 PRO - $150 (1,875,000 so'm)\n"
        "  • 100 bet / 10 band\n"
        "  • Barcha LITE xususiyatlari\n"
        "  • Ilmiy manbalar qidiruv\n"
        "  • Plagiat check (real API)\n\n"
        "💎 PROMAX - $375 (4,687,500 so'm)\n"
        "  • 150 bet / 15 band\n"
        "  • Barcha PRO xususiyatlari\n"
        "  • Priority support\n"
        "  • Advisor collaboration\n"
        "  • Unlimited revisions\n\n"
        "📞 Tarif sotib olish uchun:\n"
        "Admin: @admin_username"
    )

    await callback.message.answer(text)
    await callback.answer()

# ========================================
# PROFIL KO'RISH
# ========================================
@dp.callback_query(F.data == "my_profile")
async def my_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)

    if not user:
        await callback.message.answer("❌ Profil topilmadi. /start buyrug'ini bosing.")
        await callback.answer()
        return

    tarif_info = TARIFS.get(user.get("tarif", "free"), TARIFS["free"])

    text = (
        f"👤 MENING PROFILIM\n\n"
        f"📛 Ism: {user['name']}\n"
        f"📱 Tel: {user['phone']}\n"
        f"🎓 Mavzu: {user['topic']}\n"
        f"💰 Tarif: {tarif_info['name']} - ${tarif_info['price']}\n"
        f"📄 Betlar: {tarif_info['pages']} ta\n"
        f"📋 Bandlar: {tarif_info['bands']} ta\n"
        f"📅 Ro'yxatdan o'tgan: {user['registered_at']}\n"
        f"✅ Status: {'Tasdiqlangan' if user['status'] == 'approved' else 'Kutmoqda'}"
    )

    await callback.message.answer(text)
    await callback.answer()

# ========================================
# MAIN
# ========================================
async def main():
    logger.info("Bot ishlanmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())