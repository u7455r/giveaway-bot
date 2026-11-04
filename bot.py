# ============================================================
# RAFIM GIVEAWAY BOT - FULL & FINAL SCRIPT
# Render Ready | Flask + Telegram Polling | SQLite
# Bengali / English | Force Join | Redeem | Giveaway
# Daily Giveaway | Status | Settings | Help
# Admin Panel | Broadcast | Direct User Chat
# ============================================================

import os
import sys
import time
import sqlite3
import threading
import secrets
import string
import traceback
from datetime import datetime, timezone

import telebot
from telebot import types
from flask import Flask

# ============================================================
# ENVIRONMENT / CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8886219226:AAE5modsPJsbGK17JneyphHvujsposX6fc0").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "8298133943").strip()

# Force Join চ্যানেলের ইউজারনেম (প্রয়োজনে পরিবর্তন করে নিবেন)
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL", "@rafimhossen3").strip()

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    ADMIN_ID = 8298133943

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ============================================================
# DATABASE SETUP
# ============================================================

DB_FILE = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    username TEXT,
                    lang TEXT DEFAULT 'bn',
                    points INTEGER DEFAULT 0,
                    joined_at TEXT
                )''')
    # Giveaways table
    c.execute('''CREATE TABLE IF NOT EXISTS giveaways (
                    giveaway_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    prize TEXT,
                    winners_count INTEGER,
                    status TEXT DEFAULT 'active',
                    created_at TEXT
                )''')
    # Giveaway entries
    c.execute('''CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giveaway_id INTEGER,
                    user_id INTEGER,
                    UNIQUE(giveaway_id, user_id)
                )''')
    # Redeem codes
    c.execute('''CREATE TABLE IF NOT EXISTS redeem_codes (
                    code TEXT PRIMARY KEY,
                    points INTEGER,
                    is_used INTEGER DEFAULT 0,
                    used_by INTEGER
                )''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect(DB_FILE)

# ============================================================
# LOCALIZATION & TEXTS
# ============================================================

TEXTS = {
    "bn": {
        "welcome": "👋 <b>স্বাগতম {name}!</b>\n\nআমাদের গিভঅ্যাওয়ে বটে আপনাকে স্বাগতম। নিচের বাটনগুলো ব্যবহার করে অংশ নিন বা ব্যালেন্স চেক করুন।",
        "force_join": "⚠️ বট ব্যবহার করতে হলে আপনাকে আমাদের চ্যানেলে জয়েন করতে হবে:\n👉 {channel}\n\nজয়েন করার পর <b>Joined ✅</b> বাটনে চাপ দিন।",
        "btn_giveaway": "🎁 লাইভ গিভঅ্যাওয়ে",
        "btn_redeem": "🎟 কোড রিডিম",
        "btn_status": "📊 আমার প্রোফাইল",
        "btn_help": "ℹ️ সাহায্য",
        "btn_lang": "🌐 Language / ভাষা",
        "admin_menu": "⚙️ <b>অ্যাডমিন কন্ট্রোল প্যানেল</b>\n\nনিচের অপশনগুলো সিলেক্ট করুন:",
        "joined_success": "✅ ধন্যবাদ! আপনার মেম্বারশিপ যাচাই সফল হয়েছে।",
        "not_joined": "❌ আপনি এখনো চ্যানেলে জয়েন করেননি! দয়া করে জয়েন করুন।",
        "no_active_giveaway": "❌ বর্তমানে কোনো সক্রিয় গিভঅ্যাওয়ে নেই!",
        "giveaway_joined": "🎉 আপনি সফলভাবে এই গিভঅ্যাওয়েতে অংশগ্রহণ করেছেন!",
        "already_joined": "⚠️ আপনি ইতিমধ্যে এই গিভঅ্যাওয়েতে অংশ নিয়েছেন!",
        "enter_redeem": "অনুগ্রহ করে আপনার রিডিম কোডটি পাঠান:",
        "redeem_success": "✅ অভিনন্দন! আপনি {points} পয়েন্ট অর্জন করেছেন।",
        "redeem_invalid": "❌ কোডটি ভুল অথবা ইতিমধ্যে ব্যবহার করা হয়েছে!",
        "profile": "👤 <b>আপনার প্রোফাইল:</b>\n\n🆔 ইউজার আইডি: <code>{id}</code>\n💎 পয়েন্ট: <b>{points}</b>\n🌐 ভাষা: <b>বাংলা</b>"
    },
    "en": {
        "welcome": "👋 <b>Welcome {name}!</b>\n\nWelcome to our giveaway bot. Use the menu buttons below to participate and check your balance.",
        "force_join": "⚠️ You must join our channel to use this bot:\n👉 {channel}\n\nAfter joining, click the <b>Joined ✅</b> button.",
        "btn_giveaway": "🎁 Active Giveaways",
        "btn_redeem": "🎟 Redeem Code",
        "btn_status": "📊 My Profile",
        "btn_help": "ℹ️ Help",
        "btn_lang": "🌐 Language / ভাষা",
        "admin_menu": "⚙️ <b>Admin Control Panel</b>\n\nSelect an operation below:",
        "joined_success": "✅ Thank you! Membership successfully verified.",
        "not_joined": "❌ You haven't joined the channel yet! Please join first.",
        "no_active_giveaway": "❌ There are no active giveaways right now!",
        "giveaway_joined": "🎉 You have successfully entered this giveaway!",
        "already_joined": "⚠️ You have already entered this giveaway!",
        "enter_redeem": "Please enter your redeem code:",
        "redeem_success": "✅ Success! You received {points} points.",
        "redeem_invalid": "❌ Invalid code or already redeemed!",
        "profile": "👤 <b>Your Profile:</b>\n\n🆔 User ID: <code>{id}</code>\n💎 Points: <b>{points}</b>\n🌐 Language: <b>English</b>"
    }
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def is_subscribed(user_id):
    if not FORCE_CHANNEL or FORCE_CHANNEL == "@":
        return True
    try:
        member = bot.get_chat_member(FORCE_CHANNEL, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception:
        return True

def get_user_lang(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "bn"

def main_keyboard(lang):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    t = TEXTS[lang]
    markup.add(
        types.KeyboardButton(t["btn_giveaway"]),
        types.KeyboardButton(t["btn_redeem"]),
        types.KeyboardButton(t["btn_status"]),
        types.KeyboardButton(t["btn_help"]),
        types.KeyboardButton(t["btn_lang"])
    )
    return markup

# ============================================================
# USER COMMAND HANDLERS
# ============================================================

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username or ""

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    if not res:
        c.execute("INSERT INTO users (user_id, first_name, username, joined_at) VALUES (?, ?, ?, ?)",
                  (user_id, first_name, username, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    conn.close()

    lang = get_user_lang(user_id)

    if not is_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        clean_channel = FORCE_CHANNEL.replace("@", "")
        markup.add(types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{clean_channel}"))
        markup.add(types.InlineKeyboardButton("Joined ✅", callback_data="check_subscription"))
        bot.send_message(user_id, TEXTS[lang]["force_join"].format(channel=FORCE_CHANNEL), reply_markup=markup)
        return

    bot.send_message(user_id, TEXTS[lang]["welcome"].format(name=first_name), reply_markup=main_keyboard(lang))

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_sub_callback(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    if is_subscribed(user_id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, TEXTS[lang]["joined_success"], reply_markup=main_keyboard(lang))
    else:
        bot.answer_callback_query(call.id, TEXTS[lang]["not_joined"], show_alert=True)

# ============================================================
# MESSAGE INTERACTION & KEYBOARD LOGIC
# ============================================================

@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text
    lang = get_user_lang(user_id)

    if not is_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        clean_channel = FORCE_CHANNEL.replace("@", "")
        markup.add(types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{clean_channel}"))
        markup.add(types.InlineKeyboardButton("Joined ✅", callback_data="check_subscription"))
        bot.send_message(user_id, TEXTS[lang]["force_join"].format(channel=FORCE_CHANNEL), reply_markup=markup)
        return

    # Language Switch
    if text == TEXTS[lang]["btn_lang"]:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("বাংলা 🇧🇩", callback_data="setlang_bn"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data="setlang_en")
        )
        bot.send_message(user_id, "Select your preferred language / ভাষা নির্বাচন করুন:", reply_markup=markup)
        return

    # Profile / Status
    elif text == TEXTS[lang]["btn_status"]:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        points = c.fetchone()[0]
        conn.close()
        bot.send_message(user_id, TEXTS[lang]["profile"].format(id=user_id, points=points))
        return

    # Help
    elif text == TEXTS[lang]["btn_help"]:
        help_text = "📞 Support: Contact @rafimhossen3 for any issues or queries." if lang == "en" else "📞 সহায়তার জন্য যোগাযোগ করুন: @rafimhossen3"
        bot.send_message(user_id, help_text)
        return

    # Active Giveaways
    elif text == TEXTS[lang]["btn_giveaway"]:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT giveaway_id, title, prize, winners_count FROM giveaways WHERE status = 'active' ORDER BY giveaway_id DESC LIMIT 1")
        gw = c.fetchone()
        conn.close()

        if not gw:
            bot.send_message(user_id, TEXTS[lang]["no_active_giveaway"])
            return

        gw_id, title, prize, winners = gw
        caption = f"🎁 <b>{title}</b>\n\n🏆 পুরস্কার: <b>{prize}</b>\n👥 বিজয়ী সংখ্যা: <b>{winners}</b>" if lang == "bn" else f"🎁 <b>{title}</b>\n\n🏆 Prize: <b>{prize}</b>\n👥 Winners: <b>{winners}</b>"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎉 Participate Now", callback_data=f"enter_gw_{gw_id}"))
        bot.send_message(user_id, caption, reply_markup=markup)
        return

    # Redeem Code
    elif text == TEXTS[lang]["btn_redeem"]:
        msg = bot.send_message(user_id, TEXTS[lang]["enter_redeem"])
        bot.register_next_step_handler(msg, process_redeem)
        return

def process_redeem(message):
    user_id = message.from_user.id
    code = message.text.strip()
    lang = get_user_lang(user_id)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT points, is_used FROM redeem_codes WHERE code = ?", (code,))
    row = c.fetchone()

    if row and row[1] == 0:
        points = row[0]
        c.execute("UPDATE redeem_codes SET is_used = 1, used_by = ? WHERE code = ?", (user_id, code))
        c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points, user_id))
        conn.commit()
        bot.send_message(user_id, TEXTS[lang]["redeem_success"].format(points=points))
    else:
        bot.send_message(user_id, TEXTS[lang]["redeem_invalid"])
    conn.close()

# ============================================================
# CALLBACK QUERY HANDLERS
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith("setlang_"))
def callback_set_lang(call):
    new_lang = call.data.split("_")[1]
    user_id = call.from_user.id

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_lang, user_id))
    conn.commit()
    conn.close()

    bot.delete_message(call.message.chat.id, call.message.message_id)
    confirm = "ভাষা পরিবর্তন সম্পন্ন হয়েছে!" if new_lang == "bn" else "Language updated successfully!"
    bot.send_message(user_id, confirm, reply_markup=main_keyboard(new_lang))

@bot.callback_query_handler(func=lambda call: call.data.startswith("enter_gw_"))
def callback_enter_gw(call):
    user_id = call.from_user.id
    gw_id = int(call.data.split("_")[2])
    lang = get_user_lang(user_id)

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO entries (giveaway_id, user_id) VALUES (?, ?)", (gw_id, user_id))
        conn.commit()
        bot.answer_callback_query(call.id, TEXTS[lang]["giveaway_joined"], show_alert=True)
    except sqlite3.IntegrityError:
        bot.answer_callback_query(call.id, TEXTS[lang]["already_joined"], show_alert=True)
    finally:
        conn.close()

# ============================================================
# ADMIN PANEL COMMANDS & ACTIONS
# ============================================================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Create Giveaway", callback_data="adm_new_gw"),
        types.InlineKeyboardButton("🎯 End & Pick Winner", callback_data="adm_end_gw"),
        types.InlineKeyboardButton("🎟 Make Redeem Code", callback_data="adm_make_code"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("📊 Bot Stats", callback_data="adm_stats")
    )
    bot.send_message(ADMIN_ID, "⚙️ <b>Admin Control Panel</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return

    action = call.data

    if action == "adm_stats":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM giveaways WHERE status = 'active'")
        active_gw = c.fetchone()[0]
        conn.close()

        bot.answer_callback_query(call.id)
        bot.send_message(ADMIN_ID, f"📊 <b>Bot Statistics</b>\n\n👥 Total Users: {total_users}\n🎁 Active Giveaways: {active_gw}")

    elif action == "adm_make_code":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(ADMIN_ID, "কত পয়েন্টের কোড তৈরি করতে চান? পয়েন্ট সংখ্যা লিখুন:")
        bot.register_next_step_handler(msg, process_make_code)

    elif action == "adm_new_gw":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(ADMIN_ID, "গিভঅ্যাওয়ের টাইটেল ও তথ্য পাঠান (Format: <code>Title | Prize | WinnersCount</code>):\n\nযেমন: <code>Telegram Premium | 1 Month Sub | 1</code>")
        bot.register_next_step_handler(msg, process_create_gw)

    elif action == "adm_end_gw":
        bot.answer_callback_query(call.id)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT giveaway_id, title, winners_count FROM giveaways WHERE status = 'active' ORDER BY giveaway_id DESC LIMIT 1")
        gw = c.fetchone()

        if not gw:
            bot.send_message(ADMIN_ID, "❌ কোনো সক্রিয় গিভঅ্যাওয়ে নেই সমাপ্ত করার জন্য।")
            conn.close()
            return

        gw_id, title, count = gw
        c.execute("SELECT user_id FROM entries WHERE giveaway_id = ?", (gw_id,))
        participants = [row[0] for row in c.fetchall()]

        if not participants:
            c.execute("UPDATE giveaways SET status = 'ended' WHERE giveaway_id = ?", (gw_id,))
            conn.commit()
            bot.send_message(ADMIN_ID, f"⚠️ গিভঅ্যাওয়ে সমাপ্ত হয়েছে তবে কোনো পার্টিসিপেন্ট ছিল না।")
            conn.close()
            return

        import random
        winners = random.sample(participants, min(len(participants), count))
        c.execute("UPDATE giveaways SET status = 'ended' WHERE giveaway_id = ?", (gw_id,))
        conn.commit()
        conn.close()

        winners_mention = "\n".join([f"🎉 <a href='tg://user?id={w}'>User {w}</a> (ID: <code>{w}</code>)" for w in winners])
        bot.send_message(ADMIN_ID, f"🏆 <b>Giveaway Ended: {title}</b>\n\n<b>Winners:</b>\n{winners_mention}")

    elif action == "adm_broadcast":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(ADMIN_ID, "সব ইউজারকে পাঠাতে চাওয়া ব্রডকাস্ট মেসেজটি লিখুন:")
        bot.register_next_step_handler(msg, process_broadcast)

def process_make_code(message):
    try:
        points = int(message.text.strip())
        code = "RAFIM-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO redeem_codes (code, points) VALUES (?, ?)", (code, points))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"✅ কোড জেনারেট হয়েছে!\n\n🎟 কোড: <code>{code}</code>\n💎 পয়েন্ট: {points}")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ পয়েন্ট সংখ্যা সঠিক নয়!")

def process_create_gw(message):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 3:
            bot.send_message(ADMIN_ID, "❌ ফরম্যাট সঠিক হয়নি! <code>Title | Prize | WinnersCount</code> এভাবে লিখুন।")
            return

        title, prize, count = parts[0], parts[1], int(parts[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO giveaways (title, prize, winners_count, created_at) VALUES (?, ?, ?, ?)",
                  (title, prize, count, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"✅ নতুন গিভঅ্যাওয়ে তৈরি হয়েছে!\n\n📌 টাইটেল: {title}\n🎁 পুরস্কার: {prize}\n👥 উইনার: {count}")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ ত্রুটি: {str(e)}")

def process_broadcast(message):
    broadcast_text = message.text
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()

    sent = 0
    bot.send_message(ADMIN_ID, f"⏳ ব্রডকাস্ট শুরু হচ্ছে... মোট ইউজার: {len(users)}")
    for u in users:
        try:
            bot.send_message(u[0], broadcast_text)
            sent += 1
            time.sleep(0.05)
        except Exception:
            pass

    bot.send_message(ADMIN_ID, f"✅ ব্রডকাস্ট সফল! মোট {sent} জনের কাছে মেসেজ পাঠানো হয়েছে।")

# ============================================================
# FLASK SERVER & BACKGROUND RUNNER (Render Ready)
# ============================================================

@app.route('/')
def home():
    return "RAFIM GIVEAWAY BOT is running perfectly 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    # Flask সার্ভারকে ব্যাকগ্রাউন্ড থ্রেডে চালু করা (Web Service সচল রাখার জন্য)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("🚀 Bot starting...")
    # Polling লুপ
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            traceback.print_exc()
            time.sleep(5)
