import os
import json
import re
import requests
import time
import logging
import tempfile
from urllib.parse import urlparse, unquote
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters, RateLimiter
from bs4 import BeautifulSoup
from functools import wraps

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]  # अपना Admin ID डालें
USER_DATA_FILE = "user_data.json"
TERABOX_DOMAINS = [
    "terabox.com", "teraboxapp.com", "www.terabox.com",
    "dl.terabox.com", "teraboxlink.com", "tb-video.com",
    "terabox.club", "teraboxcdn.com", "terabox.xyz",
    "teraboxdrive.com", "terabox.to", "terabox.live",
    "www.terabox.club", "terabox.net", "terabox.site",
    "teraboxvideo.com", "terabox.fun", "terabox.org",
    "terabox.ws", "terabox.stream", "terabox.cloud"
]
DEBUG_MODE = True  # एरर डिटेल्स के लिए True पर सेट करें

# ================== LOGGING SETUP ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== UTILITIES ==================
def retry(max_retries=3, delay=2):
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

# ================== TERABOX DOWNLOADER ==================
class TeraboxDownloader:
    @staticmethod
    @retry(max_retries=3, delay=2)
    def download(url: str) -> str:
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.terabox.com/",
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1"
            })

            clean_url = TeraboxDownloader.sanitize_url(url)
            logger.info(f"Processing: {clean_url}")

            response = session.get(clean_url, allow_redirects=True, timeout=20)
            response.raise_for_status()

            if "captcha" in response.text.lower():
                raise Exception("CAPTCHA verification required")

            if "filelist" in response.url:
                return TeraboxDownloader.handle_filelist(session, response)
            return TeraboxDownloader.process_video_page(session, response)

        except Exception as e:
            logger.error(f"Download Error: {str(e)}")
            raise

    @staticmethod
    def sanitize_url(url: str) -> str:
        url = unquote(url).strip()
        url = re.sub(r'[?&](fbclid|utm_[^&]+)=[^&]+', '', url)
        parsed = urlparse(url)
        if parsed.netloc not in TERABOX_DOMAINS:
            raise ValueError("Invalid Terabox domain")
        return url.split('?')[0]

    @staticmethod
    def handle_filelist(session, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        video_links = []
        
        for link in soup.find_all('a', {'class': 'file-download'}):
            href = link.get('href', '')
            if any(ext in href for ext in ['.mp4', '.mkv', '.webm']):
                if not href.startswith('http'):
                    href = f"{urlparse(response.url).scheme}://{urlparse(response.url).netloc}{href}"
                video_links.append(href)
        
        if not video_links:
            raise Exception("No video links in filelist")
            
        return TeraboxDownloader.process_video_page(session, session.get(video_links[0]))

    @staticmethod
    def process_video_page(session, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        extraction_methods = [
            TeraboxDownloader.extract_new_json_pattern,
            TeraboxDownloader.extract_og_meta,
            TeraboxDownloader.scan_scripts_enhanced,
            TeraboxDownloader.find_video_tag
        ]
        
        for method in extraction_methods:
            if video_url := method(soup):
                return TeraboxDownloader.download_video(session, video_url)
        
        raise Exception("All extraction methods failed")

    @staticmethod
    def extract_new_json_pattern(soup):
        for script in soup.find_all('script', {'type': 'application/json'}):
            try:
                data = json.loads(script.string)
                if video_info := data.get('video', {}):
                    return video_info.get('url')
            except:
                continue
        return None

    @staticmethod
    def extract_og_meta(soup):
        meta = soup.find('meta', property='og:video:url')
        return meta['content'] if meta else None

    @staticmethod
    def find_video_tag(soup):
        video = soup.find('video')
        return video['src'] if video else None

    @staticmethod
    def scan_scripts_enhanced(soup):
        patterns = [
            r'"url":"(https:\\/\\/[^"]+\.mp4)"',
            r'videoUrl\s*:\s*["\'](.*?\.mp4)["\']',
            r'play_url\s*=\s*["\'](https?://[^"\']+)["\']'
        ]
        
        for script in soup.find_all('script'):
            text = script.string or ""
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    url = match.group(1).replace('\\/', '/')
                    if url.startswith('http'):
                        return url
        return None

    @staticmethod
    def download_video(session, video_url):
        try:
            response = session.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            
            filename = unquote(urlparse(video_url).path.split('/')[-1])
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return temp_path
        except Exception as e:
            logger.error(f"Download Failed: {str(e)}")
            raise

# ================== BOT HANDLERS ==================
async def start(update: Update, context: CallbackContext):
    try:
        admin1 = await context.bot.get_chat(ADMIN_IDS[0])
        admin2 = await context.bot.get_chat(ADMIN_IDS[1])
        text = (
            "🚀 Terabox Video Download Bot\n\n"
            "Send any Terabox link to download videos instantly!\n"
            "• Free daily limit: 4 downloads\n"
            "• Contact admins for premium access\n\n"
            f"Admins: @{admin1.username} & @{admin2.username}"
        )
    except:
        text = "🚀 Terabox Video Download Bot - Send links to get started!"
    
    await update.message.reply_text(text)

async def add_coins(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin access required!")
        return

    try:
        target_user = int(context.args[0])
        coins = int(context.args[1])
        
        data = load_user_data()
        data["users"].setdefault(str(target_user), {"downloads": 0, "coins": 0})["coins"] += coins
        save_user_data(data)
        
        await update.message.reply_text(f"✅ Added {coins} coins to user {target_user}")
    except (IndexError, ValueError):
        await update.message.reply_text("❗ Usage: /addcoins <user_id> <amount>")

async def handle_admin_reply(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMIN_IDS:
        return

    replied_msg = update.message.reply_to_message
    if not replied_msg:
        return

    data = load_user_data()
    key = f"{update.message.chat.id}_{replied_msg.message_id}"
    if key in data["reply_map"]:
        target_user = data["reply_map"][key]
        try:
            await context.bot.send_message(
                target_user,
                f"📨 Admin Response:\n\n{update.message.text}"
            )
            del data["reply_map"][key]
            save_user_data(data)
        except Exception as e:
            logger.error(f"Admin Reply Error: {str(e)}")

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    data = load_user_data()
    
    # User initialization
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {"downloads": 0, "coins": 0}
        save_user_data(data)
    
    # Daily limit check
    user_data = data["users"][str(user_id)]
    if user_data["downloads"] >= 4 and user_data["coins"] <= 0:
        await update.message.reply_text("❌ Daily limit reached! Contact admin for premium access")
        return
    
    # URL validation
    url = update.message.text
    if not any(domain in url for domain in TERABOX_DOMAINS):
        await update.message.reply_text("❌ Only Terabox links are accepted!")
        return
    
    try:
        # Store reply mapping
        data["reply_map"][f"{update.message.chat.id}_{update.message.message_id}"] = user_id
        save_user_data(data)
        
        # Download process
        file_path = TeraboxDownloader.download(url)
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ Download Successful!",
                    supports_streaming=True
                )
            os.remove(file_path)
            # Update download count
            data["users"][str(user_id)]["downloads"] += 1
            save_user_data(data)
            
    except Exception as e:
        logger.error(f"Handle Message Error: {str(e)}")
        error_msg = f"⚠️ Error: {str(e)}" if DEBUG_MODE else "⚠️ Please try again later"
        await update.message.reply_text(error_msg)

# ================== ERROR HANDLER ==================
async def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Error: {context.error}", exc_info=True)
    if update.message:
        await update.message.reply_text("⚠️ Server error, please try after 5 minutes")

# ================== MAIN APPLICATION ==================
def main():
    application = Application.builder() \
        .token(BOT_TOKEN) \
        .rate_limiter(RateLimiter(max_retries=3, time_period=60)) \
        .build()

    # Handlers
    handlers = [
        CommandHandler("start", start),
        CommandHandler("addcoins", add_coins),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY, handle_admin_reply)
    ]
    
    for handler in handlers:
        application.add_handler(handler)
    
    # Error handler
    application.add_error_handler(error_handler)

    # Initialize data
    if not os.path.exists(USER_DATA_FILE):
        save_user_data({"users": {}, "reply_map": {}})

    logger.info("🤖 Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()