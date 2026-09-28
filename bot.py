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

# PUBLIC CHANNEL
CHANNEL_1 = os.getenv("CHANNEL_1", "@hacksmethod6")

# PUBLIC GROUP
GROUP_1 = os.getenv("GROUP_1", "@rafimhossen3")

DB_FILE = "premium_giveaway.db"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing.")

if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable is missing.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# =========================
# FLASK
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            alert_sent INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# =========================
# USER DATABASE
# =========================

def save_user(user):

    conn = db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        user.last_name or ""
    ))

    cursor.execute("""
        UPDATE users
        SET username=?,
            first_name=?,
            last_name=?
        WHERE user_id=?
    """, (
        user.username or "",
        user.first_name or "",
        user.last_name or "",
        user.id
    ))

    conn.commit()
    conn.close()


def alert_already_sent(user_id):

    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT alert_sent FROM users WHERE user_id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    conn.close()

    return bool(result and result[0] == 1)


def mark_alert_sent(user_id):

    conn = db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET alert_sent=1
        WHERE user_id=?
    """, (user_id,))

    conn.commit()
    conn.close()


# =========================
# NEW USER ADMIN ALERT
# =========================

def send_new_user_alert(user):

    if user.id == ADMIN_ID:
        return

    if alert_already_sent(user.id):
        return

    username = (
        f"@{user.username}"
        if user.username
        else "❌ No Username"
    )

    full_name = user.first_name or ""

    if user.last_name:
        full_name += f" {user.last_name}"

    text = (
        "🚨 *NEW USER STARTED BOT!*\n\n"
        f"👤 Name: `{full_name}`\n"
        f"🔗 Username: `{username}`\n"
        f"🆔 User ID: `{user.id}`\n\n"
        "📢 Channel: ✅ Joined\n"
        "👥 Group: ✅ Joined\n\n"
        "🎉 New user successfully registered!"
    )

    try:

        bot.send_message(
            ADMIN_ID,
            text
        )

        mark_alert_sent(user.id)

    except Exception:
        pass


# =========================
# LANGUAGE SYSTEM
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

    if result:
        return result[0]

    return "bn"


def set_user_lang(user_id, lang):

    if lang not in ["bn", "en"]:
        lang = "bn"

    conn = db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO user_lang(user_id, lang)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET lang=excluded.lang
    """, (
        user_id,
        lang
    ))

    conn.commit()
    conn.close()


# =========================
# LANGUAGE TEXT
# =========================

TEXT = {

    "bn": {

        "settings": "⚙️ *SETTINGS*\n\n🌐 আপনার ভাষা নির্বাচন করুন:",

        "lang_changed":
        "✅ ভাষা সফলভাবে বাংলা করা হয়েছে।",

        "welcome":
        "🎁 *WELCOME TO GIVEAWAY BOT!*\n\n"
        "🔑 আপনার Redeem Code এখানে ব্যবহার করুন।\n"
        "🎁 Daily Giveaway দেখতে Daily Giveaway চাপুন।",

        "redeem_button": "🔑 Redeem Code",
        "settings_button": "⚙️ Settings",
        "daily_button": "🎁 Daily Giveaway",
        "status_button": "📊 My Status",

        "access":
        "🚨 *ACCESS REQUIRED*\n\n"
        "এই বট ব্যবহার করতে আগে আমাদের Channel এবং Group-এ Join করুন।\n\n"
        "📢 Channel-এ Join করুন\n"
        "👥 Group-এ Join করুন\n\n"
        "✅ দুই জায়গায় Join করার পর নিচের Verify বাটনে চাপুন।",

        "verify_success":
        "🎉 *Access Granted!*\n\n"
        "এখন আপনি bot ব্যবহার করতে পারবেন।",

        "verify_failed":
        "❌ আগে Channel এবং Group-এ Join করুন।"
    },

    "en": {

        "settings":
        "⚙️ *SETTINGS*\n\n🌐 Select your language:",

        "lang_changed":
        "✅ Language successfully changed to English.",

        "welcome":
        "🎁 *WELCOME TO GIVEAWAY BOT!*\n\n"
        "🔑 Send your Redeem Code here.\n"
        "🎁 Press Daily Giveaway to view giveaway information.",

        "redeem_button": "🔑 Redeem Code",
        "settings_button": "⚙️ Settings",
        "daily_button": "🎁 Daily Giveaway",
        "status_button": "📊 My Status",

        "access":
        "🚨 *ACCESS REQUIRED*\n\n"
        "Please join our Channel and Group before using the bot.\n\n"
        "📢 Join the Channel\n"
        "👥 Join the Group\n\n"
        "✅ After joining both, press Verify.",

        "verify_success":
        "🎉 *Access Granted!*\n\n"
        "You can now use the bot.",

        "verify_failed":
        "❌ Please join the Channel and Group first."
    }
}


# =========================
# MAIN KEYBOARD
# =========================

def main_keyboard(user_id=None):

    lang = get_user_lang(user_id) if user_id else "bn"

    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    keyboard.row(
        KeyboardButton(TEXT[lang]["redeem_button"]),
        KeyboardButton(TEXT[lang]["settings_button"])
    )

    keyboard.row(
        KeyboardButton(TEXT[lang]["daily_button"]),
        KeyboardButton(TEXT[lang]["status_button"])
    )

    return keyboard


# =========================
# FORCE JOIN
# =========================

def get_member_status(chat_id, user_id):

    try:

        member = bot.get_chat_member(
            chat_id,
            user_id
        )

        return member.status

    except Exception:

        return None


def is_valid_member(status):

    return status in [
        "creator",
        "administrator",
        "member"
    ]


def is_user_subscribed(user_id):

    channel_status = get_member_status(
        CHANNEL_1,
        user_id
    )

    group_status = get_member_status(
        GROUP_1,
        user_id
    )

    return (
        is_valid_member(channel_status)
        and
        is_valid_member(group_status)
    )


def force_join_markup():

    markup = InlineKeyboardMarkup()

    channel_username = CHANNEL_1.replace("@", "").strip()
    group_username = GROUP_1.replace("@", "").strip()

    markup.row(
        InlineKeyboardButton(
            "📢 Join Channel",
            url=f"https://t.me/{channel_username}"
        )
    )

    markup.row(
        InlineKeyboardButton(
            "👥 Join Group",
            url=f"https://t.me/{group_username}"
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

    user_id = chat_id

    lang = get_user_lang(user_id)

    text = TEXT[lang]["access"]

    bot.send_message(
        chat_id,
        text,
        reply_markup=force_join_markup()
    )


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

    markup.row(
        InlineKeyboardButton(
            "📢 Broadcast",
            callback_data="admin_broadcast"
        )
    )

    markup.row(
        InlineKeyboardButton(
            "💬 Direct User Chat",
            callback_data="admin_direct_chat"
        )
    )

    return markup


# =========================
# ADMIN STATES
# =========================

admin_states = {}

active_direct_chat = {}

broadcast_running = False


def broadcast_markup():

    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton(
            "🛑 Cancel Broadcast",
            callback_data="broadcast_cancel"
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

    save_user(message.from_user)

    send_new_user_alert(message.from_user)

    lang = get_user_lang(user_id)

    bot.send_message(
        message.chat.id,
        TEXT[lang]["welcome"],
        reply_markup=main_keyboard(user_id)
    )


# =========================
# CALLBACK HANDLER
# =========================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):

    global broadcast_running

    user_id = call.from_user.id

    # =========================
    # VERIFY
    # =========================

    if call.data == "verify_join":

        if is_user_subscribed(user_id):

            if user_id != ADMIN_ID:

                save_user(call.from_user)

                send_new_user_alert(
                    call.from_user
                )

            lang = get_user_lang(user_id)

            bot.answer_callback_query(
                call.id,
                "✅ Verification successful!"
            )

            bot.send_message(
                call.message.chat.id,
                TEXT[lang]["verify_success"],
                reply_markup=main_keyboard(user_id)
            )

        else:

            lang = get_user_lang(user_id)

            bot.answer_callback_query(
                call.id,
                TEXT[lang]["verify_failed"],
                show_alert=True
            )

        return

    # =========================
    # LANGUAGE
    # =========================

    if call.data.startswith("lang_"):

        lang = call.data.replace(
            "lang_",
            ""
        )

        if lang not in ["bn", "en"]:
            lang = "bn"

        set_user_lang(
            user_id,
            lang
        )

        if lang == "bn":

            bot.answer_callback_query(
                call.id,
                "🇧🇩 বাংলা সেট করা হয়েছে!"
            )

        else:

            bot.answer_callback_query(
                call.id,
                "🇺🇸 English selected!"
            )

        bot.send_message(
            call.message.chat.id,
            TEXT[lang]["lang_changed"],
            reply_markup=main_keyboard(user_id)
        )

        return

    # =========================
    # ADMIN ONLY
    # =========================

    if user_id != ADMIN_ID:

        bot.answer_callback_query(
            call.id,
            "❌ Admin access required!",
            show_alert=True
        )

        return

    # =========================
    # ADD GIVEAWAY
    # =========================

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

    # =========================
    # ACTIVE CODES
    # =========================

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

    # =========================
    # STATISTICS
    # =========================

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

        cursor.execute(
            "SELECT COUNT(*) FROM users"
        )

        users = cursor.fetchone()[0]

        conn.close()

        text = (
            "📊 *GIVEAWAY STATISTICS*\n\n"
            f"📦 Total Codes: `{total}`\n"
            f"🟢 Unused: `{unused}`\n"
            f"🔴 Used: `{used}`\n\n"
            f"👥 Registered Users: `{users}`"
        )

        bot.send_message(
            call.message.chat.id,
            text
        )

        bot.answer_callback_query(call.id)

    # =========================
    # BROADCAST
    # =========================

    elif call.data == "admin_broadcast":

        admin_states[user_id] = {
            "step": "waiting_broadcast"
        }

        bot.send_message(
            call.message.chat.id,
            "📢 *BROADCAST SYSTEM*\n\n"
            "যে মেসেজটি সকল registered user-কে পাঠাতে চান সেটি এখন পাঠান।\n\n"
            "⚠️ Broadcast শুরু হওয়ার পর Cancel করা যাবে।"
        )

        bot.answer_callback_query(call.id)

    # =========================
    # DIRECT CHAT
    # =========================

    elif call.data == "admin_direct_chat":

        admin_states[user_id] = {
            "step": "waiting_user_id"
        }

        bot.send_message(
            call.message.chat.id,
            "💬 *DIRECT USER CHAT*\n\n"
            "যে User-এর সাথে কথা বলতে চান তার Telegram User ID পাঠান।\n\n"
            "Example:\n"
            "`123456789`"
        )

        bot.answer_callback_query(call.id)

    # =========================
    # BROADCAST CANCEL
    # =========================

    elif call.data == "broadcast_cancel":

        broadcast_running = False

        admin_states.pop(
            ADMIN_ID,
            None
        )

        bot.answer_callback_query(
            call.id,
            "🛑 Broadcast cancelled!"
        )

        bot.send_message(
            call.message.chat.id,
            "🛑 *BROADCAST CANCELLED*\n\n"
            "Broadcast বন্ধ করা হয়েছে।",
            reply_markup=admin_keyboard()
        )


# =========================
# ADMIN TEXT INPUT
# =========================

@bot.message_handler(
    func=lambda message:
    message.from_user.id == ADMIN_ID
    and message.from_user.id in admin_states
)
def admin_input(message):

    global broadcast_running

    user_id = message.from_user.id
    state = admin_states.get(user_id)

    if not state:
        return

    # =========================
    # ADD CODE
    # =========================

    if state["step"] == "waiting_code":

        if not message.text:
            return

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

    # =========================
    # REWARD
    # =========================

    if state["step"] == "waiting_reward":

        if not message.text:
            return

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

        admin_states.pop(
            user_id,
            None
        )

        bot.reply_to(
            message,
            "🎉 *GIVEAWAY CREATED!*\n\n"
            f"🔑 Code: `{code}`\n"
            f"🎁 Reward: {reward}\n"
            "🟢 Status: Unused"
        )

        return

    # =========================
    # USER ID
    # =========================

    if state["step"] == "waiting_user_id":

        if not message.text:
            return

        try:

            target_user_id = int(
                message.text.strip()
            )

        except Exception:

            bot.reply_to(
                message,
                "❌ সঠিক User ID দিন।\n\n"
                "Example:\n"
                "`123456789`"
            )

            return

        conn = db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, username, first_name
            FROM users
            WHERE user_id=?
            """,
            (target_user_id,)
        )

        target = cursor.fetchone()

        conn.close()

        if not target:

            bot.reply_to(
                message,
                "❌ এই User ID আমাদের registered user list-এ পাওয়া যায়নি।"
            )

            return

        active_direct_chat[ADMIN_ID] = target_user_id

        admin_states[user_id] = {
            "step": "direct_chat",
            "target_user_id": target_user_id
        }

        username = (
            f"@{target[1]}"
            if target[1]
            else "No Username"
        )

        bot.send_message(
            message.chat.id,
            "💬 *DIRECT CHAT ACTIVATED*\n\n"
            f"👤 Name: `{target[2] or 'Unknown'}`\n"
            f"🔗 Username: `{username}`\n"
            f"🆔 User ID: `{target_user_id}`\n\n"
            "✉️ এখন আপনার মেসেজ লিখুন।\n\n"
            "🛑 Chat বন্ধ করতে `/endchat` লিখুন।"
        )

        return

    # =========================
    # DIRECT CHAT
    # =========================

    if state["step"] == "direct_chat":

        target_user_id = state["target_user_id"]

        if (
            message.text
            and
            message.text.strip() == "/endchat"
        ):

            active_direct_chat.pop(
                ADMIN_ID,
                None
            )

            admin_states.pop(
                ADMIN_ID,
                None
            )

            bot.send_message(
                message.chat.id,
                "🛑 *DIRECT CHAT ENDED*",
                reply_markup=admin_keyboard()
            )

            return

        if not message.text:
            bot.reply_to(
                message,
                "❌ আপাতত শুধু text message পাঠানো যাবে।"
            )

            return

        try:

            bot.send_message(
                target_user_id,
                "💬 *ADMIN MESSAGE*\n\n"
                f"{message.text}"
            )

            bot.reply_to(
                message,
                "✅ Message sent to user."
            )

        except Exception:

            bot.reply_to(
                message,
                "❌ User-এর কাছে message পাঠানো যায়নি।"
            )

        return

    # =========================
    # BROADCAST
    # =========================

    if state["step"] == "waiting_broadcast":

        if not message.text:
            bot.reply_to(
                message,
                "❌ আপাতত শুধু text broadcast করা যাবে।"
            )
            return

        broadcast_text = message.text.strip()

        if not broadcast_text:
            bot.reply_to(
                message,
                "❌ Empty message পাঠানো যাবে না।"
            )
            return

        admin_states[user_id] = {
            "step": "broadcasting"
        }

        broadcast_running = True

        conn = db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id FROM users"
        )

        users = cursor.fetchall()

        conn.close()

        total = len(users)
        success = 0
        failed = 0

        bot.send_message(
            message.chat.id,
            "📢 *BROADCAST STARTED*\n\n"
            f"👥 Total Users: `{total}`\n\n"
            "⏳ Sending...",
            reply_markup=broadcast_markup()
        )

        for row in users:

            if not broadcast_running:
                break

            target_id = row[0]

            try:

                bot.send_message(
                    target_id,
                    "📢 *ANNOUNCEMENT*\n\n"
                    f"{broadcast_text}"
                )

                success += 1

            except Exception:

                failed += 1

        broadcast_running = False

        admin_states.pop(
            ADMIN_ID,
            None
        )

        bot.send_message(
            message.chat.id,
            "🎉 *BROADCAST FINISHED*\n\n"
            f"👥 Total: `{total}`\n"
            f"✅ Sent: `{success}`\n"
            f"❌ Failed: `{failed}`",
            reply_markup=admin_keyboard()
        )

        return


# =========================
# USER DIRECT CHAT
# =========================

@bot.message_handler(
    func=lambda message:
    message.from_user.id != ADMIN_ID
    and
    message.from_user.id in active_direct_chat.values()
)
def user_direct_chat(message):

    user_id = message.from_user.id

    if (
        message.text
        and
        message.text.startswith("/start")
    ):
        return

    try:

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "No Username"
        )

        text = (
            "💬 *USER MESSAGE*\n\n"
            f"👤 Name: `{message.from_user.first_name or 'Unknown'}`\n"
            f"🔗 Username: `{username}`\n"
            f"🆔 User ID: `{user_id}`\n\n"
            f"📩 Message:\n"
            f"{message.text or '📎 Non-text message'}"
        )

        bot.send_message(
            ADMIN_ID,
            text
        )

    except Exception:
        pass


# =========================
# REDEEM CODE
# =========================

@bot.message_handler(
    func=lambda message:
    message.text
    and
    message.text.strip().upper().startswith("GIVE-")
)
def redeem_code(message):

    user_id = message.from_user.id
    code = message.text.strip().upper()

    if not is_user_subscribed(user_id):

        send_force_join(
            message.chat.id
        )

        return

    save_user(
        message.from_user
    )

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
        WHERE id=?
        AND status='Unused'
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
# REDEEM BUTTON
# =========================

def is_redeem_button(text):

    return text in [
        "🔑 Redeem Code",
        "🔑 Redeem Code"
    ]


@bot.message_handler(
    func=lambda message:
    message.text in [
        "🔑 Redeem Code"
    ]
)
def redeem_help(message):

    lang = get_user_lang(
        message.from_user.id
    )

    if lang == "en":

        text = (
            "🔑 *REDEEM CODE*\n\n"
            "Send your Giveaway Code here.\n\n"
            "Example:\n"
            "`GIVE-2026-001`"
        )

    else:

        text = (
            "🔑 *REDEEM CODE*\n\n"
            "আপনার পাওয়া Giveaway Code সরাসরি এখানে পাঠান।\n\n"
            "Example:\n"
            "`GIVE-2026-001`"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================
# DAILY GIVEAWAY
# =========================

@bot.message_handler(
    func=lambda message:
    message.text in [
        "🎁 Daily Giveaway"
    ]
)
def daily_giveaway(message):

    lang = get_user_lang(
        message.from_user.id
    )

    if lang == "en":

        text = (
            "🎁 *DAILY GIVEAWAY*\n\n"
            "Check our channel announcements "
            "for today's Giveaway Code."
        )

    else:

        text = (
            "🎁 *DAILY GIVEAWAY*\n\n"
            "আজকের Giveaway Code পেতে "
            "আমাদের channel-এর announcement দেখুন।"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================
# MY STATUS
# =========================

@bot.message_handler(
    func=lambda message:
    message.text in [
        "📊 My Status"
    ]
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

    lang = get_user_lang(user_id)

    if lang == "en":

        text = (
            "📊 *YOUR STATUS*\n\n"
            f"🎁 Redeemed: `{count}`"
        )

    else:

        text = (
            "📊 *YOUR STATUS*\n\n"
            f"🎁 Redeemed: `{count}`"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================
# SETTINGS
# =========================

@bot.message_handler(
    func=lambda message:
    message.text in [
        "⚙️ Settings"
    ]
)
def settings(message):

    user_id = message.from_user.id
    lang = get_user_lang(user_id)

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
        TEXT[lang]["settings"],
        reply_markup=markup
    )


# =========================
# END DIRECT CHAT
# =========================

@bot.message_handler(
    commands=["endchat"]
)
def end_chat(message):

    if message.from_user.id != ADMIN_ID:
        return

    active_direct_chat.pop(
        ADMIN_ID,
        None
    )

    admin_states.pop(
        ADMIN_ID,
        None
    )

    bot.send_message(
        message.chat.id,
        "🛑 *DIRECT CHAT ENDED*",
        reply_markup=admin_keyboard()
    )


# =========================
# BROADCAST COMMAND
# =========================

@bot.message_handler(
    commands=["broadcast"]
)
def broadcast_command(message):

    if message.from_user.id != ADMIN_ID:
        return

    admin_states[ADMIN_ID] = {
        "step": "waiting_broadcast"
    }

    bot.send_message(
        message.chat.id,
        "📢 *BROADCAST SYSTEM*\n\n"
        "এখন যে মেসেজটি সকল registered user-কে পাঠাতে চান সেটি পাঠান।"
    )


# =========================
# START
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
