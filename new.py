import os
import json
import logging
import requests
from telegram import Update, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
import re
import time

# ================== CONFIGURATION ==================
BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_IDS = [708030615, 6063791789]  # Admin IDs
USER_DATA_FILE = "user_data.json"
MAX_FREE_DOWNLOADS = 5
TERABOX_DOMAINS = [
    "terabox.com", "terabox.cc", "terabox.net", "terabox.co", "terabox.org",
    "terabox.in", "terabox.us", "terabox.biz", "terabox.club", "terabox.info",
    "terabox.co.uk", "terabox.cn", "terabox.asia", "terabox.store", "terabox.tv",
    "terabox.fr", "terabox.ru", "terabox.de", "terabox.it", "terabox.eu",
    "terabox.jp", "terabox.kr", "terabox.my", "terabox.id", "terabox.sg",
    "terabox.hk", "terabox.mex", "terabox.com.br", "terabox.ar", "terabox.co.jp",
    "terabox.co.kr", "terabox.co.in", "terabox.co.id", "terabox.us.com",
    "teraboxlink.com"
]

# ================== LOGGING & UTILITIES ==================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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

# ================== MODIFIED MESSAGE HANDLER ==================

async def handle_message(update: Update, context: CallbackContext):
    """Handle incoming messages from users"""
    user_id = update.message.from_user.id
    user_message = update.message.text

    # Logging the received message
    logger.info(f"Received message: {user_message} from user {user_id}")

    # Terabox link matching regex
    terabox_pattern = re.compile(
        r'https?:\/\/(?:www\.)?(teraboxlink\.com|terabox\.(com|cc|net|co|org|in|us|biz|club|info|co\.uk|cn|asia|store|tv|fr|ru|de|it|eu|jp|kr|my|id|sg|hk|mex|com\.br|ar|co\.jp|co\.kr|co\.in|co\.id|us\.com))\/[a-zA-Z0-9\-_]+',
        re.IGNORECASE)

    if terabox_pattern.match(user_message):
        # Processing the Terabox link
        try:
            await update.message.reply_text("🔄 Processing your Terabox link... please wait.")
            logger.info(f"Processing download for user {user_id} with message: {user_message}")
            
            # Extract direct download URL using Apify's API
            download_url = get_terabox_download_url(user_message)
            if download_url:
                # Download the file
                file_path = download_file(download_url)
                if file_path:
                    # Send the file to the user
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=open(file_path, 'rb'),
                        filename=os.path.basename(file_path)
                    )
                    os.remove(file_path)  # Clean up the downloaded file
                    await update.message.reply_text("✅ Your download has completed!")
                else:
                    await update.message.reply_text("❌ Failed to download the file.")
            else:
                await update.message.reply_text("❌ Failed to extract download URL.")
        except Exception as e:
            logger.error(f"Download failed for user {user_id} with error: {str(e)}")
            await update.message.reply_text("❌ Sorry, there was an error while processing your download.")
    else:
        logger.warning(f"Invalid Terabox link received: {user_message}")
        await update.message.reply_text("⚠️ Please send a valid Terabox link.")

def get_terabox_download_url(terabox_link):
    """Extract direct download URL from Terabox link using Apify's API"""
    # Implement API call to Apify's TeraBox Video/File Downloader
    # Refer to: https://apify.com/easyapi/terabox-video-file-downloader/api/python
    # Return the download URL
    pass

def download_file(url):
    """Download file from the given URL and return the file path"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            file_path = f"downloads/{time.time()}.mp4"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            return file_path
        else:
            return None
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return None

# ================== MAIN APPLICATION ==================
def main():
    """Start the bot"""
    print("Bot is running...")

    application = Application.builder().token(BOT_TOKEN).build()

    handlers = [
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
    ]

    application.add_handlers(handlers)
    application.run_polling()

if __name
::contentReference[oaicite:0]{index=0}
 
