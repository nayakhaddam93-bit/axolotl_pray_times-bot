# -*- coding: utf-8 -*-
import os, io, sqlite3, logging
from datetime import datetime
import requests
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5195140085"))
DB_PATH = "bot_stats.db"

SYRIA_GOVERNORATES = {
    "Damascus": ("دمشق", 33.5138, 36.2765),
    "Rif_Dimashq": ("ريف دمشق", 33.5167, 36.4000),
    "Aleppo": ("حلب", 36.2021, 37.1343),
    "Homs": ("حمص", 34.7324, 36.7137),
    "Hama": ("حماة", 35.1318, 36.7578),
    "Latakia": ("اللاذقية", 35.5317, 35.7918),
    "Tartus": ("طرطوس", 34.8890, 35.8866),
    "Idlib": ("إدلب", 35.9306, 36.6339),
    "Al_Hasakah": ("الحسكة", 36.5024, 40.7477),
    "Deir_ez_Zor": ("دير الزور", 35.3359, 40.1408),
    "Raqqa": ("الرقة", 35.9528, 39.0079),
    "Daraa": ("درعا", 32.6189, 36.1021),
    "As_Suwayda": ("السويداء", 32.7090, 36.5695),
    "Quneitra": ("القنيطرة", 33.1259, 35.8246),
}

ARABIC_DAYS = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, joined_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, chat_title TEXT, chat_type TEXT, joined_at TEXT)")
    conn.commit()
    conn.close()

def register_interaction(update: Update):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = update.effective_user
    if user and not user.is_bot:
        c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at) VALUES (?, ?, ?, ?)", (user.id, user.username or "", user.full_name or "", now_str))
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        c.execute("INSERT OR IGNORE INTO chats (chat_id, chat_title, chat_type, joined_at) VALUES (?, ?, ?, ?)", (chat.id, chat.title or "", chat.type, now_str))
    conn.commit()
    conn.close()

def get_bot_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    u = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM chats")
    ch = c.fetchone()[0]
    conn.close()
    return u, ch

def format_12h(t24):
    clean = t24.split(" ")[0].strip()
    return datetime.strptime(clean, "%H:%M").strftime("%I:%M %p")

def fetch_prayer_times(gov_key):
    gov_ar, lat, lon = SYRIA_GOVERNORATES[gov_key]
    resp = requests.get("https://api.aladhan.com/v1/timings", params={"latitude": lat, "longitude": lon, "method": 4, "timezonestring": "Asia/Damascus"}, timeout=10)
    data = resp.json()["data"]
    raw = data["timings"]
    timings = {k: format_12h(v) for k, v in raw.items()}
    en_day = data["date"]["gregorian"]["weekday"]["en"]
    greg_date = f"{ARABIC_DAYS.get(en_day, '')} {data['date']['gregorian']['date']} م"
    h = data["date"]["hijri"]
    hijri_date = f"{h['day']} {h['month']['ar']} {h['year']} هـ"
    return gov_ar, greg_date, hijri_date, timings

def render_prayer_card_bytes(gov_ar, greg_date, hijri_date, timings):
    img = Image.new('RGB', (800, 1200), color='#D2F3EC')
    draw = ImageDraw.Draw(img)
    try:
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf", 36)
        f_text = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf", 26)
    except:
        f_title = f_text = ImageFont.load_default()

    draw.text((400, 100), "مواقيت الصلاة في سوريا", fill="#12383B", font=f_title, anchor="mm", direction="rtl")
    draw.text((400, 180), f"محافظة {gov_ar}", fill="#0A3622", font=f_title, anchor="mm", direction="rtl")
    draw.text((400, 240), f"{greg_date}  |  {hijri_date}", fill="#12383B", font=f_text, anchor="mm", direction="rtl")

    p_list = [("الفجر", timings["Fajr"]), ("الشروق", timings["Sunrise"]), ("الظهر", timings["Dhuhr"]), ("العصر", timings["Asr"]), ("المغرب", timings["Maghrib"]), ("العشاء", timings["Isha"])]
    y = 320
    for name, time in p_list:
        draw.rectangle([100, y, 700, y+80], fill="#1B5E55", outline="#12383B", width=3)
        draw.text((150, y+40), time, fill="#D2F3EC", font=f_text, anchor="lm")
        draw.text((650, y+40), f"صلاة {name}" if name != "الشروق" else name, fill="#FFFFFF", font=f_text, anchor="rm", direction="rtl")
        y += 100

    draw.text((400, 1050), "نسأل الله التوفيق", fill="#0A3622", font=f_text, anchor="mm", direction="rtl")
    draw.text((700, 1140), "Naya khaddam", fill="#12383B", font=f_text, anchor="rm")

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

def build_keyboard():
    buttons = []
    items = list(SYRIA_GOVERNORATES.items())
    for i in range(0, len(items), 2):
        row = []
        for key, (name_ar, _, _) in items[i:i+2]:
            row.append(InlineKeyboardButton(f"📍 {name_ar}", callback_data=f"gov:{key}"))
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_interaction(update)
    await update.message.reply_text("🌿 أهلاً بك في بوت مواقيت الصلاة في سوريا\nاختر المحافظة:", reply_markup=build_keyboard())

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text and context.bot.username in update.message.text:
        register_interaction(update)
        await update.message.reply_text("🕌 مواقيت الصلاة في سوريا - اختر المحافظة:", reply_markup=build_keyboard())

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    register_interaction(update)
    data = query.data
    if data.startswith("gov:"):
        gov_key = data.split(":")[1]
        gov_ar, greg, hijri, timings = fetch_prayer_times(gov_key)
        card = render_prayer_card_bytes(gov_ar, greg, hijri, timings)
        await query.message.reply_photo(photo=card, caption=f"🕌 مواقيت الصلاة في {gov_ar}\n🌿 نسأل الله التوفيق | Naya khaddam", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 محافظات أخرى", callback_data="back")]]))
    elif data == "back":
        await query.message.reply_text("اختر المحافظة:", reply_markup=build_keyboard())

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🔒 للأدمن فقط.")
        return
    u, ch = get_bot_stats()
    await update.message.reply_text(f"📊 إحصائيات البوت:\n👤 المستخدمين: {u}\n👥 المجموعات: {ch}")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "prayer"], start))
    app.add_handler(CommandHandler(["stats"], stats))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mention_handler))
    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
