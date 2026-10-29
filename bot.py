# -*- coding: utf-8 -*-
import os, io, math, asyncio, sqlite3
from datetime import datetime
import requests
import matplotlib
from PIL import Image, ImageDraw, ImageFont, features
import arabic_reshaper
from bidi.algorithm import get_display
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "8903468673:AAHGDMlLu2Ma-u2K4Of2bCKU34fG0RvHKv8"
ADMIN_ID = int(os.getenv("ADMIN_ID", "5195140085"))
DB_PATH = "bot_stats.db"
LOGO_PATH = "logo.jpg"

CAIRO_FONTS = ["Cairo-Bold.ttf", "Cairo-Regular.ttf"]
_MPL = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
DEJAVU_FONTS = [
    os.path.join(_MPL, "DejaVuSans-Bold.ttf"),
    os.path.join(_MPL, "DejaVuSans.ttf"),
]

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

ARABIC_DAYS = {
    "Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين",
    "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"
}

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
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)", (user.id, user.username or "", user.full_name or "", now_str))
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        c.execute("INSERT OR IGNORE INTO chats VALUES (?, ?, ?, ?)", (chat.id, chat.title or "", chat.type, now_str))
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
    return datetime.strptime(clean, "%H:%M").strftime("%I:%M %p").replace("AM", "ص").replace("PM", "م")

def fetch_prayer_times(gov_key):
    gov_ar, lat, lon = SYRIA_GOVERNORATES[gov_key]
    resp = requests.get(
        "https://api.aladhan.com/v1/timings",
        params={
            "latitude": lat,
            "longitude": lon,
            "method": 3,
            "shafaq": "general",
            "tune": "0,0,-2,2,0,3,0,2,0",
            "timezonestring": "Asia/Damascus"
        },
        timeout=10
    )
    data = resp.json()["data"]
    timings = {k: format_12h(v) for k, v in data["timings"].items()}
    en_day = data["date"]["gregorian"]["weekday"]["en"]
    greg_date = f"{ARABIC_DAYS.get(en_day, '')} {data['date']['gregorian']['date']} م"
    h = data["date"]["hijri"]
    hijri_date = f"{h['day']} {h['month']['ar']} {h['year']} هـ"
    return gov_ar, greg_date, hijri_date, timings

S = 2
W, H = 900, 1300
DARK = "#1E3A4C"
MINT = "#CDEFE3"
MINT_DARK = "#8FC4B3"
CORAL = "#E0707A"
DOODLE = (110, 175, 150, 70)

USE_RAQM = features.check("raqm")

def s(v):
    return int(v * S)

class RTLDraw(ImageDraw.ImageDraw):
    def text(self, xy, text, *args, **kwargs):
        if USE_RAQM:
            kwargs.setdefault("direction", "rtl")
            kwargs.setdefault("language", "ar")
        return super().text(xy, text, *args, **kwargs)

def ar(text):
    if USE_RAQM:
        return text
    shaped = arabic_reshaper.reshape(text)
    shaped = shaped.replace("\uFDF2", "\uFE8D\uFEDF\uFEE0\uFEEA")
    return get_display(shaped)

def get_font(size):
    if USE_RAQM:
        paths = CAIRO_FONTS + DEJAVU_FONTS
        engine = ImageFont.Layout.RAQM
    else:
        paths = DEJAVU_FONTS + CAIRO_FONTS
        engine = ImageFont.Layout.BASIC
    for path in paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, s(size), layout_engine=engine)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_doodles(size):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lw = s(3)
    def dna(x0, y0, length, amp=28):
        prev1 = prev2 = None
        for t in range(0, length, 4):
            y = y0 + t
            x1 = x0 + amp * math.sin(t / 38)
            x2 = x0 - amp * math.sin(t / 38)
            if prev1:
                d.line([(s(prev1[0]), s(prev1[1])), (s(x1), s(y))], fill=DOODLE, width=lw)
                d.line([(s(prev2[0]), s(prev2[1])), (s(x2), s(y))], fill=DOODLE, width=lw)
            if t % 20 == 0:
                d.line([(s(x1), s(y)), (s(x2), s(y))], fill=DOODLE, width=s(2))
            prev1, prev2 = (x1, y), (x2, y)
    dna(42, 280, 800)
    dna(858, 330, 800)
    def ecg(y):
        pts = []
        for x0 in range(70, 830, 150):
            pts += [(x0, y), (x0 + 40, y), (x0 + 55, y - 28), (x0 + 70, y + 38), (x0 + 85, y - 55), (x0 + 100, y), (x0 + 150, y)]
        d.line([(s(x), s(yy)) for x, yy in pts], fill=DOODLE, width=lw, joint="curve")
    ecg(1185)
    def plus(cx, cy, r=14):
        d.rounded_rectangle([s(cx - r), s(cy - r / 3), s(cx + r), s(cy + r / 3)], radius=s(3), fill=DOODLE)
        d.rounded_rectangle([s(cx - r / 3), s(cy - r), s(cx + r / 3), s(cy + r)], radius=s(3), fill=DOODLE)
    for p in [(120, 90), (780, 70), (90, 230), (820, 250), (150, 1110), (760, 1120), (450, 1265)]:
        plus(*p)
    return layer

def circular_logo(diameter):
    logo = Image.open(LOGO_PATH).convert("RGB")
    w, h = logo.size
    m = int(w * 0.065)
    logo = logo.crop((m, m, w - m, h - m)).resize((diameter, diameter), Image.LANCZOS)
    mask = Image.new("L", (diameter * 4, diameter * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter * 4 - 1, diameter * 4 - 1), fill=255)
    return logo, mask.resize((diameter, diameter), Image.LANCZOS)

def render_prayer_card_bytes(gov_ar, greg_date, hijri_date, timings):
    img = Image.new("RGBA", (s(W), s(H)), MINT)
    img = Image.alpha_composite(img, draw_doodles(img.size)).convert("RGB")

    if os.path.exists(LOGO_PATH):
        D = s(210)
        logo, mask = circular_logo(D)
        img.paste(logo, ((s(W) - D) // 2, s(30)), mask)

    draw = RTLDraw(img)
    f_title, f_sub, f_text, f_small = get_font(60), get_font(36), get_font(38), get_font(28)

    draw.text((s(450), s(305)), ar("مواقيت الصلاة"), fill=DARK, anchor="mm", font=f_title)
    draw.text((s(450), s(375)), ar(f"محافظة {gov_ar}"), fill=CORAL, anchor="mm", font=f_sub)
    draw.text((s(450), s(425)), ar(f"{greg_date}   |   {hijri_date}"), fill=DARK, anchor="mm", font=f_small)

    p_list = [("الفجر", "Fajr"), ("الشروق", "Sunrise"), ("الظهر", "Dhuhr"),
              ("العصر", "Asr"), ("المغرب", "Maghrib"), ("العشاء", "Isha")]
    y = 470
    for name, key in p_list:
        draw.rounded_rectangle([s(80), s(y), s(820), s(y + 90)], radius=s(22),
                               fill="#E9FAF4", outline=DARK, width=s(4))
        cy = y + 45
        draw.ellipse([s(105), s(cy - 16), s(137), s(cy + 16)], fill=MINT_DARK, outline=DARK, width=s(3))
        draw.text((s(170), s(cy)), ar(timings[key]), fill=DARK, anchor="lm", font=f_text)
        draw.text((s(790), s(cy)), ar(f"صلاة {name}"), fill=DARK, anchor="rm", font=f_text)
        y += 105

    draw.text((s(450), s(1120)), ar("نسأل الله التوفيق والقبول"), fill=DARK, anchor="mm", font=f_sub)
    draw.text((s(450), s(1240)), ar("To be a Doctor…  |  Naya Khaddam"), fill=CORAL, anchor="mm", font=f_small)

    bio = io.BytesIO()
    img.save(bio, format="PNG", optimize=True)
    bio.seek(0)
    return bio

def build_keyboard():
    buttons = []
    items = list(SYRIA_GOVERNORATES.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(f"📍 {name_ar}", callback_data=f"gov:{key}") for key, (name_ar, _, _) in items[i:i + 2]]
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_interaction(update)
    await update.message.reply_text("🌸 أهلاً بك في بوت مواقيت الصلاة (إصدار Axolotl 🐾)\nاختر المحافظة:", reply_markup=build_keyboard())

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
        user = query.from_user
        who = f"@{user.username}" if user.username else user.full_name
        gov_key = data.split(":")[1]
        gov_ar, greg, hijri, timings = await asyncio.to_thread(fetch_prayer_times, gov_key)
        card = await asyncio.to_thread(render_prayer_card_bytes, gov_ar, greg, hijri, timings)
        await query.message.reply_photo(
            photo=card,
            caption=f"🕌 مواقيت الصلاة في {gov_ar}\n👤 بطلب من: {who}\n🐾 Axolotl Prayer Bot | Naya khaddam",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 محافظات أخرى", callback_data="back")]]))
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
