import os
import json
import re
import requests
import time
import logging
import tempfile
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
from bs4 import BeautifulSoup
from functools import wraps

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]
USER_DATA_FILE = "user_data.json"
MAX_FREE_DOWNLOADS = 5
TERABOX_DOMAINS = [
    "terabox.com", "teraboxapp.com", "www.terabox.com",
    "dl.terabox.com", "teraboxlink.com", "tb-video.com",
    "terabox.club", "teraboxcdn.com", "terabox.xyz",
    "teraboxdrive.com", "terabox.to", "terabox.live",
    "www.terabox.club", "terabox.net", "terabox.site",
    "teraboxvideo.com", "terabox.fun", "terabox.org",
    "terabox.ws", "terabox.stream", "terabox.cloud",
    "tb1.terabox.com", "tb2.terabox.com", "tb3.terabox.com",
    "terabox.download", "teraboxapi.com", "terabox-cdn.net"
]

# ================== LOGGING SETUP ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== UTILITIES ==================
def retry(max_retries=3, delay=2):
    """Retry decorator को सही जगह पर डिफाइन किया गया"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Retry {retries+1}/{max_retries} failed: {str(e)}")
                    retries += 1
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

# ================== DATA MANAGEMENT ==================
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": {}, "reply_map": {}}

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_today_downloads(user_id):
    data = load_user_data()
    user = data["users"].get(str(user_id), {"download_history": []})
    now = datetime.now()
    return sum(1 for t in user["download_history"] if 
        (now - datetime.strptime(t, "%Y-%m-%d %H:%M:%S")) < timedelta(hours=24))

# ================== ENHANCED DOWNLOADER ==================
class TeraboxDownloader:
    @staticmethod
    @retry(max_retries=3, delay=5)  # ✅ Retry decorator अब काम करेगा
    def download(url: str) -> str:
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://www.terabox.com/",
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1"
            })

            # URL सैनिटाइजेशन
            url = unquote(url).strip()
            url = re.sub(r'[?&](fbclid|utm_[^&]+)=[^&]+', '', url)
            parsed = urlparse(url)
            if not any(domain in parsed.netloc for domain in TERABOX_DOMAINS):
                raise ValueError("Invalid Terabox domain")

            response = session.get(url, allow_redirects=True, timeout=30)
            response.raise_for_status()

            if "captcha" in response.text.lower():
                raise ValueError("CAPTCHA verification required")

            # डाउनलोड लॉजिक
            soup = BeautifulSoup(response.text, 'html.parser')
            video_url = soup.find('meta', property='og:video:url')['content']
            return self.download_video(session, video_url)

        except Exception as e:
            logger.error(f"Download Error: {str(e)}")
            raise

    @staticmethod
    def download_video(session, video_url):
        try:
            response = session.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            
            filename = unquote(urlparse(video_url).path.split('/')[-1]
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return temp_path
        except Exception as e:
            logger.error(f"Video Download Failed: {str(e)}")
            raise

# ================== BOT HANDLERS ==================
async def start(update: Update, context: CallbackContext):
    text = (
        "🚀 Terabox Video Download Bot\n\n"
        f"• Free Downloads/Day: {MAX_FREE_DOWNLOADS}\n"
        "• Send any Terabox link to download"
    )
    await update.message.reply_text(text)

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    data = load_user_data()
    
    # यूजर इनिशियलाइजेशन
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {
            "coins": 0,
            "download_history": []
        }
        save_user_data(data)
    
    # डाउनलोड लिमिट चेक
    if get_today_downloads(user_id) >= MAX_FREE_DOWNLOADS:
        await update.message.reply_text("❌ Daily limit reached!")
        return
    
    try:
        file_path = TeraboxDownloader.download(update.message.text)
        if file_path:
            with open(file_path, 'rb') as f:
                await update.message.reply_video(f)
            os.remove(file_path)
            
            # डाउनलोड हिस्ट्री अपडेट
            data["users"][str(user_id)]["download_history"].append(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            save_user_data(data)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ================== MAIN APPLICATION ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # हैंडलर्स
    handlers = [
        CommandHandler("start", start),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    ]
    
    application.add_handlers(handlers)
    logger.info("🤖 Bot started successfully!")
    application.run_polling()

if __name__ == "__main__":
    main()