import os
import json
import logging
from telegram import Update, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
import re
import requests
from bs4 import BeautifulSoup

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"  # Replace with your bot's token
ADMIN_IDS = [708030615, 6063791789]  # Admin IDs
USER_DATA_FILE = "user_data.json"
MAX_FREE_DOWNLOADS = 5
TERABOX_DOMAINS = [
    "terabox.com", "teraboxlink.com", "terabox.cc", "terabox.net", "terabox.co", "terabox.org",
    "terabox.in", "terabox.us", "terabox.biz", "terabox.club", "terabox.info", "terabox.co.uk", 
    "terabox.cn", "terabox.asia", "terabox.store", "terabox.tv", "terabox.fr", "terabox.ru", 
    "terabox.de", "terabox.it", "terabox.eu", "terabox.jp", "terabox.kr", "terabox.my", 
    "terabox.id", "terabox.sg", "terabox.hk", "terabox.mex", "terabox.com.br", "terabox.ar", 
    "terabox.co.jp", "terabox.co.kr", "terabox.co.in", "terabox.co.id", "terabox.us.com"
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


# ================== MESSAGE HANDLER ==================

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


# ================== GET TERABOX DOWNLOAD LINK ==================

import requests
import json
import logging
import os
from requests.exceptions import RequestException

# Setup logger
logging.basicConfig(
    filename='terabox_downloader.log',  # Log file name
    level=logging.DEBUG,               # Log level, DEBUG to capture everything
    format='%(asctime)s - %(levelname)s - %(message)s'  # Log format with timestamp
)

# Read the config file for the API key
def load_config():
    try:
        if not os.path.exists("config.json"):
            logging.error("config.json file not found!")
            print("Error: config.json file is missing.")
            return None
        with open("config.json", "r") as config_file:
            config = json.load(config_file)
            if 'rapidapi_key' in config:
                return config['rapidapi_key']
            else:
                logging.error("API key missing in config.json.")
                print("Error: API key missing in config.json.")
                return None
    except Exception as e:
        logging.error(f"Error loading config.json: {e}")
        print(f"Error loading config.json: {e}")
        return None

# Fetch the download link from the TeraBox API
def fetch_download_link(url, api_key):
    headers = {
        'Content-Type': 'application/json',
        'x-rapidapi-host': 'terabox-downloader-direct-download-link-generator.p.rapidapi.com',
        'x-rapidapi-key': api_key
    }
    payload = {"url": url}
    
    try:
        logging.info(f"Fetching download link for URL: {url}")
        response = requests.post(
            'https://terabox-downloader-direct-download-link-generator.p.rapidapi.com/fetch',
            headers=headers,
            data=json.dumps(payload)
        )
        
        # Log the status code of the response
        logging.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data and isinstance(response_data, list):
                download_link = response_data[0].get("url1", "")
                if download_link:
                    logging.info(f"Download link fetched successfully: {download_link}")
                    return download_link
                else:
                    logging.error("Download link not found in the response.")
                    return None
            else:
                logging.error("Invalid response data.")
                return None
        else:
            logging.error(f"Failed to fetch the download link, status code: {response.status_code}")
            return None
    except RequestException as e:
        logging.error(f"An error occurred while fetching the download link: {e}")
        return None

# Function to download the file from the URL
def download_file(download_url, filename):
    try:
        logging.info(f"Starting download for: {filename}")
        response = requests.get(download_url, stream=True)
        
        if response.status_code == 200:
            with open(filename, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            logging.info(f"File downloaded successfully: {filename}")
        else:
            logging.error(f"Failed to download file, status code: {response.status_code}")
    except RequestException as e:
        logging.error(f"An error occurred while downloading the file: {e}")

# Main function
def main():
    # Load API key from config file
    api_key = load_config()
    if api_key is None:
        print("❌ Error: Could not load API key.")
        return
    
    # Ask user for the TeraBox sharing URL
    terabox_url = input("Enter the TeraBox sharing URL: ")
    
    # Basic validation for URL
    if not terabox_url.startswith("https://teraboxlink.com/s/"):
        print("❌ Invalid TeraBox URL format. Please check the URL.")
        logging.error(f"Invalid URL format: {terabox_url}")
        return
    
    logging.info(f"Starting to process the TeraBox URL: {terabox_url}")
    
    # Fetch the download link
    download_link = fetch_download_link(terabox_url, api_key)
    
    if download_link:
        # Generate filename from the URL or use a default name
        filename = "downloaded_file.mp4"
        
        # Prompt for custom filename
        user_filename = input(f"Enter a name for the downloaded file (default: {filename}): ")
        if user_filename:
            filename = user_filename
        
        logging.info(f"Download link: {download_link}")
        
        # Proceed to download the file
        download_file(download_link, filename)
        print(f"File downloaded successfully as {filename}")
    else:
        logging.error("Could not fetch the download link.")
        print("❌ Could not fetch the download link. Please check if the link is valid.")

if __name__ == "__main__":
    main()
