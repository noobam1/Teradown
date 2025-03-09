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
    "tb1.terabox.com", "tb2.terabox.com", "tb3.terabox.com",  # New domains
    "terabox.download", "teraboxapi.com", "terabox-cdn.net"
]

# ================== ERROR CLASSES ==================
class CaptchaError(Exception):
    pass

class InvalidURLError(Exception):
    pass

# ================== ENHANCED DOWNLOADER ==================
class TeraboxDownloader:
    @staticmethod
    @retry(max_retries=3, delay=5)  # Increased delay between retries
    def download(url: str) -> str:
        try:
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(max_retries=3)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://www.terabox.com/",
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1"
            })

            clean_url = TeraboxDownloader.sanitize_url(url)
            logger.info(f"Processing: {clean_url}")

            response = session.get(clean_url, allow_redirects=True, timeout=30)
            
            # Enhanced CAPTCHA detection
            if any(keyword in response.text.lower() for keyword in ["captcha", "verify", "security check"]):
                raise CaptchaError("CAPTCHA verification required")

            if response.status_code != 200:
                raise requests.HTTPError(f"HTTP Error {response.status_code}")

            # Domain validation check
            parsed_url = urlparse(response.url)
            if not any(domain in parsed_url.netloc for domain in TERABOX_DOMAINS):
                raise InvalidURLError("Invalid Terabox domain")

            # Content type handling
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                if "filelist" in response.url:
                    return TeraboxDownloader.handle_filelist(session, response)
                return TeraboxDownloader.process_video_page(session, response)
            elif 'video/' in content_type:
                return TeraboxDownloader.download_video(session, response.url)
            else:
                raise ValueError("Unsupported content type")

        except Exception as e:
            logger.error(f"Download Error: {str(e)}")
            raise

    @staticmethod
    def sanitize_url(url: str) -> str:
        url = unquote(url).strip()
        url = re.sub(r'[?&](fbclid|utm_[^&]+|ns=|nltest)=[^&]+', '', url)
        url = re.sub(r'\/share\/link\?', '/share/link?', url, flags=re.IGNORECASE)
        return url.split('#')[0]

    @staticmethod
    def process_video_page(session, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # New extraction methods
        extraction_methods = [
            TeraboxDownloader.extract_json_ld,
            TeraboxDownloader.extract_iframe_src,
            TeraboxDownloader.extract_m3u8_playlist,
            TeraboxDownloader.extract_new_json_pattern,
            TeraboxDownloader.extract_og_meta,
            TeraboxDownloader.scan_scripts_enhanced,
            TeraboxDownloader.find_video_tag
        ]
        
        for method in extraction_methods:
            if video_url := method(soup):
                logger.info(f"Found video via {method.__name__}: {video_url}")
                return TeraboxDownloader.download_video(session, video_url)
        
        raise ValueError("No video source found")

    @staticmethod
    def extract_json_ld(soup):
        """New: Extract from JSON-LD structured data"""
        script = soup.find('script', type='application/ld+json')
        if script:
            try:
                data = json.loads(script.string)
                return data.get('contentUrl')
            except:
                return None

    @staticmethod
    def extract_iframe_src(soup):
        """New: Handle iframe embeds"""
        iframe = soup.find('iframe', {'allowfullscreen': 'true'})
        return iframe['src'] if iframe else None

    @staticmethod
    def extract_m3u8_playlist(soup):
        """New: Handle HLS streams"""
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'm3u8' in script.string:
                match = re.search(r'(https?://[^\s]+\.m3u8)', script.string)
                return match.group(1) if match else None

    @staticmethod
    def download_video(session, video_url):
        try:
            # Handle different URL patterns
            if 'm3u8' in video_url:
                raise ValueError("HLS streams not supported")
                
            response = session.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            
            filename = unquote(urlparse(video_url).path.split('/')[-1])
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
            return temp_path
        except Exception as e:
            logger.error(f"Download Failed: {str(e)}")
            raise

# ================== ENHANCED ERROR HANDLING ==================
async def handle_message(update: Update, context: CallbackContext):
    try:
        # ... (previous user checks remain same) ...
        
        file_path = TeraboxDownloader.download(url)
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ Download Successful!",
                    supports_streaming=True,
                    read_timeout=60,
                    write_timeout=60
                )
            os.remove(file_path)
            # Update user data...

    except CaptchaError:
        await update.message.reply_text(
            "⚠️ CAPTCHA Detected!\n"
            "1. Open link in browser\n"
            "2. Solve CAPTCHA\n"
            "3. Resend verified link"
        )
    except InvalidURLError:
        await update.message.reply_text(
            "❌ Invalid Terabox Link\n"
            f"Supported Domains:\n{', '.join(TERABOX_DOMAINS[:5])}..."
        )
    except requests.HTTPError as e:
        await update.message.reply_text(f"🚨 Server Error: {str(e)}")
    except Exception as e:
        logger.error(f"Unhandled Error: {str(e)}", exc_info=True)
        await update.message.reply_text("🔧 Temporary Error - Please try again later")

# ================== NEW FEATURES ==================
async def info(update: Update, context: CallbackContext):
    """User info command"""
    user_id = update.message.from_user.id
    data = load_user_data()
    user = data["users"].get(str(user_id), {})
    
    msg = (
        f"📊 Your Stats:\n"
        f"🆓 Free Downloads Left: {MAX_FREE_DOWNLOADS - get_today_downloads(user_id)}\n"
        f"💎 Coins: {user.get('coins',0)}\n"
        f"🌐 Supported Domains: {len(TERABOX_DOMAINS)}"
    )
    await update.message.reply_text(msg)

# Update start command
async def start(update: Update, context: CallbackContext):
    text = (
        "🚀 Terabox Video Download Bot\n\n"
        f"• Daily Free: {MAX_FREE_DOWNLOADS} Videos\n"
        "• Use /info to check your status\n"
        "• Supported Domains:\n"
        f"{', '.join(TERABOX_DOMAINS[:8])}..."
    )
    await update.message.reply_text(text)

# ================== MAIN APPLICATION ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    handlers = [
        CommandHandler("start", start),
        CommandHandler("info", info),
        CommandHandler("addcoins", add_coins),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY, handle_admin_reply)
    ]
    
    application.add_handlers(handlers)
    application.run_polling()

if __name__ == "__main__":
    main()