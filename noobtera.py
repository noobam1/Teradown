import os
import json
import requests
from telegram import Update, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters  # यहाँ 'filters' इस्तेमाल करें
from bs4 import BeautifulSoup

TOKEN = "YOUR_BOT_TOKEN"
ADMINS = [123456789]

# ... (बाकी कोड अपडेट नहीं हुआ है)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addcoins", add_coins))
    
    # अपडेटेड MessageHandler (filters का नया सिंटैक्स)
    dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    dp.add_handler(MessageHandler(filters.REPLY, handle_admin_reply))

    updater.start_polling()
    updater.idle()

# ------------------ डेटा मैनेजमेंट ------------------
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}, "reply_map": {}}

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, data, indent=4)

# ------------------ टेरेबॉक्स डाउनलोड (फिक्स्ड लॉजिक) ------------------
def download_terabox(url: str) -> str:
    try:
        # स्टेप 1: टेरेबॉक्स पेज पार्स करें
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # स्टेप 2: वीडियो URL निकालें (नया फिक्स्ड लॉजिक)
        script_tag = soup.find('script', text=lambda t: 'video_url' in str(t))
        if not script_tag:
            return None
        
        # JSON डेटा एक्सट्रेक्ट करें
        script_text = script_tag.string
        video_url = script_text.split('video_url":"')[1].split('"')[0].replace('\\', '')
        
        # स्टेप 3: वीडियो डाउनलोड करें
        filename = "video.mp4"
        with requests.get(video_url, stream=True) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return filename
    except Exception as e:
        print(f"Download Error: {e}")
        return None

# ------------------ बॉट कमांड्स ------------------
def start(update: Update, context: CallbackContext):
    update.message.reply_text("📤 कृपया अपना Terabox लिंक भेजें!")

def add_coins(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in ADMINS:
        return

    try:
        target_user = int(context.args[0])
        coins = int(context.args[1])
        data = load_user_data()
        if str(target_user) not in data["users"]:
            data["users"][str(target_user)] = {"downloads": 0, "coins": 0}
        data["users"][str(target_user)]["coins"] += coins
        save_user_data(data)
        update.message.reply_text(f"✅ {coins} कॉइन यूजर {target_user} को दिए गए!")
    except:
        update.message.reply_text("⚠️ यूज़: /addcoins <user_id> <coins>")

# ------------------ मैसेज हैंडलिंग ------------------
def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    url = update.message.text
    data = load_user_data()

    # नया यूजर रजिस्टर करें
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {"downloads": 0, "coins": 0}
        save_user_data(data)

    # एडमिन को मैसेज फॉरवर्ड करें
    for admin_id in ADMINS:
        context.bot.send_message(
            admin_id,
            f"📩 यूजर {user_id} ने भेजा:\n\n{url}"
        )

    # डाउनलोड प्रोसेस
    if "terabox.com" in url:
        user_data = data["users"][str(user_id)]
        
        # फ्री डाउनलोड (पहले 4)
        if user_data["downloads"] < 4:
            update.message.reply_text("⚡ डाउनलोड शुरू हो रहा है...")
            filename = download_terabox(url)
            if filename:
                with open(filename, 'rb') as f:
                    update.message.reply_video(video=f)
                os.remove(filename)
                user_data["downloads"] += 1
                save_user_data(data)
            else:
                update.message.reply_text("❌ डाउनलोड विफल! लिंक चेक करें।")
        
        # कॉइन सिस्टम (4 के बाद)
        else:
            if user_data["coins"] > 0:
                user_data["coins"] -= 1  # 1 कॉइन कटेगा
                save_user_data(data)
                filename = download_terabox(url)
                if filename:
                    with open(filename, 'rb') as f:
                        update.message.reply_video(video=f)
                    os.remove(filename)
                else:
                    update.message.reply_text("❌ डाउनलोड विफल! लिंक चेक करें।")
            else:
                update.message.reply_text(
                    "⚠️ कॉइन खत्म! एडमिन से संपर्क करें।\n"
                    f"Admin ID: @{context.bot.get_chat(ADMINS[0]).username}"
                )
    else:
        update.message.reply_text("❌ गलत लिंक! सिर्फ Terabox लिंक चलेंगे।")

# ------------------ एडमिन रिप्लाई ------------------
def handle_admin_reply(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMINS:
        return

    replied_msg = update.message.reply_to_message
    if replied_msg:
        admin_text = update.message.text
        user_id = replied_msg.text.split("यूजर ")[1].split(" ने")[0]
        context.bot.send_message(user_id, f"📬 एडमिन का जवाब:\n\n{admin_text}")

# ------------------ मेन फंक्शन ------------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addcoins", add_coins))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.reply, handle_admin_reply))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    # पहली बार रन करने पर user_data.json बनाएँ
    if not os.path.exists(USER_DATA_FILE):
        save_user_data({"users": {}, "reply_map": {}})
    main()