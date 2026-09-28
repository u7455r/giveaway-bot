import os
import sqlite3
import threading
import time
from datetime import datetime, date

import telebot
from telebot import types
from flask import Flask


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# ADMIN_ID অবশ্যই Render Environment Variable-এ দেবে
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# তোমার Public Channel
CHANNEL_1 = os.getenv("CHANNEL_1", "@hacksmethod6").strip()

# তোমার Public Group
GROUP_1 = os.getenv("GROUP_1", "@rafimhossen3").strip()

DB_FILE = os.getenv("DB_FILE", "giveaway_bot.db")

SUPPORT_USERNAME = os.getenv(
    "SUPPORT_USERNAME",
    "rafimhossen"
).strip().lstrip("@")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable missing")

if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID environment variable missing")


bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


# =========================================================
# FLASK SERVER - RENDER KEEP ALIVE
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Giveaway Bot is running!"


@app.route("/health")
def health():
    return "OK"


# =========================================================
# DATABASE
# =========================================================

db_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False,
        timeout=30
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redeem_code TEXT UNIQUE NOT NULL,
                reward_text TEXT NOT NULL,
                category TEXT DEFAULT 'Giveaway',
                status TEXT DEFAULT 'active',
                used_by INTEGER,
                used_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                alert_sent INTEGER DEFAULT 0,
                daily_date TEXT,
                daily_claimed INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_lang (
                user_id INTEGER PRIMARY KEY,
                lang TEXT DEFAULT 'bn'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS redeem_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                redeem_code TEXT,
                reward_text TEXT,
                redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()


init_db()


# =========================================================
# ADMIN STATES
# =========================================================

admin_states = {}

broadcast_running = False


# =========================================================
# LANGUAGE
# =========================================================

TEXT = {
    "bn": {
        "welcome": (
            "🎉 <b>Welcome to Giveaway Bot!</b>\n\n"
            "🔥 এখানে Giveaway Code Redeem করতে পারবে।\n"
            "🎁 Daily Giveaway Claim করতে পারবে।\n"
            "📊 নিজের Status দেখতে পারবে।\n\n"
            "👇 নিচের Menu ব্যবহার করো।"
        ),

        "join_title": (
            "🔒 <b>আগে Join করুন</b>\n\n"
            "🎯 Bot ব্যবহার করার আগে নিচের দুটো জায়গায় Join করতে হবে।\n\n"
            "1️⃣ Channel\n"
            "2️⃣ Group\n\n"
            "✅ Join করার পর <b>Verify</b> চাপুন।"
        ),

        "verify_success": (
            "✅ <b>Verification Successful!</b>\n\n"
            "🎉 আপনি সফলভাবে Channel এবং Group-এ Joined আছেন।\n"
            "🚀 এখন Bot-এর সব Feature ব্যবহার করতে পারবেন।"
        ),

        "verify_failed": (
            "❌ <b>Verification Failed!</b>\n\n"
            "⚠️ আপনি এখনো Channel অথবা Group-এ Joined নন।\n"
            "👇 দুটো জায়গায় Join করে আবার Verify করুন।"
        ),

        "redeem_help": (
            "🔑 <b>Redeem Code</b>\n\n"
            "আপনার Giveaway Code পাঠান।\n\n"
            "উদাহরণ:\n"
            "<code>GIVE-ABC123</code>"
        ),

        "invalid_code": (
            "❌ <b>Invalid Code!</b>\n\n"
            "এই Code পাওয়া যায়নি অথবা Codeটি ইতিমধ্যে ব্যবহার করা হয়েছে।"
        ),

        "redeem_success": (
            "🎉 <b>Congratulations!</b>\n\n"
            "✅ আপনার Code সফলভাবে Redeem হয়েছে।\n\n"
            "🎁 <b>Reward:</b>\n"
            "{reward}"
        ),

        "daily": (
            "🎁 <b>Daily Giveaway</b>\n\n"
            "প্রতিদিন একজন User Daily Reward Claim করতে পারবে।"
        ),

        "daily_success": (
            "🎉 <b>Daily Giveaway Claimed!</b>\n\n"
            "🎁 আজকের Daily Reward সফলভাবে Claim হয়েছে।"
        ),

        "daily_already": (
            "⏳ <b>Already Claimed!</b>\n\n"
            "আপনি আজকের Daily Giveaway ইতিমধ্যে Claim করেছেন।\n"
            "🌅 আগামীকাল আবার Claim করতে পারবেন।"
        ),

        "status": (
            "📊 <b>My Status</b>\n\n"
            "🆔 ID: <code>{id}</code>\n"
            "👤 Name: {name}\n"
            "🔗 Username: {username}\n"
            "🎁 Redeemed: {redeemed}\n"
            "📅 Daily: {daily}"
        ),

        "settings": (
            "⚙️ <b>Settings</b>\n\n"
            "🌐 Language পরিবর্তন করতে নিচের Button চাপুন।"
        ),

        "language_changed": (
            "✅ Language successfully changed to <b>{language}</b>."
        ),

        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "🔑 Redeem Code — Giveaway Code Redeem\n"
            "🎁 Daily Giveaway — Daily Reward\n"
            "📊 My Status — Account Status\n"
            "⚙️ Settings — Language Settings\n\n"
            "🆘 Support: @{support}"
        ),

        "not_registered": "❌ আগে /start দিয়ে Bot ব্যবহার শুরু করুন।"
    },

    "en": {
        "welcome": (
            "🎉 <b>Welcome to Giveaway Bot!</b>\n\n"
            "🔥 Redeem Giveaway Codes.\n"
            "🎁 Claim your Daily Giveaway.\n"
            "📊 Check your account status.\n\n"
            "👇 Use the menu below."
        ),

        "join_title": (
            "🔒 <b>Join Required</b>\n\n"
            "🎯 You must join both places before using the bot.\n\n"
            "1️⃣ Channel\n"
            "2️⃣ Group\n\n"
            "✅ After joining, press <b>Verify</b>."
        ),

        "verify_success": (
            "✅ <b>Verification Successful!</b>\n\n"
            "🎉 You are successfully joined to the Channel and Group.\n"
            "🚀 You can now use all bot features."
        ),

        "verify_failed": (
            "❌ <b>Verification Failed!</b>\n\n"
            "⚠️ You are not joined to the Channel or Group yet.\n"
            "👇 Join both and press Verify again."
        ),

        "redeem_help": (
            "🔑 <b>Redeem Code</b>\n\n"
            "Send your Giveaway Code.\n\n"
            "Example:\n"
            "<code>GIVE-ABC123</code>"
        ),

        "invalid_code": (
            "❌ <b>Invalid Code!</b>\n\n"
            "This code does not exist or has already been used."
        ),

        "redeem_success": (
            "🎉 <b>Congratulations!</b>\n\n"
            "✅ Your code has been successfully redeemed.\n\n"
            "🎁 <b>Reward:</b>\n"
            "{reward}"
        ),

        "daily": (
            "🎁 <b>Daily Giveaway</b>\n\n"
            "You can claim the Daily Reward once per day."
        ),

        "daily_success": (
            "🎉 <b>Daily Giveaway Claimed!</b>\n\n"
            "🎁 Today's Daily Reward has been claimed successfully."
        ),

        "daily_already": (
            "⏳ <b>Already Claimed!</b>\n\n"
            "You have already claimed today's Daily Giveaway.\n"
            "🌅 Come back tomorrow."
        ),

        "status": (
            "📊 <b>My Status</b>\n\n"
            "🆔 ID: <code>{id}</code>\n"
            "👤 Name: {name}\n"
            "🔗 Username: {username}\n"
            "🎁 Redeemed: {redeemed}\n"
            "📅 Daily: {daily}"
        ),

        "settings": (
            "⚙️ <b>Settings</b>\n\n"
            "🌐 Select your language below."
        ),

        "language_changed": (
            "✅ Language successfully changed to <b>{language}</b>."
        ),

        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "🔑 Redeem Code — Redeem a Giveaway Code\n"
            "🎁 Daily Giveaway — Daily Reward\n"
            "📊 My Status — Account Status\n"
            "⚙️ Settings — Language Settings\n\n"
            "🆘 Support: @{support}"
        ),

        "not_registered": "❌ Start the bot with /start first."
    }
}


def get_lang(user_id):
    with db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT lang FROM user_lang WHERE user_id=?",
            (user_id,)
        ).fetchone()
        conn.close()

    if row and row["lang"] in ("bn", "en"):
        return row["lang"]

    return "bn"


def set_lang(user_id, lang):
    with db_lock:
        conn = get_db()
        conn.execute("""
            INSERT INTO user_lang(user_id, lang)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET lang=excluded.lang
        """, (user_id, lang))
        conn.commit()
        conn.close()


def t(user_id, key, **kwargs):
    lang = get_lang(user_id)

    text = TEXT.get(lang, TEXT["bn"]).get(key, "")

    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass

    return text


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard(user_id):
    lang = get_lang(user_id)

    keyboard = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    if lang == "en":
        keyboard.add(
            types.KeyboardButton("🔑 Redeem Code"),
            types.KeyboardButton("⚙️ Settings")
        )
        keyboard.add(
            types.KeyboardButton("🎁 Daily Giveaway"),
            types.KeyboardButton("📊 My Status")
        )
        keyboard.add(
            types.KeyboardButton("ℹ️ Help")
        )
    else:
        keyboard.add(
            types.KeyboardButton("🔑 কোড রিডিম"),
            types.KeyboardButton("⚙️ সেটিংস")
        )
        keyboard.add(
            types.KeyboardButton("🎁 ডেইলি গিভঅ্যাওয়ে"),
            types.KeyboardButton("📊 আমার স্ট্যাটাস")
        )
        keyboard.add(
            types.KeyboardButton("ℹ️ সাহায্য")
        )

    return keyboard


def admin_keyboard():
    keyboard = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    keyboard.add(
        types.KeyboardButton("➕ Add Giveaway"),
        types.KeyboardButton("📋 Active Codes")
    )

    keyboard.add(
        types.KeyboardButton("📊 Statistics"),
        types.KeyboardButton("📢 Broadcast")
    )

    keyboard.add(
        types.KeyboardButton("💬 Direct User Chat"),
        types.KeyboardButton("🛑 Cancel Broadcast")
    )

    keyboard.add(
        types.KeyboardButton("🏠 User Menu")
    )

    return keyboard


def force_join_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    keyboard.add(
        types.InlineKeyboardButton(
            "📢 Join Channel",
            url="https://t.me/hacksmethod6"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "👥 Join Group",
            url="https://t.me/rafimhossen3"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "✅ Verify",
            callback_data="verify_join"
        )
    )

    return keyboard


def language_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        types.InlineKeyboardButton(
            "🇧🇩 বাংলা",
            callback_data="lang_bn"
        ),
        types.InlineKeyboardButton(
            "🇬🇧 English",
            callback_data="lang_en"
        )
    )

    return keyboard


# =========================================================
# USER DATABASE
# =========================================================

def save_user(user):
    with db_lock:
        conn = get_db()

        conn.execute("""
            INSERT INTO users(
                user_id,
                username,
                first_name,
                last_name
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            user.last_name or ""
        ))

        conn.commit()
        conn.close()


def get_user(user_id):
    with db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()
        conn.close()

    return row


# =========================================================
# MEMBERSHIP CHECK
# =========================================================

def get_member(chat_id, user_id):
    try:
        return bot.get_chat_member(chat_id, user_id)
    except Exception:
        return None


def member_is_valid(member):
    if not member:
        return False

    status = getattr(member, "status", "")

    if status in (
        "creator",
        "administrator",
        "member"
    ):
        return True

    # Restricted member can still be a valid member
    if status == "restricted":
        return bool(getattr(member, "is_member", False))

    return False


def check_membership(user_id):
    channel_member = get_member(CHANNEL_1, user_id)
    group_member = get_member(GROUP_1, user_id)

    channel_ok = member_is_valid(channel_member)
    group_ok = member_is_valid(group_member)

    return channel_ok and group_ok


# =========================================================
# FORCE JOIN
# =========================================================

def send_force_join(chat_id):
    bot.send_message(
        chat_id,
        t(chat_id, "join_title"),
        reply_markup=force_join_keyboard()
    )


# =========================================================
# NEW USER ADMIN ALERT
# =========================================================

def send_new_user_alert(user):
    row = get_user(user.id)

    if not row:
        return

    if row["alert_sent"]:
        return

    name = (
        f"{user.first_name or ''} "
        f"{user.last_name or ''}"
    ).strip()

    username = (
        f"@{user.username}"
        if user.username
        else "No Username"
    )

    text = (
        "🚨 <b>NEW USER JOINED</b>\n\n"
        f"👤 Name: {name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 User ID: <code>{user.id}</code>\n\n"
        "✅ Channel + Group Verification Passed."
    )

    try:
        bot.send_message(ADMIN_ID, text)

        with db_lock:
            conn = get_db()
            conn.execute(
                "UPDATE users SET alert_sent=1 WHERE user_id=?",
                (user.id,)
            )
            conn.commit()
            conn.close()

    except Exception:
        pass


# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def start_handler(message):
    user = message.from_user

    save_user(user)

    if user.id == ADMIN_ID:
        bot.send_message(
            user.id,
            "👑 <b>Admin Panel</b>\n\n"
            "🔥 Welcome Admin!",
            reply_markup=admin_keyboard()
        )
        return

    if not check_membership(user.id):
        send_force_join(user.id)
        return

    send_new_user_alert(user)

    bot.send_message(
        user.id,
        t(user.id, "welcome"),
        reply_markup=main_keyboard(user.id)
    )


# =========================================================
# VERIFY JOIN
# =========================================================

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_callback(call):
    user_id = call.from_user.id

    try:
        bot.answer_callback_query(
            call.id,
            "🔍 Checking..."
        )
    except Exception:
        pass

    save_user(call.from_user)

    if check_membership(user_id):
        send_new_user_alert(call.from_user)

        try:
            bot.edit_message_text(
                t(user_id, "verify_success"),
                user_id,
                call.message.message_id
            )
        except Exception:
            pass

        bot.send_message(
            user_id,
            "🏠 <b>Main Menu</b>",
            reply_markup=main_keyboard(user_id)
        )

    else:
        try:
            bot.edit_message_text(
                t(user_id, "verify_failed"),
                user_id,
                call.message.message_id,
                reply_markup=force_join_keyboard()
            )
        except Exception:
            bot.send_message(
                user_id,
                t(user_id, "verify_failed"),
                reply_markup=force_join_keyboard()
            )


# =========================================================
# SETTINGS
# =========================================================

def show_settings(chat_id):
    bot.send_message(
        chat_id,
        t(chat_id, "settings"),
        reply_markup=language_keyboard()
    )


# =========================================================
# LANGUAGE CALLBACK
# =========================================================

@bot.callback_query_handler(
    func=lambda call: call.data in ("lang_bn", "lang_en")
)
def language_callback(call):
    user_id = call.from_user.id

    lang = "bn" if call.data == "lang_bn" else "en"

    set_lang(user_id, lang)

    language_name = "বাংলা 🇧🇩" if lang == "bn" else "English 🇬🇧"

    try:
        bot.answer_callback_query(
            call.id,
            "✅ Language changed!"
        )
    except Exception:
        pass

    bot.send_message(
        user_id,
        t(
            user_id,
            "language_changed",
            language=language_name
        ),
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# REDEEM
# =========================================================

def redeem_code(user_id, code):
    code = code.strip().upper()

    with db_lock:
        conn = get_db()

        row = conn.execute("""
            SELECT *
            FROM giveaways
            WHERE redeem_code=?
              AND status='active'
        """, (code,)).fetchone()

        if not row:
            conn.close()
            return None

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            UPDATE giveaways
            SET status='used',
                used_by=?,
                used_at=?
            WHERE id=?
              AND status='active'
        """, (
            user_id,
            now,
            row["id"]
        ))

        conn.execute("""
            INSERT INTO redeem_history(
                user_id,
                redeem_code,
                reward_text
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            code,
            row["reward_text"]
        ))

        conn.commit()
        conn.close()

    return row


@bot.message_handler(
    func=lambda message:
    message.text
    and message.text.strip().upper().startswith("GIVE-")
)
def redeem_message(message):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        return

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    save_user(message.from_user)

    result = redeem_code(
        user_id,
        message.text
    )

    if not result:
        bot.send_message(
            user_id,
            t(user_id, "invalid_code")
        )
        return

    bot.send_message(
        user_id,
        t(
            user_id,
            "redeem_success",
            reward=result["reward_text"]
        ),
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# DAILY GIVEAWAY
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "🎁 Daily Giveaway",
        "🎁 ডেইলি গিভঅ্যাওয়ে"
    )
)
def daily_handler(message):
    user_id = message.from_user.id

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    save_user(message.from_user)

    today = date.today().isoformat()

    with db_lock:
        conn = get_db()

        row = conn.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if row["daily_date"] == today and row["daily_claimed"] == 1:
            conn.close()

            bot.send_message(
                user_id,
                t(user_id, "daily_already")
            )
            return

        conn.execute("""
            UPDATE users
            SET daily_date=?,
                daily_claimed=1
            WHERE user_id=?
        """, (
            today,
            user_id
        ))

        conn.commit()
        conn.close()

    bot.send_message(
        user_id,
        t(user_id, "daily_success"),
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# STATUS
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "📊 My Status",
        "📊 আমার স্ট্যাটাস"
    )
)
def status_handler(message):
    user_id = message.from_user.id

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    save_user(message.from_user)

    row = get_user(user_id)

    with db_lock:
        conn = get_db()

        redeemed = conn.execute("""
            SELECT COUNT(*)
            FROM redeem_history
            WHERE user_id=?
        """, (user_id,)).fetchone()[0]

        conn.close()

    daily = "Claimed" if row["daily_claimed"] else "Not Claimed"

    if get_lang(user_id) == "bn":
        daily = "ক্লেইম করা হয়েছে" if row["daily_claimed"] else "ক্লেইম করা হয়নি"

    name = (
        f"{row['first_name'] or ''} "
        f"{row['last_name'] or ''}"
    ).strip()

    username = (
        f"@{row['username']}"
        if row["username"]
        else "No Username"
    )

    bot.send_message(
        user_id,
        t(
            user_id,
            "status",
            id=user_id,
            name=name or "Unknown",
            username=username,
            redeemed=redeemed,
            daily=daily
        ),
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# HELP
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "ℹ️ Help",
        "ℹ️ সাহায্য"
    )
)
def help_handler(message):
    user_id = message.from_user.id

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    bot.send_message(
        user_id,
        t(
            user_id,
            "help",
            support=SUPPORT_USERNAME
        ),
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# SETTINGS BUTTON
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "⚙️ Settings",
        "⚙️ সেটিংস"
    )
)
def settings_handler(message):
    user_id = message.from_user.id

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    show_settings(user_id)


# =========================================================
# REDEEM BUTTON
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "🔑 Redeem Code",
        "🔑 কোড রিডিম"
    )
)
def redeem_button(message):
    user_id = message.from_user.id

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    bot.send_message(
        user_id,
        t(user_id, "redeem_help"),
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


# =========================================================
# ADMIN PANEL
# =========================================================

@bot.message_handler(commands=["admin"])
def admin_command(message):
    if not is_admin(message.from_user.id):
        return

    admin_states.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "👑 <b>ADMIN PANEL</b>\n\n"
        "🔥 Select an option below.",
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADD GIVEAWAY
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and message.text == "➕ Add Giveaway"
)
def add_giveaway_start(message):
    admin_states[message.from_user.id] = {
        "action": "add_code"
    }

    bot.send_message(
        message.chat.id,
        "➕ <b>Add Giveaway</b>\n\n"
        "🔑 এখন Giveaway Code পাঠাও।\n\n"
        "Example:\n"
        "<code>GIVE-ABC123</code>\n\n"
        "❌ Cancel করতে /cancel পাঠাও।"
    )


# =========================================================
# ACTIVE CODES
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and message.text == "📋 Active Codes"
)
def active_codes(message):
    with db_lock:
        conn = get_db()

        rows = conn.execute("""
            SELECT redeem_code, reward_text, category, created_at
            FROM giveaways
            WHERE status='active'
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()

        conn.close()

    if not rows:
        bot.send_message(
            message.chat.id,
            "📋 <b>Active Codes</b>\n\n"
            "❌ কোনো Active Code নেই।"
        )
        return

    text = "📋 <b>ACTIVE GIVEAWAYS</b>\n\n"

    for index, row in enumerate(rows, 1):
        text += (
            f"{index}️⃣ <code>{row['redeem_code']}</code>\n"
            f"🎁 {row['reward_text']}\n"
            f"🏷 {row['category']}\n\n"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================================================
# STATISTICS
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and message.text == "📊 Statistics"
)
def statistics(message):
    with db_lock:
        conn = get_db()

        total_users = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        total_codes = conn.execute(
            "SELECT COUNT(*) FROM giveaways"
        ).fetchone()[0]

        active_codes = conn.execute("""
            SELECT COUNT(*)
            FROM giveaways
            WHERE status='active'
        """).fetchone()[0]

        used_codes = conn.execute("""
            SELECT COUNT(*)
            FROM giveaways
            WHERE status='used'
        """).fetchone()[0]

        redeemed = conn.execute(
            "SELECT COUNT(*) FROM redeem_history"
        ).fetchone()[0]

        today_users = conn.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE DATE(registered_at)=DATE('now')
        """).fetchone()[0]

        today_redeem = conn.execute("""
            SELECT COUNT(*)
            FROM redeem_history
            WHERE DATE(redeemed_at)=DATE('now')
        """).fetchone()[0]

        conn.close()

    text = (
        "📊 <b>BOT STATISTICS</b>\n\n"
        f"👥 Total Users: <b>{total_users}</b>\n"
        f"🆕 Today's Users: <b>{today_users}</b>\n\n"
        f"🎁 Total Codes: <b>{total_codes}</b>\n"
        f"🟢 Active Codes: <b>{active_codes}</b>\n"
        f"🔴 Used Codes: <b>{used_codes}</b>\n"
        f"🔑 Total Redeems: <b>{redeemed}</b>\n"
        f"📅 Today's Redeems: <b>{today_redeem}</b>"
    )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================================================
# BROADCAST START
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and message.text == "📢 Broadcast"
)
def broadcast_start(message):
    global broadcast_running

    admin_states[message.from_user.id] = {
        "action": "broadcast"
    }

    broadcast_running = False

    bot.send_message(
        message.chat.id,
        "📢 <b>Broadcast Mode</b>\n\n"
        "যে Message সবাইকে পাঠাতে চাও সেটা এখন পাঠাও।\n\n"
        "🛑 Cancel করতে /cancel পাঠাও।"
    )


# =========================================================
# BROADCAST CANCEL BUTTON
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and message.text == "🛑 Cancel Broadcast"
)
def cancel_broadcast_button(message):
    global broadcast_running

    broadcast_running = False

    admin_states.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "🛑 <b>Broadcast Cancelled!</b>",
        reply_markup=admin_keyboard()
    )


# =========================================================
# DIRECT USER CHAT START
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and message.text == "💬 Direct User Chat"
)
def direct_chat_start(message):
    admin_states[message.from_user.id] = {
        "action": "direct_user"
    }

    bot.send_message(
        message.chat.id,
        "💬 <b>Direct User Chat</b>\n\n"
        "যে User-এর সাথে Chat করতে চাও তার Telegram ID পাঠাও।\n\n"
        "Example:\n"
        "<code>123456789</code>\n\n"
        "❌ Cancel করতে /cancel পাঠাও।"
    )


# =========================================================
# USER -> ADMIN DIRECT REPLY
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.from_user.id != ADMIN_ID
)
def user_messages(message):
    user_id = message.from_user.id

    # Command messages already handled above
    if message.text and message.text.startswith("/"):
        return

    # Force join
    if not check_membership(user_id):
        send_force_join(user_id)
        return

    # Forward normal messages to admin
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "No Username"
    )

    header = (
        "📩 <b>USER MESSAGE</b>\n\n"
        f"👤 {message.from_user.first_name or 'Unknown'}\n"
        f"🔗 {username}\n"
        f"🆔 <code>{user_id}</code>\n\n"
    )

    try:
        if message.content_type == "text":
            bot.send_message(
                ADMIN_ID,
                header + message.text
            )

        else:
            bot.send_message(
                ADMIN_ID,
                header +
                "📎 <b>Non-text message received.</b>"
            )

    except Exception:
        pass


# =========================================================
# ADMIN INPUT HANDLER
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
)
def admin_input(message):
    user_id = message.from_user.id

    state = admin_states.get(user_id)

    if not state:
        return

    action = state.get("action")

    # -----------------------------------------------------
    # CANCEL
    # -----------------------------------------------------

    if message.text and message.text.strip().lower() == "/cancel":
        admin_states.pop(user_id, None)

        bot.send_message(
            user_id,
            "❌ <b>Action Cancelled.</b>",
            reply_markup=admin_keyboard()
        )
        return

    # -----------------------------------------------------
    # ADD CODE
    # -----------------------------------------------------

    if action == "add_code":
        code = message.text.strip().upper()

        if not code.startswith("GIVE-"):
            bot.send_message(
                user_id,
                "❌ Code অবশ্যই <code>GIVE-</code> দিয়ে শুরু করতে হবে।\n\n"
                "Example:\n"
                "<code>GIVE-ABC123</code>"
            )
            return

        with db_lock:
            conn = get_db()

            existing = conn.execute(
                "SELECT id FROM giveaways WHERE redeem_code=?",
                (code,)
            ).fetchone()

            conn.close()

        if existing:
            bot.send_message(
                user_id,
                "❌ এই Code ইতিমধ্যে আছে। অন্য Code দাও।"
            )
            return

        admin_states[user_id] = {
            "action": "add_reward",
            "code": code
        }

        bot.send_message(
            user_id,
            "🎁 এখন এই Code-এর <b>Reward</b> পাঠাও।\n\n"
            "Example:\n"
            "<code>100 Points</code>\n"
            "অথবা\n"
            "<code>Premium Access</code>"
        )
        return

    # -----------------------------------------------------
    # ADD REWARD
    # -----------------------------------------------------

    if action == "add_reward":
        reward = message.text.strip()
        code = state["code"]

        with db_lock:
            conn = get_db()

            conn.execute("""
                INSERT INTO giveaways(
                    redeem_code,
                    reward_text,
                    category,
                    status
                )
                VALUES (?, ?, ?, 'active')
            """, (
                code,
                reward,
                "Giveaway"
            ))

            conn.commit()
            conn.close()

        admin_states.pop(user_id, None)

        bot.send_message(
            user_id,
            "✅ <b>Giveaway Created!</b>\n\n"
            f"🔑 Code: <code>{code}</code>\n"
            f"🎁 Reward: {reward}",
            reply_markup=admin_keyboard()
        )
        return

    # -----------------------------------------------------
    # BROADCAST
    # -----------------------------------------------------

    if action == "broadcast":
        admin_states.pop(user_id, None)

        broadcast_message = message

        thread = threading.Thread(
            target=run_broadcast,
            args=(broadcast_message,),
            daemon=True
        )

        thread.start()

        return

    # -----------------------------------------------------
    # DIRECT USER
    # -----------------------------------------------------

    if action == "direct_user":
        try:
            target_id = int(message.text.strip())
        except Exception:
            bot.send_message(
                user_id,
                "❌ সঠিক numeric Telegram User ID দাও।"
            )
            return

        target = get_user(target_id)

        if not target:
            bot.send_message(
                user_id,
                "❌ এই User Bot-এ Registered নেই।"
            )
            return

        admin_states[user_id] = {
            "action": "direct_message",
            "target_id": target_id
        }

        bot.send_message(
            user_id,
            "💬 <b>Direct Chat Active</b>\n\n"
            f"🆔 User ID: <code>{target_id}</code>\n\n"
            "এখন তোমার Message পাঠাও।\n"
            "শেষ করতে /endchat পাঠাও।"
        )
        return

    # -----------------------------------------------------
    # DIRECT MESSAGE
    # -----------------------------------------------------

    if action == "direct_message":
        if message.text and message.text.strip().lower() == "/endchat":
            admin_states.pop(user_id, None)

            bot.send_message(
                user_id,
                "✅ Direct Chat Ended.",
                reply_markup=admin_keyboard()
            )
            return

        target_id = state["target_id"]

        try:
            if message.content_type == "text":
                bot.send_message(
                    target_id,
                    "👑 <b>Admin Message</b>\n\n"
                    + message.text
                )

            elif message.content_type == "photo":
                bot.send_photo(
                    target_id,
                    message.photo[-1].file_id,
                    caption=(
                        "👑 <b>Admin Message</b>\n\n"
                        + (message.caption or "")
                    )
                )

            elif message.content_type == "video":
                bot.send_video(
                    target_id,
                    message.video.file_id,
                    caption=(
                        "👑 <b>Admin Message</b>\n\n"
                        + (message.caption or "")
                    )
                )

            elif message.content_type == "document":
                bot.send_document(
                    target_id,
                    message.document.file_id,
                    caption=(
                        "👑 <b>Admin Message</b>\n\n"
                        + (message.caption or "")
                    )
                )

            else:
                bot.send_message(
                    target_id,
                    "👑 <b>Admin Message</b>\n\n"
                    "📎 একটি Message পাঠানো হয়েছে।"
                )

            bot.send_message(
                user_id,
                "✅ Message Sent."
            )

        except Exception as e:
            bot.send_message(
                user_id,
                "❌ Message Send Failed.\n\n"
                f"<code>{str(e)[:300]}</code>"
            )

        return


# =========================================================
# BROADCAST FUNCTION
# =========================================================

def run_broadcast(message):
    global broadcast_running

    broadcast_running = True

    with db_lock:
        conn = get_db()

        users = conn.execute(
            "SELECT user_id FROM users"
        ).fetchall()

        conn.close()

    total = len(users)
    success = 0
    failed = 0

    if total == 0:
        broadcast_running = False

        bot.send_message(
            ADMIN_ID,
            "❌ কোনো Registered User নেই।"
        )
        return

    progress_message = bot.send_message(
        ADMIN_ID,
        "📢 <b>Broadcast Started</b>\n\n"
        f"👥 Total: {total}\n"
        "📤 Sent: 0\n"
        "❌ Failed: 0\n"
        "📊 Progress: 0%"
    )

    for index, row in enumerate(users, 1):

        if not broadcast_running:
            break

        target_id = row["user_id"]

        try:
            bot.copy_message(
                target_id,
                message.chat.id,
                message.message_id
            )

            success += 1

        except Exception:
            failed += 1

        percent = int((index / total) * 100)

        if (
            index == 1
            or index % 10 == 0
            or index == total
        ):
            try:
                bot.edit_message_text(
                    "📢 <b>Broadcast Running...</b>\n\n"
                    f"👥 Total: {total}\n"
                    f"📤 Sent: {success}\n"
                    f"❌ Failed: {failed}\n"
                    f"📊 Progress: {percent}%",
                    ADMIN_ID,
                    progress_message.message_id
                )
            except Exception:
                pass

        time.sleep(0.05)

    was_cancelled = not broadcast_running

    broadcast_running = False

    if was_cancelled:
        status = "🛑 <b>Broadcast Cancelled</b>"
    else:
        status = "✅ <b>Broadcast Completed</b>"

    try:
        bot.edit_message_text(
            f"{status}\n\n"
            f"👥 Total: {total}\n"
            f"📤 Sent: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📊 Progress: "
            f"{int(((success + failed) / total) * 100)}%",
            ADMIN_ID,
            progress_message.message_id
        )
    except Exception:
        pass


# =========================================================
# ADMIN USER MENU
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and message.text == "🏠 User Menu"
)
def admin_user_menu(message):
    admin_states.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "🏠 <b>User Menu</b>",
        reply_markup=main_keyboard(message.from_user.id)
    )


# =========================================================
# ADMIN /ENDCHAT
# =========================================================

@bot.message_handler(commands=["endchat"])
def endchat_command(message):
    if not is_admin(message.from_user.id):
        return

    admin_states.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "✅ <b>Direct Chat Ended.</b>",
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN /USERS
# =========================================================

@bot.message_handler(commands=["users"])
def users_command(message):
    if not is_admin(message.from_user.id):
        return

    with db_lock:
        conn = get_db()

        rows = conn.execute("""
            SELECT user_id, username, first_name
            FROM users
            ORDER BY registered_at DESC
            LIMIT 30
        """).fetchall()

        conn.close()

    if not rows:
        bot.send_message(
            message.chat.id,
            "❌ No users found."
        )
        return

    text = "👥 <b>RECENT USERS</b>\n\n"

    for row in rows:
        username = (
            f"@{row['username']}"
            if row["username"]
            else "No Username"
        )

        text += (
            f"👤 {row['first_name'] or 'Unknown'}\n"
            f"🔗 {username}\n"
            f"🆔 <code>{row['user_id']}</code>\n\n"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================================================
# ERROR HANDLER
# =========================================================

def polling_error_handler():
    pass


# =========================================================
# FLASK THREAD
# =========================================================

def run_flask():
    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    print("Giveaway Bot starting...")

    bot.infinity_polling(
        skip_pending=True,
        allowed_updates=[
            "message",
            "callback_query"
        ],
        timeout=30,
        long_polling_timeout=30
    )
