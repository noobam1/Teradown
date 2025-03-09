import os
import json
import re
import requests
from urllib.parse import urlparse, unquote
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
from bs4 import BeautifulSoup

# ================== CONFIGURATION ==================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_IDS = [123456789]  # Add your Telegram ID
USER_DATA_FILE = "user_data.json"
TERABOX_DOMAINS = [
    "terabox.com", "teraboxapp.com", "www.terabox.com",
    "dl.terabox.com", "teraboxlink.com", "tb-video.com",
    "terabox.club", "teraboxcdn.com", "terabox.xyz",
    "teraboxdrive.com", "terabox.to", "terabox.live",
    "www.terabox.club", "terabox.net", "terabox.site",
    "teraboxvideo.com", "terabox.fun", "terabox.org"
]

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
    def download(url: str) -> str:
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.terabox.com/",
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1"
            })

            # Clean and verify URL
            clean_url = TeraboxDownloader.sanitize_url(url)
            print(f"Processing: {clean_url}")

            # Handle redirects and different page types
            response = session.get(clean_url, allow_redirects=True, timeout=20)
            response.raise_for_status()

            if "filelist" in response.url:
                return TeraboxDownloader.handle_filelist(session, response)
            return TeraboxDownloader.process_video_page(session, response)

        except Exception as e:
            print(f"Main Error: {str(e)}")
            return None

    @staticmethod
    def sanitize_url(url: str) -> str:
        url = unquote(url).strip()
        url = re.sub(r'[?&](fbclid|utm_[^&]+)=[^&]+', '', url)
        url = re.sub(r'(%23|#|\?|&)$', '', url)
        return url.split('?')[0]

    @staticmethod
    def handle_filelist(session, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        video_links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            if any(ext in href for ext in ['.mp4', '.mkv', '.webm']):
                video_links.append(link['href'])
        
        if not video_links:
            return None
            
        video_path = video_links[0]
        if not video_path.startswith('http'):
            base_url = f"{urlparse(response.url).scheme}://{urlparse(response.url).netloc}"
            video_url = base_url + video_path
        else:
            video_url = video_path
            
        print(f"Found video: {video_url}")
        return TeraboxDownloader.process_video_page(session, session.get(video_url))

    @staticmethod
    def process_video_page(session, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Multiple extraction strategies
        extraction_methods = [
            TeraboxDownloader.extract_json_ld,
            TeraboxDownloader.extract_og_meta,
            TeraboxDownloader.extract_direct_link,
            TeraboxDownloader.scan_scripts_deep
        ]
        
        for method in extraction_methods:
            video_url = method(soup)
            if video_url:
                print(f"Extracted via {method.__name__}")
                return TeraboxDownloader.download_video(session, video_url)
        
        return None

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
    def extract_direct_link(soup):
        for link in soup.find_all('a', href=True):
            if link['href'].lower().endswith(('.mp4', '.mkv')):
                return link['href']
        return None

    @staticmethod
    def scan_scripts_deep(soup):
        patterns = [
            r'(https?:\\?/\\?/[^\'"]+\.mp4)',
            r'videoUrl\s*:\s*["\'](.*?)["\']',
            r'play_url\s*=\s*["\'](.*?)["\']',
            r'src\s*:\s*["\'](.*?\.mp4)["\']'
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
    def download_video(session, url):
        try:
            print(f"Downloading: {url}")
            response = session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            filename = "terabox_video.mp4"
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return filename
        except Exception as e:
            print(f"Download Failed: {str(e)}")
            return None

# ================== BOT HANDLERS ==================
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🎬 Terabox Video Download Bot\n\n"
        "Send any Terabox link to download videos instantly!\n"
        "Free daily limit: 4 downloads\n"
        "Contact admin for premium access"
    )

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    url = update.message.text.strip()
    data = load_user_data()

    # User registration
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {"downloads": 0, "coins": 0}
        save_user_data(data)

    # Notify admins
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

    # Process request
    parsed_url = urlparse(url)
    if any(domain in parsed_url.netloc for domain in TERABOX_DOMAINS):
        user_data = data["users"][str(user_id)]
        
        try:
            if user_data["downloads"] < 4 or user_data["coins"] > 0:
                await update.message.reply_text("⏳ Processing...")
                
                if user_data["downloads"] >= 4:
                    user_data["coins"] -= 1

                filename = TeraboxDownloader.download(url)
                if filename:
                    await update.message.reply_video(video=open(filename, 'rb'))
                    os.remove(filename)
                    user_data["downloads"] += 1
                    save_user_data(data)
                else:
                    await update.message.reply_text("❌ Failed to download. Try another link.")
            else:
                await update.message.reply_text(
                    "⚠️ Daily limit reached! Contact admin\n"
                    f"Admin: @{context.bot.get_chat(ADMIN_IDS[0]).username}"
                )
        except Exception as e:
            print(f"Handler Error: {str(e)}")
            await update.message.reply_text("🔧 Temporary issue. Please try later")
    else:
        await update.message.reply_text("❌ Invalid link! Only Terabox links supported")

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
    
    # Register handlers
    handlers = [
        CommandHandler("start", start),
        CommandHandler("addcoins", add_coins),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY, handle_admin_reply)
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    # Initialize data
    if not os.path.exists(USER_DATA_FILE):
        save_user_data({"users": {}, "reply_map": {}})

    # Start bot
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()