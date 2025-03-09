import os
import json
import logging
from telegram import Update, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
import re  # Importing re module for regular expression matching
import time
import requests
from bs4 import BeautifulSoup

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]  # Admin IDs
USER_DATA_FILE = "user_data.json"
MAX_FREE_DOWNLOADS = 5
# Adding 30+ Terabox domains, including the new teraboxlink.com domain
TERABOX_DOMAINS = [
    "terabox.com", "terabox.cc", "terabox.net", "terabox.co", "terabox.org",
    "terabox.in", "terabox.us", "terabox.biz", "terabox.club", "terabox.info",
    "terabox.co.uk", "terabox.cn", "terabox.asia", "terabox.store", "terabox.tv",
    "terabox.fr", "terabox.ru", "terabox.de", "terabox.it", "terabox.eu",
    "terabox.jp", "terabox.kr", "terabox.my", "terabox.id", "terabox.sg",
    "terabox.hk", "terabox.mex", "terabox.com.br", "terabox.ar", "terabox.co.jp",
    "terabox.co.kr", "terabox.co.in", "terabox.co.id", "terabox.us.com",
    "teraboxlink.com"  # Added domain
]

# ================== LOGGING & UTILITIES ==================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            save_user_data(data)
        except Exception as e:
            logger.error(f"Admin reply failed: {str(e)}")


# ================== MODIFIED MESSAGE HANDLER ==================

async def handle_message(update: Update, context: CallbackContext):
    """Handle incoming messages from users"""
    user_id = update.message.from_user.id
    user_message = update.message.text

    # Logging the received message
    logger.info(f"Received message: {user_message} from user {user_id}")

    # Simplified Terabox link matching regex
    terabox_pattern = re.compile(
        r'https?:\/\/(?:www\.)?(teraboxlink\.com|terabox\.(com|cc|net|co|org|in|us|biz|club|info|co\.uk|cn|asia|store|tv|fr|ru|de|it|eu|jp|kr|my|id|sg|hk|mex|com\.br|ar|co\.jp|co\.kr|co\.in|co\.id|us\.com))\/[a-zA-Z0-9\-_]+',
        re.IGNORECASE)

    if terabox_pattern.match(user_message):
        # User sent a Terabox link, start processing it
        try:
            await update.message.reply_text("🔄 Processing your Terabox link... please wait.")
            logger.info(f"Processing download for user {user_id} with message: {user_message}")

            # Extract the actual download URL from Terabox
            download_url = await get_terabox_download_link(user_message)
            if download_url:
                await update.message.reply_text(f"✅ Your download link: {download_url}")
            else:
                await update.message.reply_text("❌ Could not fetch the download link. Please check if the link is valid.")
        except Exception as e:
            logger.error(f"Download failed for user {user_id} with error: {str(e)}")
            await update.message.reply_text("❌ Sorry, there was an error while processing your download.")
    else:
        logger.warning(f"Invalid Terabox link received: {user_message}")
        await update.message.reply_text("⚠️ Please send a valid Terabox link.")


# Function to scrape Terabox link and get download URL
async def get_terabox_download_link(link: str):
    """Function to scrape and get the download link from Terabox"""
    try:
        # Send HTTP GET request to the link
        response = requests.get(link)
        response.raise_for_status()  # Will raise an exception for HTTP errors

        # Parse the page content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Debug: Print out the raw HTML content for inspection
        print("Page HTML content:")
        print(soup.prettify())  # This will output the HTML structure of the page

        # Find the download link by analyzing the HTML structure of the page
        download_link = None

        # This might change depending on the structure of the Terabox page
        # You should inspect the page structure and look for the correct element
        for link in soup.find_all('a', href=True):
            if 'download' in link['href'].lower():  # A simple condition to check for download link
                download_link = link['href']
                break

        return download_link

    except Exception as e:
        logger.error(f"Error fetching download link from Terabox: {str(e)}")
        return None


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


# ================== ADD COINS FUNCTION ==================

def add_coins(update: Update, context: CallbackContext):
    """Add coins to a specific user"""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    if len(context.args) != 2:
        update.message.reply_text("⚠️ Usage: /add_coins <user_id> <coins>")
        return

    user_id = int(context.args[0])
    coins = int(context.args[1])

    data = load_user_data()

    if str(user_id) not in data["users"]:
        update.message.reply_text("⚠️ User not found!")
        return

    data["users"][str(user_id)].setdefault("coins", 0)
    data["users"][str(user_id)]["coins"] += coins

    save_user_data(data)
    update.message.reply_text(f"✅ Successfully added {coins} coins to user {user_id}.")


# ================== BROADCAST COMMAND ==================

async def broadcast(update: Update, context: CallbackContext):
    """Handle the /broadcast command to send a message to all users"""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    # Get the message to broadcast (the rest of the command)
    message = ' '.join(context.args)
    
    if not message:
        await update.message.reply_text("⚠️ Please provide a message to broadcast.")
        return

    data = load_user_data()

    # Send the message to each user in the 'users' data
    for user_id in data["users"]:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {str(e)}")
    
    await update.message.reply_text(f"✅ Broadcast message sent to all users.")


# ================== MAIN APPLICATION ==================
def main():
    """Start the bot"""
    print("Noob AM ka bot run ho gaya hai!")  # This will print when the bot runs

    application = Application.builder().token(BOT_TOKEN).build()

    handlers = [
        CommandHandler("start", start),
        CommandHandler("broadcast", broadcast),  # Added the broadcast handler
        CommandHandler("add_coins", add_coins),  # Added the add_coins handler
        CommandHandler("check_coins", check_coins),  # Implement your check_coins function if needed
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY & filters.Chat(ADMIN_IDS), handle_admin_reply)
    ]

    application.add_handlers(handlers)
    application.run_polling()


if __name__ == "__main__":
    main()
