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
ADMIN_IDS = [708030615, 6063791789]  # Add your Telegram ID
USER_DATA_FILE = "user_data.json"
TERABOX_DOMAINS = [
    "terabox.com", "teraboxapp.com", "www.terabox.com",
    "dl.terabox.com", "teraboxlink.com", "tb-video.com",
    "terabox.club", "teraboxcdn.com", "terabox.xyz",
    "teraboxdrive.com", "terabox.to", "terabox.live",
    "www.terabox.club", "terabox.net", "terabox.site",
    "teraboxvideo.com", "terabox.fun", "terabox.org"
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
                    print(f"Retry {retries+1}/{max_retries} failed: {str(e)}")
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

# ================== ADVANCED TERABOX DOWNLOADER ==================
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
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive"
            })

            clean_url = TeraboxDownloader.sanitize_url(url)
            print(f"🔗 Processing: {clean_url}")

            response = session.get(clean_url, allow_redirects=True, timeout=20)
            response.raise_for_status()

            # Detect CAPTCHA or authentication walls
            if "captcha" in response.text.lower() or "login" in response.text.lower():
                raise Exception("CAPTCHA/Authentication required")

            if "filelist" in response.url:
                return TeraboxDownloader.handle_filelist(session, response)
            return TeraboxDownloader.process_video_page(session, response)

        except Exception as e:
            print(f"🚨 Main Error: {str(e)}")
            raise

    @staticmethod
    def sanitize_url(url: str) -> str:
        url = unquote(url).strip()
        url = re.sub(
            r'[?&](fbclid|utm_[^&]+|_gl|gclid|msclkid)=[^&]+', 
            '', 
            url
        )
        url = re.sub(r'[#?&]$', '', url)
        return url.split('?')[0]

    @staticmethod
    def handle_filelist(session, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        video_links = []
        
        for link in soup.find_all('a', href=re.compile(r'\.(mp4|mkv|webm)$', re.I)):
            href = link['href']
            if not href.startswith('http'):
                href = f"{urlparse(response.url).scheme}://{urlparse(response.url).netloc}{href}"
            video_links.append(href)
        
        if not video_links:
            raise Exception("No video links in filelist")
            
        print(f"📂 Found {len(video_links)} video links")
        return TeraboxDownloader.process_video_page(session, session.get(video_links[0]))

    @staticmethod
    def process_video_page(session, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        extraction_strategies = [
            TeraboxDownloader.extract_json_ld,
            TeraboxDownloader.extract_meta_tags,
            TeraboxDownloader.scan_scripts,
            TeraboxDownloader.find_video_tag
        ]
        
        for strategy in extraction_strategies:
            if video_url := strategy(soup):
                print(f"✅ Extracted via {strategy.__name__}")
                return TeraboxDownloader.download_video(session, video_url)
        
        raise Exception("All extraction methods failed")

    @staticmethod
    def extract_json_ld(soup):
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") == "VideoObject":
                    return data.get("contentUrl")
            except Exception as e:
                print(f"JSON-LD Error: {str(e)}")
        return None

    @staticmethod
    def extract_meta_tags(soup):
        for meta in soup.find_all('meta'):
            if meta.get('property') in ['og:video', 'twitter:player:stream']:
                return meta.get('content')
        return None

    @staticmethod
    def scan_scripts(soup):
        patterns = [
            r'(https?:\\?/\\?/[^\'"]+\.mp4)',
            r'videoUrl\s*[:=]\s*["\'](.*?)["\']',
            r'play_url\s*[:=]\s*["\'](.*?)["\']',
            r'src\s*[:=]\s*["\'](.*?\.mp4)["\']',
            r'file_url\s*[:=]\s*["\'](.*?)["\']'
        ]
        
        for script in soup.find_all('script'):
            text = script.string or ""
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    url = match.group(1).replace('\\/', '/')
                    if url.startswith('http'):
                        return url
        return None

    @staticmethod
    def find_video_tag(soup):
        video_tag = soup.find('video')
        if video_tag and video_tag.get('src'):
            return video_tag['src']
        return None

    @staticmethod
    @retry(max_retries=2, delay=1)
    def download_video(session, url):
        try:
            print(f"⬇️ Downloading from: {url}")
            response = session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            if 'video/' not in response.headers.get('Content-Type', ''):
                raise Exception("Invalid content type")
            
            filename = "terabox_video.mp4"
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return filename
        except Exception as e:
            print(f"🚨 Download Failed: {str(e)}")
            raise

# ================== BOT HANDLERS ==================
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    url = update.message.text.strip()
    data = load_user_data()

    # User initialization
    data["users"].setdefault(str(user_id), {"downloads": 0, "coins": 0})
    
    # Admin notification
    for admin_id in ADMIN_IDS:
        try:
            sent_msg = await context.bot.send_message(
                admin_id,
                f"📥 New Request\nUser: {user_id}\nLink: {url}"
            )
            data["reply_map"][f"{admin_id}_{sent_msg.message_id}"] = user_id
        except Exception as e:
            print(f"Admin Alert Error: {e}")
    save_user_data(data)

    # Processing
    parsed_url = urlparse(url)
    if any(domain in parsed_url.netloc for domain in TERABOX_DOMAINS):
        user_data = data["users"][str(user_id)]
        
        try:
            if user_data["downloads"] >= 4 and user_data["coins"] <= 0:
                raise Exception("Daily limit reached")

            await update.message.reply_text("⏳ Processing your request...")
            filename = TeraboxDownloader.download(url)
            
            if not filename:
                raise Exception("Download failed after retries")

            await update.message.reply_video(video=open(filename, 'rb'))
            os.remove(filename)
            
            user_data["downloads"] += 1
            if user_data["downloads"] >= 4:
                user_data["coins"] = max(user_data["coins"] - 1, 0)
            
            save_user_data(data)

        except Exception as e:
            error_message = {
                "Daily limit reached": 
                    f"⚠️ Daily limit reached! Contact admin\n@{context.bot.get_chat(ADMIN_IDS[0]).username}",
                "CAPTCHA/Authentication required": 
                    "🔒 This link requires authentication/CAPTCHA",
                "Invalid content type": 
                    "❌ The link doesn't contain a valid video",
                "All extraction methods failed": 
                    "❌ Couldn't find video in the page"
            }.get(str(e), "❌ Download failed. Please try another link")
            
            await update.message.reply_text(error_message)
            print(f"User Error: {str(e)}")

    else:
        await update.message.reply_text("❌ Invalid link! Supported domains:\n" + "\n".join(TERABOX_DOMAINS))

# [Keep other handlers (start, add_coins, handle_admin_reply) from previous code]

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

    print("🤖 Bot is actively monitoring...")
    application.run_polling()

if __name__ == "__main__":
    main()