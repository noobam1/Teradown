import os
import json
import requests
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
from bs4 import BeautifulSoup

# ------------------ ग्लोबल वेरिएबल्स ------------------
TOKEN = "7461025500:AAEAQL3W2enqzT23qDrw-OirqQAux9c5w7E"  # BotFather से टोकन डालें
ADMINS = [708030615, 6063791789]  # दोनों Admin के User ID डालें
USER_DATA_FILE = "user_data.json"

# ------------------ डेटा मैनेजमेंट ------------------
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}, "reply_map": {}}

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ------------------ टेरेबॉक्स डाउनलोड ------------------
def download_terabox(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        script_tag = soup.find('script', text=lambda t: 'video_url' in str(t))
        if not script_tag:
            return None
        
        script_text = script_tag.string
        video_url = script_text.split('video_url":"')[1].split('"')[0].replace('\\', '')
        
        filename = "terabox_video.mp4"
        with requests.get(video_url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return filename
    except Exception as e:
        print(f"Download Error: {e}")
        return None

# ------------------ बॉट कमांड्स ------------------
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("📤 कृपया अपना Terabox लिंक भेजें!")

async def add_coins(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("⚠️ आप एडमिन नहीं हैं!")
        return

    try:
        target_user = int(context.args[0])
        coins = int(context.args[1])
        data = load_user_data()
        if str(target_user) not in data["users"]:
            data["users"][str(target_user)] = {"downloads": 0, "coins": 0}
        data["users"][str(target_user)]["coins"] += coins
        save_user_data(data)
        await update.message.reply_text(f"✅ {coins} कॉइन यूजर {target_user} को दिए गए!")
    except:
        await update.message.reply_text("⚠️ यूज़: /addcoins <user_id> <coins>")

# ------------------ यूजर मैसेज हैंडलर ------------------
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    url = update.message.text
    data = load_user_data()

    # नया यूजर रजिस्टर करें
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {"downloads": 0, "coins": 0}
        save_user_data(data)

    # एडमिन को मैसेज फॉरवर्ड करें
    for admin_id in ADMINS:
        try:
            sent_msg = await context.bot.send_message(
                admin_id,
                f"📩 यूजर {user_id} ने भेजा:\n\n{url}"
            )
            data["reply_map"][f"{admin_id}_{sent_msg.message_id}"] = user_id
        except Exception as e:
            print(f"Admin {admin_id} को मैसेज नहीं भेजा जा सका: {e}")
    save_user_data(data)

    # डाउनलोड प्रोसेस
    if "terabox.com" in url:
        user_data = data["users"][str(user_id)]
        
        if user_data["downloads"] < 4:
            await update.message.reply_text("⚡ डाउनलोड शुरू हो रहा है...")
            filename = download_terabox(url)
            if filename:
                with open(filename, 'rb') as f:
                    await update.message.reply_video(video=f)
                os.remove(filename)
                user_data["downloads"] += 1
                save_user_data(data)
            else:
                await update.message.reply_text("❌ डाउनलोड विफल! लिंक चेक करें।")
        else:
            if user_data["coins"] > 0:
                user_data["coins"] -= 1
                save_user_data(data)
                filename = download_terabox(url)
                if filename:
                    with open(filename, 'rb') as f:
                        await update.message.reply_video(video=f)
                    os.remove(filename)
                else:
                    await update.message.reply_text("❌ डाउनलोड विफल! लिंक चेक करें।")
            else:
                await update.message.reply_text(
                    f"⚠️ कॉइन खत्म! एडमिन से संपर्क करें: @{ADMINS}"
                )
    else:
        await update.message.reply_text("❌ गलत लिंक! सिर्फ Terabox लिंक चलेंगे।")

# ------------------ एडमिन रिप्लाई हैंडलर ------------------
async def handle_admin_reply(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMINS:
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
            f"📬 एडमिन का जवाब:\n\n{update.message.text}"
        )
        del data["reply_map"][key]
        save_user_data(data)

# ------------------ मेन फंक्शन ------------------
def main():
    application = Application.builder().token(TOKEN).build()
    
    # हैंडलर्स रजिस्टर करें
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addcoins", add_coins))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.REPLY, handle_admin_reply))
    
    application.run_polling()

if __name__ == "__main__":
    if not os.path.exists(USER_DATA_FILE):
        save_user_data({"users": {}, "reply_map": {}})
    main()