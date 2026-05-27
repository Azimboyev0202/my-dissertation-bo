import os
import logging
from typing import Optional
from datetime import datetime
import io

# ← BUNI QO'SHING:
from dotenv import load_dotenv
load_dotenv()  # LOAD QILISH
# ↑ QOSHILDI


from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, File
import google.generativeai as genai
from dotenv import load_dotenv

from plagiat_checker import quick_plagiat_check
from word_generator import create_band_document

# Config
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)

# Bot va Dispatcher
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# FSM States
class DissertationState(StatesGroup):
    waiting_band_number = State()
    waiting_band_title = State()
    waiting_band_content = State()
    waiting_confirmation = State()

# User sessions
user_sessions = {}

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Bot start"""
    await message.answer(
        "🎓 Dissertatsiya Ilmiy Yordamchi Botiga xush kelibsiz!\n\n"
        "Men siz bilan dissertatsiya bandlarini ishlab chiqishda yordam beradigan AI yordamchisiman.\n\n"
        "Foydalan buyruqlari:\n"
        "/new_band - Yangi band yaratish\n"
        "/help - Yordam\n"
        "/cancel - Bekor qilish",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Yordam"""
    await message.answer(
        "📖 QANDAY ISHLAYDI:\n\n"
        "1️⃣ /new_band bosing\n"
        "2️⃣ Band raqamini kiriting (masalan: 1.1)\n"
        "3️⃣ Band nomini kiriting\n"
        "4️⃣ Band matnini kiriting\n"
        "5️⃣ Bot plagiat tekshiruv o'tkazadi\n"
        "6️⃣ AI tavsiyalar beradi\n"
        "7️⃣ Word fayl yuklansadi\n\n"
        "💡 ANTI-PLAGIAT STANDARTLARI:\n"
        "• Originallik: Kamida 70%\n"
        "• Ko'chirmakashlik: 30% gacha\n"
        "• Manbalar: [manba 1], [manba 2] tarzida\n\n"
        "🔗 Manbalar: Google Scholar, ResearchGate, DOAJ"
    )

@dp.message(Command("new_band"))
async def cmd_new_band(message: Message, state: FSMContext):
    """Yangi band yaratish"""
    user_id = message.from_user.id
    user_sessions[user_id] = {}
    
    await state.set_state(DissertationState.waiting_band_number)
    await message.answer(
        "📝 Band raqamini kiriting\n"
        "(masalan: 1.1, 1.2, 2.1, va h.k.)",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(DissertationState.waiting_band_number)
async def process_band_number(message: Message, state: FSMContext):
    """Band raqamini qabul qilish"""
    band_number = message.text.strip()
    
    if not band_number:
        await message.answer("❌ Band raqamini to'g'ri kiriting!")
        return
    
    user_id = message.from_user.id
    user_sessions[user_id]['band_number'] = band_number
    
    await state.set_state(DissertationState.waiting_band_title)
    await message.answer(
        f"✅ Band: {band_number}\n\n"
        "📚 Endi band nomini kiriting\n"
        "(masalan: 'Pedagogik vositalari')"
    )

@dp.message(DissertationState.waiting_band_title)
async def process_band_title(message: Message, state: FSMContext):
    """Band nomini qabul qilish"""
    title = message.text.strip()
    
    user_id = message.from_user.id
    user_sessions[user_id]['band_title'] = title
    
    await state.set_state(DissertationState.waiting_band_content)
    await message.answer(
        f"✅ Nomi: {title}\n\n"
        "📄 Endi band matnini kiriting\n"
        "(Kamida 200 belgi, manbalarni [manba 1] tarzida qo'shing)"
    )

@dp.message(DissertationState.waiting_band_content)
async def process_band_content(message: Message, state: FSMContext):
    """Band matnini qabul qilish va tahlil qilish"""
    content = message.text.strip()
    
    if len(content) < 100:
        await message.answer(
            "❌ Matn juda qisqa! Kamita 100 belgili matn kerak.\n"
            "Yana urinib ko'ring."
        )
        return
    
    user_id = message.from_user.id
    user_sessions[user_id]['band_content'] = content
    
    # Status ko'rsatish
    await message.answer("⏳ Plagiat tekshiruvi jarayonida...", reply_markup=types.ReplyKeyboardRemove())
    
    # Plagiat tekshiruvi
    plagiat_result = quick_plagiat_check(content)
    user_sessions[user_id]['plagiat_result'] = plagiat_result
    
    # Natija ko'rsatish
    status_emoji = "✅" if plagiat_result['statusBadge'] == "OK" else \
                   "⚠️" if plagiat_result['statusBadge'] == "SHARTLI" else "❌"
    
    result_text = (
        f"{status_emoji} PLAGIAT TEKSHIRUV NATIJALARI\n\n"
        f"Originallik: {plagiat_result['originallikFoizi']}%\n"
        f"Ko'chirmakashlik: {plagiat_result['kochirilganFoizi']}%\n"
        f"Status: {plagiat_result['statusBadge']}\n"
        f"Manbalar: {plagiat_result['sourcesFound']} ta topildi\n\n"
        f"💡 TAVSIYALAR:\n"
    )
    
    for i, rec in enumerate(plagiat_result['recommendations'], 1):
        result_text += f"{i}. {rec}\n"
    
    await message.answer(result_text)
    
    # Gemini tavsiyalari (optional - agar API ishsa)
    try:
        gemini_rec = await get_gemini_recommendations(content, plagiat_result)
        if gemini_rec:
            await message.answer(
                f"🤖 GEMINI AI TAVSIYALARI:\n\n{gemini_rec}",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[[
                        types.KeyboardButton(text="✅ Word yuklash"),
                        types.KeyboardButton(text="❌ Bekor qilish")
                    ]],
                    resize_keyboard=True
                )
            )
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        await message.answer(
            "Word faylni yuklashni istaysizmi?",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[[
                    types.KeyboardButton(text="✅ Word yuklash"),
                    types.KeyboardButton(text="❌ Bekor qilish")
                ]],
                resize_keyboard=True
            )
        )
    
    await state.set_state(DissertationState.waiting_confirmation)

@dp.message(DissertationState.waiting_confirmation, F.text.contains("Word"))
async def generate_word_file(message: Message, state: FSMContext):
    """Word fayl yaratish va yuklash"""
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if not session:
        await message.answer("❌ Sessiya tugagan. /new_band bosing.")
        await state.clear()
        return
    
    await message.answer("⏳ Word fayl tayyorlanmoqda...", reply_markup=types.ReplyKeyboardRemove())
    
    try:
        # Word document yaratish
        doc = create_band_document(
            band_number=session.get('band_number', '1.1'),
            title=session.get('band_title', 'Band'),
            content=session.get('band_content', ''),
            plagiat_analysis=session.get('plagiat_result', {}),
            author="Dissertant"
        )
        
        # File buffer
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        # Yuklash
        filename = f"Band_{session.get('band_number', '1.1')}.docx"
        await message.answer_document(
            document=types.BufferedInputFile(
                file=buffer.getvalue(),
                filename=filename
            ),
            caption=f"✅ Word fayl: {filename}"
        )
        
        await message.answer(
            "✅ Fayl tayyor!\n\n"
            "Keyingi band uchun /new_band bosing",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
    except Exception as e:
        logger.error(f"Word generation error: {e}")
        await message.answer(f"❌ Xato: {str(e)}")
    
    await state.clear()

@dp.message(DissertationState.waiting_confirmation, F.text.contains("Bekor"))
async def cancel_process(message: Message, state: FSMContext):
    """Bekor qilish"""
    user_id = message.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    await message.answer(
        "❌ Bekor qilindi.\n\n"
        "Yangi band uchun /new_band bosing",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel command"""
    await state.clear()
    await message.answer(
        "❌ Bekor qilindi.",
        reply_markup=types.ReplyKeyboardRemove()
    )

async def get_gemini_recommendations(content: str, plagiat_result: dict) -> Optional[str]:
    """Gemini'dan tavsiyalar olish"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""Bu dissertatsiya bandini tahlil qiling va konkret tavsiyalar bering:

MATN:
{content}

PLAGIAT ANALIZI:
- Originallik: {plagiat_result['originallikFoizi']}%
- Manbalar: {plagiat_result['sourcesFound']} ta

Quyidagilarni bering:
1. Qaysi qismlarda o'zgartirish kerak
2. Qo'shimcha qaysi xulosalar kerak
3. Qaysi paragrafda manba qo'shish kerak

Juda qisqa va konkret tavsiyalar bering (5-7 jumlada)."""

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return None

async def main():
    """Bot ishini boshlash"""
    logger.info("Bot ishlanmoqda...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
