import os
import sqlite3
import threading
from flask import Flask
import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHANNEL_1 = os.getenv("CHANNEL_1", "@hacksmethod6")
CHANNEL_2 = os.getenv("CHANNEL_2", "@rafimhossen3")

DB_FILE = "premium_giveaway.db"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing.")

if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable is missing.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# =========================
# FLASK SERVER FOR RENDER
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "Giveaway Bot is running!", 200

@app.route("/health")
def health():
    return "OK", 200


def run_server():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


# =========================
# DATABASE
# =========================

def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            redeem_code TEXT UNIQUE NOT NULL,
            reward_text TEXT NOT NULL,
            category TEXT DEFAULT 'Daily',
            status TEXT DEFAULT 'Unused',
            used_by INTEGER,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_lang (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'bn'
        )
    """)

    conn.commit()
    conn.close()


# =========================
# LANGUAGE
# =========================

def get_user_lang(user_id):
    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT lang FROM user_lang WHERE user_id=?",
        (user_id,)
    )

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else "bn"


def set_user_lang(user_id, lang):
    conn = db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO user_lang(user_id, lang)
        VALUES (?, ?)
    """, (user_id, lang))

    conn.commit()
    conn.close()


# =========================
# FORCE JOIN
# =========================

def is_user_subscribed(user_id):
    try:
        member1 = bot.get_chat_member(CHANNEL_1, user_id)
        member2 = bot.get_chat_member(CHANNEL_2, user_id)

        valid_status = ["creator", "administrator", "member"]

        return (
            member1.status in valid_status and
            member2.status in valid_status
        )

    except Exception:
        return False


def force_join_markup():
    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton(
            "💬 Join Chat Channel",
            url=f"https://t.me/{CHANNEL_1.replace('@', '')}"
        )
    )

    markup.row(
        InlineKeyboardButton(
            "📢 Join Main Channel",
            url=f"https://t.me/{CHANNEL_2.replace('@', '')}"
        )
    )

    markup.row(
        InlineKeyboardButton(
            "🔄 Verify",
            callback_data="verify_join"
        )
    )

    return markup


def send_force_join(chat_id):
    text = (
        "🚨 *ACCESS REQUIRED*\n\n"
        "এই বট ব্যবহার করতে আগে আমাদের দুইটি চ্যানেলে Join করুন।\n\n"
        "✅ দুইটি চ্যানেলে Join করার পর নিচের Verify বাটনে চাপুন।"
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=force_join_markup()
    )


# =========================
# REPLY KEYBOARD
# =========================

def main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    keyboard.row(
        KeyboardButton("🔑 Redeem Code"),
        KeyboardButton("⚙️ Settings")
    )

    keyboard.row(
        KeyboardButton("🎁 Daily Giveaway"),
        KeyboardButton("📊 My Status")
    )

    return keyboard


# =========================
# ADMIN KEYBOARD
# =========================

def admin_keyboard():
    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton(
            "➕ Add Giveaway",
            callback_data="admin_add"
        )
    )

    markup.row(
        InlineKeyboardButton(
            "📋 Active Codes",
            callback_data="admin_list"
        )
    )

    markup.row(
        InlineKeyboardButton(
            "📊 Statistics",
            callback_data="admin_stats"
        )
    )

    return markup


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start_command(message):

    user_id = message.from_user.id

    if user_id == ADMIN_ID:

        bot.send_message(
            message.chat.id,
            "👑 *ADMIN PANEL*\n\n"
            "আপনার Giveaway Bot প্রস্তুত।\n\n"
            "নিচের menu থেকে কাজ নির্বাচন করুন।",
            reply_markup=admin_keyboard()
        )

        return

    if not is_user_subscribed(user_id):
        send_force_join(message.chat.id)
        return

    bot.send_message(
        message.chat.id,
        "🎁 *WELCOME TO GIVEAWAY BOT!*\n\n"
        "🔑 আপনার Redeem Code এখানে ব্যবহার করুন।\n"
        "🎁 Daily Giveaway দেখতে Daily Giveaway চাপুন।",
        reply_markup=main_keyboard()
    )


# =========================
# CALLBACK HANDLER
# =========================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):

    user_id = call.from_user.id

    # VERIFY JOIN
    if call.data == "verify_join":

        if is_user_subscribed(user_id):

            bot.answer_callback_query(
                call.id,
                "✅ Verification successful!"
            )

            bot.send_message(
                call.message.chat.id,
                "🎉 *Access Granted!*\n\n"
                "এখন আপনি bot ব্যবহার করতে পারবেন।",
                reply_markup=main_keyboard()
            )

        else:

            bot.answer_callback_query(
                call.id,
                "❌ আগে দুইটি channel join করুন।",
                show_alert=True
            )

        return

    # ADMIN ONLY
    if user_id != ADMIN_ID:

        bot.answer_callback_query(
            call.id,
            "❌ Admin access required!",
            show_alert=True
        )

        return

    # ADD GIVEAWAY
    if call.data == "admin_add":

        admin_states[user_id] = {
            "step": "waiting_code"
        }

        bot.send_message(
            call.message.chat.id,
            "➕ *ADD GIVEAWAY*\n\n"
            "প্রথমে একটি নতুন Redeem Code পাঠান।\n\n"
            "Example:\n"
            "`GIVE-2026-001`"
        )

        bot.answer_callback_query(call.id)

    # ACTIVE CODES
    elif call.data == "admin_list":

        conn = db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT redeem_code, category, status
            FROM giveaways
            WHERE status='Unused'
            ORDER BY id DESC
            LIMIT 30
        """)

        rows = cursor.fetchall()
        conn.close()

        if not rows:

            bot.send_message(
                call.message.chat.id,
                "📭 বর্তমানে কোনো unused code নেই।"
            )

        else:

            text = "📋 *ACTIVE GIVEAWAY CODES*\n\n"

            for code, category, status in rows:
                text += (
                    f"🔑 `{code}`\n"
                    f"📁 {category}\n"
                    f"🟢 {status}\n\n"
                )

            bot.send_message(
                call.message.chat.id,
                text
            )

        bot.answer_callback_query(call.id)

    # STATISTICS
    elif call.data == "admin_stats":

        conn = db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM giveaways"
        )
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM giveaways WHERE status='Unused'"
        )
        unused = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM giveaways WHERE status='Used'"
        )
        used = cursor.fetchone()[0]

        conn.close()

        text = (
            "📊 *GIVEAWAY STATISTICS*\n\n"
            f"📦 Total Codes: `{total}`\n"
            f"🟢 Unused: `{unused}`\n"
            f"🔴 Used: `{used}`"
        )

        bot.send_message(
            call.message.chat.id,
            text
        )

        bot.answer_callback_query(call.id)


# =========================
# ADMIN STATES
# =========================

admin_states = {}


# =========================
# ADMIN TEXT INPUT
# =========================

@bot.message_handler(
    func=lambda message:
    message.from_user.id == ADMIN_ID and
    message.from_user.id in admin_states
)
def admin_input(message):

    user_id = message.from_user.id
    state = admin_states.get(user_id)

    if not state:
        return

    # STEP 1: CODE
    if state["step"] == "waiting_code":

        code = message.text.strip().upper()

        conn = db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM giveaways WHERE redeem_code=?",
            (code,)
        )

        exists = cursor.fetchone()

        conn.close()

        if exists:

            bot.reply_to(
                message,
                "❌ এই code আগে থেকেই আছে। অন্য code পাঠান।"
            )

            return

        admin_states[user_id] = {
            "step": "waiting_reward",
            "code": code
        }

        bot.reply_to(
            message,
            "✅ Code saved!\n\n"
            "এখন এই code redeem করলে user কী reward পাবে সেটা লিখুন।\n\n"
            "Example:\n"
            "`Daily Giveaway Reward`"
        )

        return

    # STEP 2: REWARD
    if state["step"] == "waiting_reward":

        reward = message.text.strip()
        code = state["code"]

        conn = db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO giveaways
            (redeem_code, reward_text, category, status)
            VALUES (?, ?, ?, 'Unused')
        """, (
            code,
            reward,
            "Daily"
        ))

        conn.commit()
        conn.close()

        del admin_states[user_id]

        bot.reply_to(
            message,
            "🎉 *GIVEAWAY CREATED!*\n\n"
            f"🔑 Code: `{code}`\n"
            f"🎁 Reward: {reward}\n"
            "🟢 Status: Unused"
        )


# =========================
# REDEEM CODE
# =========================

@bot.message_handler(
    func=lambda message:
    message.text and
    message.text.strip().upper().startswith("GIVE-")
)
def redeem_code(message):

    user_id = message.from_user.id
    code = message.text.strip().upper()

    if not is_user_subscribed(user_id):

        send_force_join(message.chat.id)
        return

    conn = db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, reward_text, status
        FROM giveaways
        WHERE redeem_code=?
    """, (code,))

    row = cursor.fetchone()

    if not row:

        conn.close()

        bot.reply_to(
            message,
            "❌ *Invalid Code*\n\n"
            "এই Redeem Code পাওয়া যায়নি।"
        )

        return

    db_id, reward, status = row

    if status != "Unused":

        conn.close()

        bot.reply_to(
            message,
            "❌ *Code Already Used!*\n\n"
            "এই code ইতোমধ্যে redeem করা হয়েছে।"
        )

        return

    cursor.execute("""
        UPDATE giveaways
        SET status='Used',
            used_by=?,
            used_at=CURRENT_TIMESTAMP
        WHERE id=? AND status='Unused'
    """, (
        user_id,
        db_id
    ))

    conn.commit()

    if cursor.rowcount == 1:

        conn.close()

        bot.reply_to(
            message,
            "🎉 *REDEEM SUCCESSFUL!*\n\n"
            f"🎁 Reward:\n{reward}\n\n"
            "✅ এই code এখন আর ব্যবহার করা যাবে না।"
        )

    else:

        conn.close()

        bot.reply_to(
            message,
            "❌ এই code ইতোমধ্যে অন্য কেউ redeem করেছে।"
        )


# =========================
# REPLY BUTTONS
# =========================

@bot.message_handler(
    func=lambda message:
    message.text == "🔑 Redeem Code"
)
def redeem_help(message):

    bot.send_message(
        message.chat.id,
        "🔑 *REDEEM CODE*\n\n"
        "আপনার পাওয়া Giveaway Code সরাসরি এখানে পাঠান।\n\n"
        "Example:\n"
        "`GIVE-2026-001`"
    )


@bot.message_handler(
    func=lambda message:
    message.text == "🎁 Daily Giveaway"
)
def daily_giveaway(message):

    bot.send_message(
        message.chat.id,
        "🎁 *DAILY GIVEAWAY*\n\n"
        "আজকের Giveaway Code পেতে আমাদের channel-এর announcement দেখুন।"
    )


@bot.message_handler(
    func=lambda message:
    message.text == "📊 My Status"
)
def my_status(message):

    user_id = message.from_user.id

    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM giveaways WHERE used_by=?",
        (user_id,)
    )

    count = cursor.fetchone()[0]

    conn.close()

    bot.send_message(
        message.chat.id,
        f"📊 *YOUR STATUS*\n\n"
        f"🎁 Redeemed: `{count}`"
    )


@bot.message_handler(
    func=lambda message:
    message.text == "⚙️ Settings"
)
def settings(message):

    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton(
            "🇧🇩 বাংলা",
            callback_data="lang_bn"
        ),
        InlineKeyboardButton(
            "🇺🇸 English",
            callback_data="lang_en"
        )
    )

    bot.send_message(
        message.chat.id,
        "⚙️ *SETTINGS*\n\nভাষা নির্বাচন করুন:",
        reply_markup=markup
    )


# =========================
# LANGUAGE CALLBACK
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("lang_")
)
def language_callback(call):

    user_id = call.from_user.id
    lang = call.data.replace("lang_", "")

    set_user_lang(user_id, lang)

    if lang == "bn":

        bot.answer_callback_query(
            call.id,
            "🇧🇩 বাংলা সেট করা হয়েছে!"
        )

        bot.send_message(
            call.message.chat.id,
            "✅ ভাষা বাংলা করা হয়েছে।",
            reply_markup=main_keyboard()
        )

    else:

        bot.answer_callback_query(
            call.id,
            "🇺🇸 English selected!"
        )

        bot.send_message(
            call.message.chat.id,
            "✅ Language changed to English.",
            reply_markup=main_keyboard()
        )


# =========================
# START BOT
# =========================

init_db()

server_thread = threading.Thread(
    target=run_server,
    daemon=True
)

server_thread.start()

bot.infinity_polling(
    skip_pending=True,
    timeout=30,
    long_polling_timeout=30
    )
