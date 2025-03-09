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

    # [Keep other methods from previous implementation]

# ================== BOT HANDLERS (FIXED) ==================
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

async def handle_message(update: Update, context: CallbackContext):
    try:
        user_id = update.message.from_user.id
        url = update.message.text.strip()
        data = load_user_data()

        data["users"].setdefault(str(user_id), {"downloads": 0, "coins": 0})
        
        # Get admin usernames first
        admin1 = await context.bot.get_chat(ADMIN_IDS[0])
        admin2 = await context.bot.get_chat(ADMIN_IDS[1])
        admin_mention = f"@{admin1.username} & @{admin2.username}"

        # Admin notifications
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"📥 New Request\nUser: {user_id}\nLink: {url}"
                )
            except Exception as e:
                print(f"Admin Alert Error: {e}")

        # Processing
        parsed_url = urlparse(url)
        if any(domain in parsed_url.netloc for domain in TERABOX_DOMAINS):
            user_data = data["users"][str(user_id)]
            
            try:
                if user_data["downloads"] >= 4 and user_data["coins"] <= 0:
                    raise Exception("Daily limit reached")

                await update.message.reply_text("⏳ Processing...")
                filename = TeraboxDownloader.download(url)
                
                if filename:
                    await update.message.reply_video(video=open(filename, 'rb'))
                    os.remove(filename)
                    user_data["downloads"] += 1
                    save_user_data(data)
                else:
                    raise Exception("Download failed after retries")

            except Exception as e:
                error_message = {
                    "Daily limit reached": f"⚠️ Daily limit reached! Contact admins\nAdmins: {admin_mention}",
                    "CAPTCHA verification required": "🔒 CAPTCHA detected! Try in browser first",
                    "Invalid content type": "📛 Invalid media format",
                    "All extraction methods failed": "🔧 Couldn't process this link structure"
                }.get(str(e), "❌ Download failed. Try another link")
                
                await update.message.reply_text(error_message)
        else:
            await update.message.reply_text("❌ Unsupported domain. Supported:\n" + "\n".join(TERABOX_DOMAINS))

    except Exception as e:
        print(f"Global Handler Error: {str(e)}")
        await update.message.reply_text("🔧 Temporary error. Please try again later")

# [Keep add_coins and handle_admin_reply from previous implementation]

# ================== MAIN APPLICATION ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    handlers = [
        CommandHandler("start", start),
        CommandHandler("addcoins", add_coins),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY, handle_admin_reply)
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    if not os.path.exists(USER_DATA_FILE):
        save_user_data({"users": {}, "reply_map": {}})

    print("🤖 Bot running successfully with all fixes!")
    application.run_polling()

if __name__ == "__main__":
    main()