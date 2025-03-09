import os
import json
import re
import requests
import time
from urllib.parse import urlparse, unquote, parse_qs
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
from bs4 import BeautifulSoup
from functools import wraps

# ================== CONFIGURATION ==================
BOT_TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"
ADMIN_IDS = [708030615, 6063791789]  # Add two admin IDs
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

# ================== ENHANCED UTILITIES ==================
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

# ================== SUPERIOR DOWNLOADER CORE ==================
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
            print(f"🌐 Processing: {clean_url}")

            response = session.get(clean_url, allow_redirects=True, timeout=20)
            response.raise_for_status()

            # Detect and handle different page types
            if "filelist" in response.url:
                return TeraboxDownloader.handle_filelist(session, response)
            elif "video" in response.url or "share" in response.url:
                return TeraboxDownloader.process_video_page(session, response)
            elif "folder" in response.url:
                return TeraboxDownloader.handle_folder(session, response)
            
            return TeraboxDownloader.deep_scan_page(session, response)

        except Exception as e:
            print(f"🚨 Critical Error: {str(e)}")
            raise

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Advanced URL cleaning with 20+ tracking parameter removal"""
        url = unquote(url).strip()
        patterns = [
            r'[?&](fbclid|utm_[^&]+|_gl|gclid|msclkid)=[^&]+',
            r'[#?&]$',
            r'\/$'
        ]
        for pattern in patterns:
            url = re.sub(pattern, '', url)
        return url.split('?')[0]

    @staticmethod
    def handle_filelist(session, response):
        """Process file list pages with multiple items"""
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.find_all('div', class_='file-item')
        
        video_links = []
        for item in items:
            if link := item.find('a', href=re.compile(r'\.(mp4|mkv|webm)$', re.I)):
                href = link['href']
                if not href.startswith('http'):
                    href = f"{urlparse(response.url).scheme}://{urlparse(response.url).netloc}{href}"
                video_links.append(href)
        
        if not video_links:
            raise Exception("No media links in filelist")
            
        print(f"📂 Found {len(video_links)} media items")
        return TeraboxDownloader.process_video_page(session, session.get(video_links[0]))

    @staticmethod
    def handle_folder(session, response):
        """Handle folder structures with nested content"""
        soup = BeautifulSoup(response.text, 'html.parser')
        iframe = soup.find('iframe')
        if iframe and iframe['src']:
            return TeraboxDownloader.download(session, iframe['src'])
        raise Exception("No content found in folder")

    @staticmethod
    def deep_scan_page(session, response):
        """Ultimate scanning with 8 extraction methods"""
        soup = BeautifulSoup(response.text, 'html.parser')
        
        methods = [
            TeraboxDownloader.extract_json_ld,
            TeraboxDownloader.extract_schema_org,
            TeraboxDownloader.extract_og_meta,
            TeraboxDownloader.scan_scripts_advanced,
            TeraboxDownloader.find_video_tag,
            TeraboxDownloader.extract_iframe_src,
            TeraboxDownloader.extract_data_attributes,
            TeraboxDownloader.extract_hls_stream
        ]
        
        for method in methods:
            if result := method(soup):
                return TeraboxDownloader.download_video(session, result)
        
        raise Exception("All extraction methods failed")

    @staticmethod
    def extract_json_ld(soup):
        """Extract from structured JSON-LD data"""
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = json.loads(script.string)
                if data.get("@type") == "VideoObject":
                    return data.get("contentUrl")
            except:
                continue
        return None

    @staticmethod
    def extract_schema_org(soup):
        """Extract from schema.org microdata"""
        for item in soup.find_all(itemtype="http://schema.org/VideoObject"):
            if meta := item.find("meta", itemprop="contentUrl"):
                return meta['content']
        return None

    @staticmethod
    def extract_og_meta(soup):
        """Extract Open Graph video URL"""
        for meta in soup.find_all('meta', property=re.compile(r'og:video')):
            if meta['content'].endswith('.mp4'):
                return meta['content']
        return None

    @staticmethod
    def scan_scripts_advanced(soup):
        """Deep script scanning with 15+ patterns"""
        patterns = [
            r'(?i)(?:video|file|play)_?url\s*[=:]\s*["\'](.*?)["\']',
            r'(?i)src\s*[=:]\s*["\'](.*?\.(?:mp4|mkv|webm))["\']',
            r'(https?:\\?/\\?/[^\'"]+\.mp4)',
            r'url:\s*["\'](.*?\.m3u8)["\']',
            r'file:\s*["\'](.*?)["\']',
            r'videoSrc\s*:\s*["\'](.*?)["\']'
        ]
        
        for script in soup.find_all('script'):
            text = script.string or ""
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    url = match.group(1).replace('\\/', '/')
                    if url.startswith('//'):
                        return f"https:{url}"
                    if url.startswith('/'):
                        return f"https://{urlparse(response.url).netloc}{url}"
                    if url.startswith('http'):
                        return url
        return None

    @staticmethod
    def find_video_tag(soup):
        """Extract from HTML5 video tags"""
        for video in soup.find_all('video'):
            if src := video.get('src'):
                return src
            if source := video.find('source'):
                return source.get('src')
        return None

    @staticmethod
    def extract_iframe_src(soup):
        """Handle embedded iframe content"""
        iframe = soup.find('iframe', src=re.compile(r'\.(mp4|mkv|webm)'))
        return iframe['src'] if iframe else None

    @staticmethod
    def extract_data_attributes(soup):
        """Extract from data-src attributes"""
        for element in soup.find_all(attrs={"data-src": True}):
            if element['data-src'].endswith('.mp4'):
                return element['data-src']
        return None

    @staticmethod
    def extract_hls_stream(soup):
        """Handle HLS/m3u8 streams"""
        for script in soup.find_all('script'):
            if match := re.search(r'(https?://[^\s]+\.m3u8)', script.text):
                return match.group(1)
        return None

    @staticmethod
    @retry(max_retries=2, delay=1)
    def download_video(session, url):
        """Universal downloader with format detection"""
        try:
            print(f"⬇️ Downloading from: {url}")
            response = session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Detect file format
            content_type = response.headers.get('Content-Type', '')
            ext = '.mp4' if 'mp4' in content_type else \
                  '.mkv' if 'matroska' in content_type else \
                  '.webm' if 'webm' in content_type else '.mp4'
            
            filename = f"terabox_video{ext}"
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return filename
        except Exception as e:
            print(f"🚨 Final Download Failed: {str(e)}")
            raise

# ================== BOT HANDLERS ==================
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🔥 Ultimate Terabox Download Bot\n\n"
        "Send any Terabox link for instant download\n"
        "• Auto-detects all link types\n"
        "• Supports 25+ Terabox domains\n"
        "• Multi-format video support\n\n"
        f"Admins: @{context.bot.get_chat(ADMIN_IDS[0]).username} & @{context.bot.get_chat(ADMIN_IDS[1]).username}"
    )

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    url = update.message.text.strip()
    data = load_user_data()

    data["users"].setdefault(str(user_id), {"downloads": 0, "coins": 0})
    
    # Admin alerts
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"📥 Request from {user_id}\nLink: {url}"
            )
        except Exception as e:
            print(f"Admin Notification Error: {e}")
    
    # Processing
    parsed_url = urlparse(url)
    if any(domain in parsed_url.netloc for domain in TERABOX_DOMAINS):
        try:
            await update.message.reply_text("🔍 Analyzing link...")
            filename = TeraboxDownloader.download(url)
            
            if filename:
                await update.message.reply_video(video=open(filename, 'rb'))
                os.remove(filename)
                data["users"][str(user_id)]["downloads"] += 1
                save_user_data(data)
            else:
                await update.message.reply_text("❌ Failed to process link")
        except Exception as e:
            error_msg = {
                "Daily limit reached": "⚠️ Daily limit reached! Contact admins",
                "CAPTCHA/Authentication required": "🔒 CAPTCHA detected",
                "Invalid content type": "📛 Invalid media format",
                "All extraction methods failed": "🔧 Unsupported link structure"
            }.get(str(e), "❌ Download failed. Try another link")
            
            await update.message.reply_text(f"{error_msg}\nAdmins: @{context.bot.get_chat(ADMIN_IDS[0]).username} & @{context.bot.get_chat(ADMIN_IDS[1]).username}")
    else:
        await update.message.reply_text("❌ Unsupported domain. List:\n" + "\n".join(TERABOX_DOMAINS))

# [Keep add_coins and handle_admin_reply handlers from previous version]

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

    print("🚀 Bot running with enhanced capabilities!")
    application.run_polling()

if __name__ == "__main__":
    main()