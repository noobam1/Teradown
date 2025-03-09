import os
import json
import re
import requests
import time
import logging
import tempfile
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote
from telegram import Update, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
from bs4 import BeautifulSoup
from functools import wraps

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]  # अपने Admin ID डालें
USER_DATA_FILE = "user_data.json"
MAX_FREE_DOWNLOADS = 5
TERABOX_DOMAINS = [...]  # पिछली डोमेन लिस्ट यहां रखें

# ================== LOGGING & UTILITIES ==================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== ENHANCED USER DATA STRUCTURE ==================
"""
{
    "users": {
        "user_id": {
            "coins": 0,
            "download_history": [],
            "pending_replies": []
        }
    },
    "message_map": {
        "admin_chat_id:message_id": {"original_user": 123, "original_msg_id": 456}
    }
}
"""

# ================== ADMIN FEATURES ==================
async def forward_to_admins(context: CallbackContext, user_id: int, message: Message):
    """यूजर के मैसेज को सभी एडमिन्स को फॉरवर्ड करें"""
    admins = ADMIN_IDS
    forwarded_messages = []
    
    for admin_id in admins:
        try:
            fwd = await message.forward(admin_id)
            forwarded_messages.append({
                "chat_id": fwd.chat_id,
                "message_id": fwd.message_id
            })
        except Exception as e:
            logger.error(f"Admin forward failed: {str(e)}")

    # मैसेज मैपिंग सेव करें
    data = load_user_data()
    for fwd in forwarded_messages:
        map_key = f"{fwd['chat_id']}:{fwd['message_id']}"
        data["message_map"][map_key] = {
            "original_user": user_id,
            "original_msg_id": message.message_id
        }
    save_user_data(data)

async def handle_admin_reply(update: Update, context: CallbackContext):
    """एडमिन के रिप्लाई को यूजर तक पहुंचाएं"""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    replied_msg = update.message.reply_to_message
    if not replied_msg:
        return

    data = load_user_data()
    map_key = f"{replied_msg.chat_id}:{replied_msg.message_id}"
    
    if map_key in data["message_map"]:
        target_user = data["message_map"][map_key]["original_user"]
        try:
            await context.bot.send_message(
                chat_id=target_user,
                text=f"📩 Admin Response:\n\n{update.message.text}"
            )
            # हिस्ट्री अपडेट करें
            data["users"][str(target_user)].setdefault("pending_replies", []).append({
                "admin_id": update.message.from_user.id,
                "message": update.message.text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_user_data(data)
        except Exception as e:
            logger.error(f"Admin reply failed: {str(e)}")

async def broadcast(update: Update, context: CallbackContext):
    """सभी यूजर्स को ब्रॉडकास्ट मैसेज भेजें (Admin Only)"""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    data = load_user_data()
    users = data["users"].keys()
    success = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=f"📢 Broadcast Message:\n\n{' '.join(context.args)}"
            )
            success += 1
        except Exception as e:
            logger.error(f"Broadcast failed for {user_id}: {str(e)}")
    
    await update.message.reply_text(f"Broadcast complete: {success}/{len(users)} users reached")

# ================== MODIFIED MESSAGE HANDLER ==================
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    
    # एडमिन चेक
    if user_id in ADMIN_IDS:
        return  # एडमिन के मैसेजेस को सीधे प्रोसेस न करें
    
    # मैसेज को एडमिन्स को फॉरवर्ड करें
    await forward_to_admins(context, user_id, update.message)
    
    # यूजर को कन्फर्मेशन भेजें
    await update.message.reply_text(
        "✅ Your message has been forwarded to admins!\n"
        "You'll receive reply here shortly."
    )

# ================== UPDATED START COMMAND ==================
async def start(update: Update, context: CallbackContext):
    text = (
        "👋 Welcome to Terabox Download Bot!\n\n"
        "• Send any Terabox link to download\n"
        "• Need help? Just type your message - it goes directly to admins\n"
        f"• Free daily downloads: {MAX_FREE_DOWNLOADS}"
    )
    if update.message.from_user.id in ADMIN_IDS:
        text += "\n\n👮 Admin Commands:\n/reply <user_id> <message>\n/broadcast <message>"
    
    await update.message.reply_text(text)

# ================== MAIN APPLICATION ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    handlers = [
        CommandHandler("start", start),
        CommandHandler("broadcast", broadcast),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY & filters.Chat(ADMIN_IDS), handle_admin_reply)
    ]
    
    application.add_handlers(handlers)
    application.run_polling()

if __name__ == "__main__":
    main()