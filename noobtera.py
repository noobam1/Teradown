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
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]  # Add your Telegram ID(s)
USER_DATA_FILE = "user_data.json"
TERABOX_DOMAINS = [
    "terabox.com", "teraboxapp.com", "www.terabox.com",
    "dl.terabox.com", "teraboxlink.com", "tb-video.com",
    "terabox.club", "teraboxcdn.com", "terabox.xyz",
    "teraboxdrive.com", "terabox.to", "terabox.live",
    "www.terabox.club", "terabox.net", "terabox.site"
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

# ================== ENHANCED TERABOX DOWNLOADER ==================
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

            clean_url = TeraboxDownloader.sanitize_url(url)
            print(f"Processing URL: {clean_url}")
            
            response = session.get(clean_url, headers=headers, 
                                 allow_redirects=True, timeout=20)
            response.raise_for_status()

            if "filelist" in clean_url:
                return TeraboxDownloader.handle_filelist(session, response, headers)
                
            return TeraboxDownloader.extract_and_download(session, response, headers)

        except Exception as e:
            print(f"Download Error: {str(e)}")
            return None

    @staticmethod
    def sanitize_url(url: str) -> str:
        url = unquote(url).strip()
        url = re.sub(r'&?(fbclid|utm_source)=[^&]+', '', url)
        url = re.sub(r'\?.*', '', url)
        url = re.sub(r'\/$', '', url)
        return url

    @staticmethod
    def handle_filelist(session, response, headers):
        soup = BeautifulSoup(response.text, 'html.parser')
        file_links = soup.find_all('a', href=re.compile(r'/share/link'))
        
        if not file_links:
            return None
            
        first_file = file_links[0]['href']
        file_url = f"https://www.terabox.club{first_file}"
        print(f"Found filelist item: {file_url}")
        return TeraboxDownloader.extract_and_download(session, session.get(file_url), headers)

    @staticmethod
    def extract_and_download(session, response, headers):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try multiple extraction methods
        video_url = TeraboxDownloader.extract_json_ld(soup)
        if not video_url:
            video_url = TeraboxDownloader.scan_scripts(soup)
        if not video_url:
            video_url = TeraboxDownloader.check_meta_tags(soup)
        
        if not video_url:
            print("No video URL found in page")
            return None

        print(f"Downloading video from: {video_url}")
        return TeraboxDownloader.download_video(session, video_url, headers)

    @staticmethod
    def extract_json_ld(soup):
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = json.loads(script.string)
                if data.get("@type") == "VideoObject":
                    return data.get("contentUrl")
            except:
                continue
        return None

    @staticmethod
    def scan_scripts(soup):
        patterns = [
            r'"play_url":"(.*?)"',
            r'video_url":"(.*?)"',
            r'\\/\\/([^\\"]+\.mp4)',
            r'https?:\/\/[^"\'\s]+\.mp4'
        ]
        
        for script in soup.find_all('script'):
            for pattern in patterns:
                match = re.search(pattern, script.text)
                if match:
                    url = match.group(1) if match.groups() else match.group(0)
                    url = url.replace('\\u002F', '/').replace('\\', '')
                    if not url.startswith('http'):
                        url = f'https://{url}'
                    return url
        return None

    @staticmethod
    def check_meta_tags(soup):
        for meta in soup.find_all('meta'):
            if meta.get('property') in ['og:video', 'og:video:url']:
                return meta.get('content')
        return None

    @staticmethod
    def download_video(session, url, headers):
        try:
            response = session.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            filename = "terabox_video.mp4"
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return filename
        except Exception as e:
            print(f"Video Download Error: {str(e)}")
            return None

# ================== BOT HANDLERS ==================
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🚀 Terabox Video Download Bot\n\n"
        "Send any Terabox link to get instant video download!\n"
        "Free limit: 4 downloads/day\n"
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

    # Admin notifications
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

    # URL validation
    parsed_url = urlparse(url)
    if any(domain in parsed_url.netloc for domain in TERABOX_DOMAINS):
        user_data = data["users"][str(user_id)]
        
        try:
            if user_data["downloads"] < 4 or user_data["coins"] > 0:
                await update.message.reply_text("⏳ Processing your request...")
                
                if user_data["downloads"] >= 4:
                    user_data["coins"] -= 1

                filename = TeraboxDownloader.download(url)
                if filename:
                    await update.message.reply_video(video=open(filename, 'rb'))
                    os.remove(filename)
                    user_data["downloads"] += 1
                    save_user_data(data)
                else:
                    await update.message.reply_text("❌ Failed to download video. Please try another link.")
            else:
                await update.message.reply_text(
                    "⚠️ Daily limit reached! Contact admin for more downloads\n"
                    f"Admin: @{context.bot.get_chat(ADMIN_IDS[0]).username}"
                )
        except Exception as e:
            print(f"Handler Error: {str(e)}")
            await update.message.reply_text("❌ Service temporary unavailable. Please try later.")
    else:
        await update.message.reply_text("❌ Invalid link! Only Terabox links are supported.")

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

    # Initialize user data
    if not os.path.exists(USER_DATA_FILE):
        save_user_data({"users": {}, "reply_map": {}})

    # Start bot
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()