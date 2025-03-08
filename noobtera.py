import os
import json
import re
import requests
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
from bs4 import BeautifulSoup

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]  # Your Telegram User IDs
USER_DATA_FILE = "user_data.json"
TERABOX_DOMAINS = [
    "terabox.com", "teraboxapp.com", "www.terabox.com",
    "dl.terabox.com", "teraboxlink.com", "tb-video.com",
    "terabox.club", "teraboxcdn.com", "terabox.xyz",
    "teraboxdrive.com", "terabox.to", "terabox.live"
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

# ================== TERABOX DOWNLOADER ==================
class TeraboxDownloader:
    @staticmethod
    def download(url: str) -> str:
        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.terabox.com/",
                "Accept-Language": "en-US,en;q=0.9",
            }

            # Clean URL and handle redirects
            clean_url = re.sub(r'\?.*', '', url.strip())
            response = session.get(clean_url, headers=headers, allow_redirects=True, timeout=20)
            response.raise_for_status()

            # Advanced URL extraction
            soup = BeautifulSoup(response.text, 'html.parser')
            video_url = TeraboxDownloader.extract_video_url(soup)
            
            if not video_url:
                return None

            # Download video with retry logic
            return TeraboxDownloader.download_video(session, video_url, headers)

        except Exception as e:
            print(f"Download Error: {str(e)}")
            return None

    @staticmethod
    def extract_video_url(soup):
        # Try multiple extraction methods
        script_tags = soup.find_all('script', text=re.compile(r'(video_url|play_url|play_addr|file_id|url)'))
        
        for script in script_tags:
            # Method 1: JSON-like pattern
            matches = re.findall(r'"([^"]+_url)":"([^"]+)"', script.text)
            for key, value in matches:
                if key in ["video_url", "play_url", "download_url", "direct_url"]:
                    return value.replace('\\u002F', '/').replace('\\', '')

            # Method 2: Direct URL pattern
            match = re.search(r'(https?:\\?/\\?/[^\'"\s]+\.mp4)', script.text)
            if match:
                return match.group(1).replace('\\', '')

        return None

    @staticmethod
    def download_video(session, url, headers):
        try:
            response = session.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            filename = "terabox_video.mp4"
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
            return filename
        except Exception as e:
            print(f"Video Download Error: {str(e)}")
            return None

# ================== BOT HANDLERS ==================
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("🚀 Welcome to Terabox Download Bot!\nSend any Terabox link to download.")

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    url = update.message.text.strip()
    data = load_user_data()

    # Register new user
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {"downloads": 0, "coins": 0}
        save_user_data(data)

    # Forward to admins
    for admin_id in ADMIN_IDS:
        try:
            sent_msg = await context.bot.send_message(
                admin_id,
                f"📥 New Download Request\nUser: {user_id}\nLink: {url}"
            )
            data["reply_map"][f"{admin_id}_{sent_msg.message_id}"] = user_id
        except Exception as e:
            print(f"Admin Notification Error: {e}")
    save_user_data(data)

    # Validate and process
    parsed_url = urlparse(url)
    if any(domain in parsed_url.netloc for domain in TERABOX_DOMAINS):
        user_data = data["users"][str(user_id)]
        
        if user_data["downloads"] < 4 or user_data["coins"] > 0:
            await update.message.reply_text("⏳ Processing your download...")
            
            if user_data["downloads"] >= 4:
                user_data["coins"] -= 1

            filename = TeraboxDownloader.download(url)
            if filename:
                await update.message.reply_video(video=open(filename, 'rb'))
                os.remove(filename)
                user_data["downloads"] += 1
                save_user_data(data)
            else:
                await update.message.reply_text("❌ Download failed! Please check the link.")
        else:
            await update.message.reply_text(
                "⚠️ Daily limit exceeded! Contact admin for more downloads.\n"
                f"Admin: @{context.bot.get_chat(ADMIN_IDS[0]).username}"
            )
    else:
        await update.message.reply_text("❌ Invalid link! Only Terabox links are supported.")

async def add_coins(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized access!")
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
    # Initialize bot
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    handlers = [
        CommandHandler("start", start),
        CommandHandler("addcoins", add_coins),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY, handle_admin_reply)
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    # Start bot
    application.run_polling()

if __name__ == "__main__":
    # Initialize user data
    if not os.path.exists(USER_DATA_FILE):
        save_user_data({"users": {}, "reply_map": {}})
    
    # Start the bot
    main()