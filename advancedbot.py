import os
import logging
import requests
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from openai import OpenAI
from yt_dlp import YoutubeDL
import instaloader
import sqlite3

# Configurations
TELEGRAM_TOKEN = "7461025500:AAFQWgTntHmkODVeEJv3_egWaF_SS5vLDfU"
OPENAI_API_KEY = "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"
ADMIN_ID = 708030615  # Replace with your Admin ID
COINS_PER_QUESTION = 1
DATABASE_NAME = "advanced_bot.db"

# Initialize
ai_client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Setup
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                (id INTEGER PRIMARY KEY, username TEXT, coins INTEGER DEFAULT 10)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS admins 
                (id INTEGER PRIMARY KEY)''')
conn.commit()

# Add Initial Admin
try:
    cursor.execute("INSERT INTO admins (id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
except sqlite3.IntegrityError:
    pass

# ---------------------- Core Functions ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user.id, user.username))
    conn.commit()
    
    text = f"""🪙 **Welcome {user.first_name}!**
Your Coins: 10
Use /help for commands"""
    await update.message.reply_text(text)

# ---------------------- AI Chat with Coin System ----------------------
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("SELECT coins FROM users WHERE id=?", (user.id,))
    coins = cursor.fetchone()[0]

    if coins < COINS_PER_QUESTION:
        await update.message.reply_text("💰 कोईन्स खत्म! /buy_coins से खरीदें")
        return

    # Deduct Coins
    cursor.execute("UPDATE users SET coins=coins-? WHERE id=?", (COINS_PER_QUESTION, user.id))
    conn.commit()

    # Process AI Request
    try:
        response = ai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": update.message.text}]
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text("🚫 AI Service Error")

# ---------------------- Social Media Downloaders ----------------------
async def youtube_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text("Usage: /youtube <URL>")
        return

    try:
        with YoutubeDL({'format': 'best'}) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info['url']
            # Missing parenthesis fixed here 👇
            await update.message.reply_video(video=InputFile(requests.get(video_url, stream=True).raw)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def insta_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text("Usage: /insta <URL>")
        return

    try:
        L = instaloader.Instaloader()
        shortcode = url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        await update.message.reply_photo(photo=post.url)
    except Exception as e:
        await update.message.reply_text(f"❌ Instagram Error: {str(e)}")

# ---------------------- Admin Management System ----------------------
async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("SELECT id FROM admins")
    admins = cursor.fetchall()
    
    for admin in admins:
        await context.bot.send_message(
            chat_id=admin[0],
            text=f"🚨 Message from @{user.username} ({user.id}):\n\n{update.message.text}"
        )

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Permission Denied!")
        return

    new_admin_id = int(context.args[0])
    try:
        cursor.execute("INSERT INTO admins (id) VALUES (?)", (new_admin_id,))
        conn.commit()
        await update.message.reply_text(f"✅ Added Admin: {new_admin_id}")
    except sqlite3.IntegrityError:
        await update.message.reply_text("⚠️ Already an Admin!")

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🛠️ **Admin Commands**
/addadmin [ID] - Add new admin
/listusers - Show all users
/coins [ID] [AMOUNT] - Add coins
/broadcast [MESSAGE] - Broadcast message"""
    await update.message.reply_text(help_text)

# ---------------------- Main Setup ----------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # User Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("youtube", youtube_dl))
    app.add_handler(CommandHandler("insta", insta_dl))

    # Admin Commands
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("adminhelp", admin_help))

    # Message Handling
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))
    
    # Forward Non-Command Messages to Admin
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admin))

    app.run_polling()