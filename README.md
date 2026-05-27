# 🎓 Dissertatsiya Ilmiy Yordamchi Bot

O'zbekiston standartlariga muvofiq dissertatsiya bandlarini tahlil qiluvchi, AI-powered Telegram boti.

## ✨ Xususiyatlari

- 📝 Band matnini plagiat tekshiruvi (70% originallik talab)
- 🤖 Gemini AI bilan tavsiyalar
- 📄 Word fayl yaratish va yuklash
- 🔍 Manbalar analizi ([manba N] formatida)
- ⚡ Tez va hech qanday muammosiz

## 🚀 Setup

### 1. Telegram Bot Token olish

```bash
# Telegram @BotFather ga yo'naling
# /newbot buyrug'ini kiriting
# Token olish (masalan: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)
```

### 2. Gemini API Key olish

```bash
# https://ai.google.dev ga o'ting
# "Get API Key" bosing
# Tekin API key oling
```

### 3. Local test

```bash
# Python 3.9+ kerak

# Requirements o'rnatish
pip install -r requirements.txt

# .env faylini yaratish
cp .env.example .env

# .env'da API kalitlarini qo'shing:
# TELEGRAM_TOKEN=xxx
# GEMINI_API_KEY=yyy

# Bot ishlanishi
python bot.py
```

## 📤 Render'da Deploy qilish

### Step 1: GitHub'ga push qiling

```bash
git init
git add .
git commit -m "Bot v1.0"
git remote add origin https://github.com/YOUR_USERNAME/dissertation-bot.git
git push -u origin main
```

### Step 2: Render'da create qiling

1. https://render.com ga o'ting
2. New → Web Service
3. GitHub repositoryni select qiling
4. Settings:
   - **Name**: dissertation-bot
   - **Runtime**: Python 3.11
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`

### Step 3: Environment Variables qo'shing

Render Dashboard → Environment:
```
TELEGRAM_TOKEN=your_token
GEMINI_API_KEY=your_gemini_api_key
```

### Step 4: Deploy

- "Create Web Service" bosing
- Deploy logs ko'ring
- Tayyoq! ✅

## 💬 Telegram Bot Buyruqlari

```
/start       - Bot bilan salom
/new_band    - Yangi band yaratish
/help        - Yordam
/cancel      - Bekor qilish
```

## 📋 Anti-Plagiat Standartlari

| Mezon | Talabi | Status |
|-------|--------|--------|
| Originallik | 70%+ | ✅ OK |
| Ko'chirmakashlik | 30% gacha | ✅ OK |
| Manbalar | [manba N] | ✅ OK |
| Jumla uzunligi | 15-20 so'z | ⚠️ Normal |

## 🛠 Texnik Stack

- **Python 3.11**
- **aiogram 3.0** - Telegram API
- **google-generativeai** - Gemini AI
- **python-docx** - Word fayl yaratish
- **Render** - Hosting

## 📊 Fayllar

```
.
├── bot.py                 # Asosiy bot logikasi
├── plagiat_checker.py     # Plagiat tekshiruv moduli
├── word_generator.py      # Word fayl generator
├── requirements.txt       # Python dependencies
├── .env.example          # Config template
├── Procfile              # Render config
├── runtime.txt           # Python versiyasi
└── README.md             # Bu fayl
```

## 🔐 Xavfsizlik

- API kalitlarini GitHub'da joylashtirmang
- `.env` faylini `.gitignore` qo'shing
- Sensitive ma'lumotlar Render Secrets'da saqlang

## 🐛 Muammolar

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "API Key invalid"
- Gemini API key'ni tekshiring
- Tekin tier xuddan ham valid ekanligini tasdiqlang

### Bot javob bermaydi
- Telegram token'ni tekshiring
- Render logs'ni ko'ring: `render.com/logs`

## 📞 Support

Issues yoki savollar uchun GitHub Issues ochib qo'ying.

## 📄 Litsenziya

MIT License - Free to use

---

**Made with ❤️ for dissertation researchers in Uzbekistan**
