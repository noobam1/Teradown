import os
import json
import logging
from telegram import Update, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
from datetime import datetime
import time

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]  # अपने Admin ID डालें
USER_DATA_FILE = "user_data.json"
MAX_FREE_DOWNLOADS = 5
# Adding 30+ Terabox domains
TERABOX_DOMAINS = [
    "terabox.com", "terabox.cc", "terabox.net", "terabox.co", "terabox.org",
    "terabox.in", "terabox.us", "terabox.biz", "terabox.club", "terabox.info",
    "terabox.co.uk", "terabox.cn", "terabox.asia", "terabox.store", "terabox.tv",
    "terabox.fr", "terabox.ru", "terabox.de", "terabox.it", "terabox.eu",
    "terabox.jp", "terabox.kr", "terabox.my", "terabox.id", "terabox.sg",
    "terabox.hk", "terabox.mex", "terabox.com.br", "terabox.ar", "terabox.co.jp",
    "terabox.co.kr", "terabox.co.in", "terabox.co.id", "terabox.us.com"
]

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
    """Forward user message to admins"""
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

    # Save message map for reply handling
    data = load_user_data()
    for fwd in forwarded_messages:
        map_key = f"{fwd['chat_id']}:{fwd['message_id']}"
        data["message_map"][map_key] = {
            "original_user": user_id,
            "original_msg_id": message.message_id
        }
    save_user_data(data)


async def handle_admin_reply(update: Update, context: CallbackContext):
    """Handle replies from admins to users"""
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
            # Update history with admin reply
            data["users"][str(target_user)].setdefault("pending_replies", []).append({
                "admin_id": update.message.from_user.id,
                "message": update.message.text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_user_data(data)
        except Exception as e:
            logger.error(f"Admin reply failed: {str(e)}")


async def broadcast(update: Update, context: CallbackContext):
    """Broadcast a message to all users"""
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


# ================== ADMIN COINS SYSTEM ==================

async def add_coins(update: Update, context: CallbackContext):
    """Admin command to add coins to a user"""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    # Ensure the correct format
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /add_coins <user_id> <coins>")
        return

    user_id = context.args[0]
    coins = int(context.args[1])

    # Load user data
    data = load_user_data()

    # Add coins to the user
    if str(user_id) in data["users"]:
        data["users"][str(user_id)]["coins"] += coins
        save_user_data(data)
        await update.message.reply_text(f"✅ {coins} coins added to user {user_id}. Total: {data['users'][str(user_id)]['coins']} coins.")
    else:
        await update.message.reply_text(f"❌ User {user_id} not found.")

async def check_coins(update: Update, context: CallbackContext):
    """Admin command to check a user's coins"""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /check_coins <user_id>")
        return

    user_id = context.args[0]

    data = load_user_data()
    if str(user_id) in data["users"]:
        coins = data["users"][str(user_id)]["coins"]
        await update.message.reply_text(f"💰 User {user_id} has {coins} coins.")
    else:
        await update.message.reply_text(f"❌ User {user_id} not found.")


# ================== MODIFIED MESSAGE HANDLER ==================

async def handle_message(update: Update, context: CallbackContext):
    """Handle incoming messages from users"""
    user_id = update.message.from_user.id
    user_message = update.message.text

    # Logging the received message
    logger.info(f"Received message: {user_message} from user {user_id}")

    # Check if the message contains a Terabox link
    if any(domain in user_message for domain in TERABOX_DOMAINS):
        # Simulating the download logic (Replace with actual download code)
        try:
            await update.message.reply_text("🔄 Processing your Terabox link... please wait.")
            logger.info(f"Processing download for user {user_id} with message: {user_message}")
            
            # Replace with actual download logic (e.g., fetch file)
            time.sleep(2)  # Simulating download process

            await update.message.reply_text("✅ Your download has started!")
        except Exception as e:
            logger.error(f"Download failed for user {user_id} with error: {str(e)}")
            await update.message.reply_text("❌ Sorry, there was an error while processing your download.")
    else:
        await update.message.reply_text("⚠️ Please send a valid Terabox link.")

# ================== UPDATED START COMMAND ==================
async def start(update: Update, context: CallbackContext):
    """Handle /start command"""
    text = (
        "👋 Welcome to Terabox Download Bot!\n\n"
        "• Send any Terabox link to download\n"
        "• Need help? Just type your message - it goes directly to admins\n"
        f"• Free daily downloads: {MAX_FREE_DOWNLOADS}"
    )
    if update.message.from_user.id in ADMIN_IDS:
        text += "\n\n👮 Admin Commands:\n/reply <user_id> <message>\n/broadcast <message>\n/add_coins <user_id> <coins>\n/check_coins <user_id>"

    await update.message.reply_text(text)


# ================== USER DATA HANDLING ==================

def load_user_data():
    """Load user data from the file"""
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as file:
            return json.load(file)
    return {"users": {}, "message_map": {}}


def save_user_data(data):
    """Save user data to the file"""
    with open(USER_DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)


# ================== MAIN APPLICATION ==================
def main():
    """Start the bot"""
    print("Noob AM ka bot run ho gaya hai!")  # This will print when the bot runs

    application = Application.builder().token(BOT_TOKEN).build()

    handlers = [
        CommandHandler("start", start),
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
