# -*- coding: utf-8 -*-
print("BOOT: file started", flush=True)
import os, io, math, asyncio, sqlite3
from datetime import datetime
import requests
import matplotlib
from PIL import Image, ImageDraw, ImageFont, features
import arabic_reshaper
from bidi.algorithm import get_display
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
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