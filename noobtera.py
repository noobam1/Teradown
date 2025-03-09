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
ADMIN_IDS = [708030615, 6063791789]  # Add two admin Telegram IDs
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

# ================== TERABOX DOWNLOADER CORE ==================
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
        
        for link in soup.find_all('a', href=re.compile(r'\.(mp4|mkv|webm)$', re.I)):
            href = link['href']
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
            TeraboxDownloader.extract_json_ld,
            TeraboxDownloader.extract_og_meta,
            TeraboxDownloader.scan_scripts,
            TeraboxDownloader.find_video_tag
        ]
        
        for method in extraction_methods:
            if video_url := method(soup):
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
            except:
                continue
        return None

    @staticmethod
    def extract_og_meta(soup):
        meta = soup.find('meta', property="og:video")
        return meta.get('content') if meta else None

    @staticmethod
    def scan_scripts(soup):
        patterns = [
            r'(https?:\\?/\\?/[^\'"]+\.mp4)',
            r'videoUrl\s*:\s*["\'](.*?)["\']',
            r'play_url\s*=\s*["\'](.*?)["\']'
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
    def find_video_tag(soup):
        video_tag = soup.find('video')
        return video_tag['src'] if video_tag and video_tag.get('src') else None

    @staticmethod
    @retry(max_retries=2, delay=1)
    def download_video(session, url):
        try:
            print(f"⬇️ Downloading from: {url}")
            response = session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
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
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🚀 Terabox Video Download Bot\n\n"
        "Send any Terabox link to download videos instantly!\n"
        "• Free daily limit: 4 downloads\n"
        "• Contact admins for premium access\n\n"
        f"Admins: @{context.bot.get_chat(ADMIN_IDS[0]).username} & @{context.bot.get_chat(ADMIN_IDS[1]).username}"
    )

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    url = update.message.text.strip()
    data = load_user_data()

    data["users"].setdefault(str(user_id), {"downloads": 0, "coins": 0})
    
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

    parsed_url = urlparse(url)
    if any(domain in parsed_url.netloc for domain in TERABOX_DOMAINS):
        user_data = data["users"][str(user_id)]
        
        try:
            if user_data["downloads"] >= 4 and user_data["coins"] <= 0:
                raise Exception("Daily limit reached")

            await update.message.reply_text("⏳ Processing...")
            filename = TeraboxDownloader.download(url)
            
            if not filename:
                raise Exception("Download failed after retries")

            await update.message.reply_video(video=open(filename, 'rb'))
            os.remove(filename)
            
            user_data["downloads"] += 1
            save_user_data(data)

        except Exception as e:
            error_message = {
                "Daily limit reached": 
                    f"⚠️ Daily limit reached! Contact admins\n"
                    f"Admins: @{context.bot.get_chat(ADMIN_IDS[0]).username} & @{context.bot.get_chat(ADMIN_IDS[1]).username}",
                "CAPTCHA/Authentication required": 
                    "🔒 This link requires authentication/CAPTCHA",
                "Invalid content type": 
                    "❌ The link doesn't contain a valid video",
                "All extraction methods failed": 
                    "❌ Couldn't find video in the page"
            }.get(str(e), "❌ Download failed. Please try another link")
            
            await update.message.reply_text(error_message)
    else:
        await update.message.reply_text("❌ Invalid link! Supported domains:\n" + "\n".join(TERABOX_DOMAINS))

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
    except:
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
        await context.bot.send_message(
            target_user,
            f"📨 Admin Response:\n\n{update.message.text}"
        )
        del data["reply_map"][key]
        save_user_data(data)

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

    print("🤖 Bot is running successfully!")
    application.run_polling()

if __name__ == "__main__":
    main()