import os
import json
import re
import requests
import time
from urllib.parse import urlparse, unquote
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
from bs4 import BeautifulSoup
from functools import wraps

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]  # Replace with admin Telegram IDs
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
                    print(f"🔄 Retry {retries+1}/{max_retries} failed: {str(e)}")
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

# ================== ENHANCED DOWNLOADER ==================
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
            print(f"🔗 Processing: {clean_url}")

            response = session.get(clean_url, allow_redirects=True, timeout=20)
            response.raise_for_status()

            # New anti-captcha detection
            if "captcha" in response.text.lower():
                raise Exception("CAPTCHA verification required")

            if "filelist" in response.url:
                return TeraboxDownloader.handle_filelist(session, response)
            return TeraboxDownloader.process_video_page(session, response)

        except Exception as e:
            print(f"🚨 Main Error: {str(e)}")
            raise

    @staticmethod
    def sanitize_url(url: str) -> str:
        url = unquote(url).strip()
        url = re.sub(r'[?&](fbclid|utm_[^&]+)=[^&]+', '', url)
        return url.split('?')[0]

    @staticmethod
    def handle_filelist(session, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        video_links = []
        
        # New pattern for filelist items
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
        
        # Enhanced extraction methods
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
        """Handles new Terabox JSON structure"""
        for script in soup.find_all('script', {'type': 'application/json'}):
            try:
                data = json.loads(script.string)
                if video_info := data.get('video', {}):
                    return video_info.get('url')
            except:
                continue
        return None

    @staticmethod
    def scan_scripts_enhanced(soup):
        """Updated regex patterns for 2024 links"""
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

# ... [Keep all previous imports and configurations] ...

# ================== BOT HANDLERS ==================
async def start(update: Update, context: CallbackContext):
    try:
        admin1 = await context.bot.get_chat(ADMIN_IDS[0])
        admin2 = await context.bot.get_chat(ADMIN_IDS[1])
        await update.message.reply_text(
            "🚀 Terabox Video Download Bot\n\n"
            "Send any Terabox link to download videos instantly!\n"
            "• Free daily limit: 4 downloads\n"
            "• Contact admins for premium access\n\n"
            f"Admins: @{admin1.username} & @{admin2.username}"
        )
    except Exception as e:
        print(f"Start Error: {str(e)}")
        await update.message.reply_text(
            "🚀 Terabox Video Download Bot\n\n"
            "Send any Terabox link to get started!"
        )

async def add_coins(update: Update, context: CallbackContext):
    """Admin command to add coins to users"""
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin access required!")
        return

    try:
        # Parse command arguments
        target_user = int(context.args[0])
        coins = int(context.args[1])
        
        # Update user data
        data = load_user_data()
        data["users"].setdefault(str(target_user), {"downloads": 0, "coins": 0})["coins"] += coins
        save_user_data(data)
        
        await update.message.reply_text(f"✅ Added {coins} coins to user {target_user}")
    except:
        await update.message.reply_text("❗ Usage: /addcoins <user_id> <amount>")

async def handle_admin_reply(update: Update, context: CallbackContext):
    """Handle admin replies to user messages"""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    # Get the original message being replied to
    replied_msg = update.message.reply_to_message
    if not replied_msg:
        return

    # Find target user from reply map
    data = load_user_data()
    key = f"{update.message.chat.id}_{replied_msg.message_id}"
    if key in data["reply_map"]:
        target_user = data["reply_map"][key]
        try:
            await context.bot.send_message(
                target_user,
                f"📨 Admin Response:\n\n{update.message.text}"
            )
            # Cleanup reply mapping
            del data["reply_map"][key]
            save_user_data(data)
        except Exception as e:
            print(f"Admin Reply Error: {str(e)}")

async def handle_message(update: Update, context: CallbackContext):
    # ... [Keep existing handle_message code] ...

# ================== MAIN APPLICATION ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers in proper order
    handlers = [
        CommandHandler("start", start),
        CommandHandler("addcoins", add_coins),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY, handle_admin_reply)
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    # Initialize data storage
    if not os.path.exists(USER_DATA_FILE):
        save_user_data({"users": {}, "reply_map": {}})

    print("🤖 Bot running successfully with all commands!")
    application.run_polling()

if __name__ == "__main__":
    main()