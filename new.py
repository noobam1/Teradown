import os
import json
import logging
import re
import asyncio
from datetime import datetime
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
import aiohttp
from io import BytesIO

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]
USER_DATA_FILE = "user_data.json"
MAX_FREE_DOWNLOADS = 5
TERABOX_API_URL = "https://terabox-dl.vercel.app/api/download"

# Terabox domains
TERABOX_DOMAINS = ["terabox.com", "teraboxlink.com"]
TERABOX_REGEX = re.compile(rf'https?://(?:www\.)?({"|".join(TERABOX_DOMAINS)})/[^\s]+', re.I)

# ================== LOGGING ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== UTILITIES ==================
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {"users": {}, "message_map": {}}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# ================== TERABOX FILE DOWNLOADER ==================
async def download_terabox_file(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    file_data = await response.read()
                    return BytesIO(file_data)
                return None
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return None

# ================== COMMAND HANDLERS ==================
async def start(update: Update, context: CallbackContext):
    # ... (same as before)

async def status(update: Update, context: CallbackContext):
    # ... (same as before)

# ================== MAIN MESSAGE HANDLER ==================
async def handle_message(update: Update, context: CallbackContext):
    user = update.effective_user
    msg_text = update.message.text
    data = load_user_data()
    user_key = str(user.id)

    # User initialization
    if user_key not in data["users"]:
        data["users"][user_key] = {
            "coins": 0,
            "downloads": 0,
            "pending_replies": []
        }

    user_data = data["users"][user_key]
    remaining = MAX_FREE_DOWNLOADS - user_data["downloads"]

    # Check download limits
    if remaining <= 0 and user_data["coins"] <= 0:
        await update.message.reply_text("❌ Download limit exceeded! Use /status")
        return

    # Process Terabox link
    if TERABOX_REGEX.match(msg_text):
        await update.message.reply_text("⏳ Processing your request...")
        
        try:
            # Step 1: Get direct link from API
            params = {'url': msg_text}
            async with aiohttp.ClientSession() as session:
                async with session.get(TERABOX_API_URL, params=params) as api_res:
                    if api_res.status != 200:
                        raise Exception("API request failed")
                    api_data = await api_res.json()
                    
            direct_url = api_data.get('direct_link')
            if not direct_url:
                raise Exception("No direct link found")
            
            # Step 2: Download file to memory
            file_buffer = await download_terabox_file(direct_url)
            if not file_buffer:
                raise Exception("File download failed")
            
            # Step 3: Send file directly to user
            file_buffer.seek(0)
            await update.message.reply_video(
                video=InputFile(file_buffer, filename=api_data.get('title', 'video.mp4')),
                caption=f"📹 {api_data.get('title', 'Your Video')}\n"
                        f"📦 Size: {api_data.get('size', 'N/A')}"
            )
            
            # Update user data
            if remaining > 0:
                user_data["downloads"] += 1
            else:
                user_data["coins"] -= 1
            save_user_data(data)

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            await update.message.reply_text("⚠️ Video delivery failed. Please try later.")

    else:
        await update.message.reply_text("❌ Invalid Terabox link")

# ================== ADMIN FEATURES ==================
# ... (same as previous code)

# ================== MAIN APP ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    handlers = [
        CommandHandler("start", start),
        CommandHandler("status", status),
        CommandHandler("broadcast", broadcast),
        CommandHandler("add_coins", add_coins),
        CommandHandler("check_coins", check_coins),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY & filters.Chat(ADMIN_IDS), handle_admin_reply)
    ]
    
    application.add_handlers(handlers)
    application.run_polling()

if __name__ == "__main__":
    main()