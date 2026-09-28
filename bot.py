import os
import sqlite3
import threading
import time
import secrets
import string
from datetime import datetime, date

import telebot
from telebot import types
from flask import Flask


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHANNEL_1 = os.getenv("CHANNEL_1", "@hacksmethod6").strip()
GROUP_1 = os.getenv("GROUP_1", "@rafimhossen3").strip()

DB_FILE = os.getenv("DB_FILE", "giveaway_bot.db")
SUPPORT_USERNAME = os.getenv(
    "SUPPORT_USERNAME",
    "rafimhossen"
).strip().lstrip("@")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID is missing")


bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

app = Flask(__name__)

db_lock = threading.Lock()
admin_states = {}
broadcast_running = False


# =========================================================
# FLASK
# =========================================================

@app.route("/")
def home():
    return "Rafim Giveaway Bot is running!"


@app.route("/health")
def health():
    return "OK"


# =========================================================
# DATABASE
# =========================================================

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
# LANGUAGE
# =========================================================

TEXT = {
    "bn": {
        "welcome": (
            "🎉 <b>Rafim Giveaway Bot</b>\n\n"
            "🔥 স্বাগতম!\n\n"
            "🔑 Redeem Code ব্যবহার করুন\n"
            "🎁 Daily Giveaway Claim করুন\n"
            "📊 নিজের Status দেখুন\n\n"
            "👇 নিচের Menu ব্যবহার করুন।"
        ),

        "join": (
            "🔒 <b>আগে Join করুন</b>\n\n"
            "Bot ব্যবহার করার আগে নিচের দুটো জায়গায় Join করতে হবে।\n\n"
            "📢 Channel\n"
            "👥 Group\n\n"
            "✅ Join করার পর Verify চাপুন।"
        ),

        "verified": (
            "✅ <b>Verification Successful!</b>\n\n"
            "🎉 Channel এবং Group Join করা হয়েছে।\n"
            "🚀 এখন Bot ব্যবহার করতে পারবেন।"
        ),

        "failed": (
            "❌ <b>Verification Failed!</b>\n\n"
            "⚠️ Channel অথবা Group এখনো Join করা হয়নি।\n"
            "👇 দুটো জায়গায় Join করে আবার Verify করুন।"
        ),

        "redeem_help": (
            "🔑 <b>Redeem Code</b>\n\n"
            "🎁 আপনার Redeem Code দিন।\n\n"
            "উদাহরণ:\n"
            "<code>GIVE-ABC123</code>"
        ),

        "invalid": (
            "❌ <b>Invalid Code!</b>\n\n"
            "Codeটি ভুল, নেই অথবা ইতিমধ্যে ব্যবহার করা হয়েছে।"
        ),

        "success": (
            "🎉 <b>Congratulations!</b>\n\n"
            "✅ আপনার Code সফলভাবে Redeem হয়েছে!\n\n"
            "🎁 <b>Reward:</b>\n{reward}"
        ),

        "daily_success": (
            "🎉 <b>Daily Giveaway Claimed!</b>\n\n"
            "🎁 আজকের Reward সফলভাবে Claim হয়েছে।"
        ),

        "daily_already": (
            "⏳ <b>Already Claimed!</b>\n\n"
            "আপনি আজকের Daily Giveaway ইতিমধ্যে Claim করেছেন।"
        ),

        "settings": (
            "⚙️ <b>Settings</b>\n\n"
            "🌐 নিচ থেকে Language নির্বাচন করুন।"
        ),

        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "🔑 Redeem Code — Giveaway Code ব্যবহার\n"
            "🎁 Daily Giveaway — Daily Reward\n"
            "📊 My Status — Account Status\n"
            "⚙️ Settings — Language\n\n"
            "🆘 Support: @{support}"
        )
    },

    "en": {
        "welcome": (
            "🎉 <b>Rafim Giveaway Bot</b>\n\n"
            "🔥 Welcome!\n\n"
            "🔑 Redeem Giveaway Codes\n"
            "🎁 Claim Daily Giveaway\n"
            "📊 Check your Status\n\n"
            "👇 Use the menu below."
        ),

        "join": (
            "🔒 <b>Join Required</b>\n\n"
            "You must join both places before using the bot.\n\n"
            "📢 Channel\n"
            "👥 Group\n\n"
            "✅ Then press Verify."
        ),

        "verified": (
            "✅ <b>Verification Successful!</b>\n\n"
            "🎉 You joined the Channel and Group.\n"
            "🚀 You can now use the bot."
        ),

        "failed": (
            "❌ <b>Verification Failed!</b>\n\n"
            "⚠️ You haven't joined the Channel or Group yet.\n"
            "👇 Join both and verify again."
        ),

        "redeem_help": (
            "🔑 <b>Redeem Code</b>\n\n"
            "🎁 Send your Redeem Code.\n\n"
            "Example:\n"
            "<code>GIVE-ABC123</code>"
        ),

        "invalid": (
            "❌ <b>Invalid Code!</b>\n\n"
            "The code is invalid, doesn't exist, or was already used."
        ),

        "success": (
            "🎉 <b>Congratulations!</b>\n\n"
            "✅ Your code has been successfully redeemed!\n\n"
            "🎁 <b>Reward:</b>\n{reward}"
        ),

        "daily_success": (
            "🎉 <b>Daily Giveaway Claimed!</b>\n\n"
            "🎁 Today's reward has been claimed."
        ),

        "daily_already": (
            "⏳ <b>Already Claimed!</b>\n\n"
            "You already claimed today's Daily Giveaway."
        ),

        "settings": (
            "⚙️ <b>Settings</b>\n\n"
            "🌐 Select your language below."
        ),

        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "🔑 Redeem Code — Redeem Giveaway Code\n"
            "🎁 Daily Giveaway — Daily Reward\n"
            "📊 My Status — Account Status\n"
            "⚙️ Settings — Language\n\n"
            "🆘 Support: @{support}"
        )
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
    text = TEXT[lang].get(key, "")

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

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    if lang == "bn":
        kb.add(
            "🔑 কোড রিডিম",
            "⚙️ সেটিংস"
        )
        kb.add(
            "🎁 ডেইলি গিভঅ্যাওয়ে",
            "📊 আমার স্ট্যাটাস"
        )
        kb.add("ℹ️ সাহায্য")

    else:
        kb.add(
            "🔑 Redeem Code",
            "⚙️ Settings"
        )
        kb.add(
            "🎁 Daily Giveaway",
            "📊 My Status"
        )
        kb.add("ℹ️ Help")

    return kb


def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    kb.add(
        "➕ Add Giveaway",
        "📋 Active Codes"
    )

    kb.add(
        "📊 Statistics",
        "📢 Broadcast"
    )

    kb.add(
        "💬 Direct User Chat",
        "🛑 Cancel Broadcast"
    )

    kb.add("🏠 User Menu")

    return kb


def force_join_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)

    kb.add(
        types.InlineKeyboardButton(
            "📢 Join Channel",
            url="https://t.me/hacksmethod6"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "👥 Join Group",
            url="https://t.me/rafimhossen3"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "✅ Verify",
            callback_data="verify_join"
        )
    )

    return kb


def language_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton(
            "🇧🇩 বাংলা",
            callback_data="lang_bn"
        ),
        types.InlineKeyboardButton(
            "🇬🇧 English",
            callback_data="lang_en"
        )
    )

    return kb


# =========================================================
# USERS
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
# MEMBERSHIP
# =========================================================

def get_member(chat_id, user_id):
    try:
        return bot.get_chat_member(
            chat_id,
            user_id
        )
    except Exception:
        return None


def valid_member(member):
    if not member:
        return False

    status = getattr(member, "status", "")

    if status in (
        "creator",
        "administrator",
        "member"
    ):
        return True

    if status == "restricted":
        return bool(
            getattr(
                member,
                "is_member",
                False
            )
        )

    return False


def check_membership(user_id):
    channel = get_member(
        CHANNEL_1,
        user_id
    )

    group = get_member(
        GROUP_1,
        user_id
    )

    return (
        valid_member(channel)
        and
        valid_member(group)
    )


def send_force_join(chat_id):
    bot.send_message(
        chat_id,
        t(chat_id, "join"),
        reply_markup=force_join_keyboard()
    )


# =========================================================
# NEW USER ALERT
# =========================================================

def new_user_alert(user):
    row = get_user(user.id)

    if not row or row["alert_sent"]:
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
        "🚨 <b>NEW USER</b>\n\n"
        f"👤 Name: {name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        "✅ Channel + Group verified."
    )

    try:
        bot.send_message(
            ADMIN_ID,
            text
        )

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
            "👑 <b>ADMIN PANEL</b>\n\n"
            "🔥 Welcome Admin!",
            reply_markup=admin_keyboard()
        )
        return

    if not check_membership(user.id):
        send_force_join(user.id)
        return

    new_user_alert(user)

    bot.send_message(
        user.id,
        t(user.id, "welcome"),
        reply_markup=main_keyboard(user.id)
    )


# =========================================================
# VERIFY
# =========================================================

@bot.callback_query_handler(
    func=lambda call: call.data == "verify_join"
)
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

        new_user_alert(call.from_user)

        try:
            bot.edit_message_text(
                t(user_id, "verified"),
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
                t(user_id, "failed"),
                user_id,
                call.message.message_id,
                reply_markup=force_join_keyboard()
            )
        except Exception:
            pass


# =========================================================
# LANGUAGE
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data in ("lang_bn", "lang_en")
)
def language_callback(call):
    user_id = call.from_user.id

    lang = (
        "bn"
        if call.data == "lang_bn"
        else "en"
    )

    set_lang(
        user_id,
        lang
    )

    try:
        bot.answer_callback_query(
            call.id,
            "✅ Language changed!"
        )
    except Exception:
        pass

    name = (
        "বাংলা 🇧🇩"
        if lang == "bn"
        else
        "English 🇬🇧"
    )

    bot.send_message(
        user_id,
        (
            "✅ Language: <b>"
            + name
            + "</b>"
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

        now = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        updated = conn.execute("""
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

        if updated.rowcount != 1:
            conn.close()
            return None

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


# =========================================================
# REDEEM BUTTON
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "🔑 কোড রিডিম",
        "🔑 Redeem Code"
    )
)
def redeem_button(message):
    user_id = message.from_user.id

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    bot.send_message(
        user_id,
        t(user_id, "redeem_help")
    )


# =========================================================
# REDEEM CODE MESSAGE
# =========================================================

@bot.message_handler(
    func=lambda message:
    bool(
        message.text
        and
        message.text.strip().upper().startswith("GIVE-")
    )
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
            t(user_id, "invalid")
        )
        return

    bot.send_message(
        user_id,
        t(
            user_id,
            "success",
            reward=result["reward_text"]
        ),
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# DAILY
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "🎁 ডেইলি গিভঅ্যাওয়ে",
        "🎁 Daily Giveaway"
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

        if (
            row["daily_date"] == today
            and
            row["daily_claimed"] == 1
        ):
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
        "📊 আমার স্ট্যাটাস",
        "📊 My Status"
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

    daily = (
        "ক্লেইম করা হয়েছে"
        if get_lang(user_id) == "bn"
        and row["daily_claimed"]
        else
        "ক্লেইম করা হয়নি"
        if get_lang(user_id) == "bn"
        else
        "Claimed"
        if row["daily_claimed"]
        else
        "Not Claimed"
    )

    name = (
        f"{row['first_name'] or ''} "
        f"{row['last_name'] or ''}"
    ).strip()

    username = (
        f"@{row['username']}"
        if row["username"]
        else
        "No Username"
    )

    bot.send_message(
        user_id,
        (
            "📊 <b>My Status</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Name: {name or 'Unknown'}\n"
            f"🔗 Username: {username}\n"
            f"🎁 Redeemed: {redeemed}\n"
            f"📅 Daily: {daily}"
        ),
        reply_markup=main_keyboard(user_id)
    )


# =========================================================
# SETTINGS
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "⚙️ সেটিংস",
        "⚙️ Settings"
    )
)
def settings_handler(message):
    user_id = message.from_user.id

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    bot.send_message(
        user_id,
        t(user_id, "settings"),
        reply_markup=language_keyboard()
    )


# =========================================================
# HELP
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text in (
        "ℹ️ সাহায্য",
        "ℹ️ Help"
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

    admin_states.pop(
        message.from_user.id,
        None
    )

    bot.send_message(
        message.chat.id,
        "👑 <b>ADMIN PANEL</b>\n\n"
        "🔥 Select an option.",
        reply_markup=admin_keyboard()
    )


# =========================================================
# GENERATE CODE
# =========================================================

def generate_redeem_code():
    while True:

        chars = string.ascii_uppercase + string.digits

        random_part = "".join(
            secrets.choice(chars)
            for _ in range(8)
        )

        code = "GIVE-" + random_part

        with db_lock:
            conn = get_db()

            exists = conn.execute(
                "SELECT id FROM giveaways WHERE redeem_code=?",
                (code,)
            ).fetchone()

            conn.close()

        if not exists:
            return code


# =========================================================
# ADD GIVEAWAY
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and
    message.text == "➕ Add Giveaway"
)
def add_giveaway_start(message):
    admin_states[
        message.from_user.id
    ] = {
        "action": "add_reward"
    }

    bot.send_message(
        message.chat.id,
        "➕ <b>Create Giveaway</b>\n\n"
        "🎁 এখন যে <b>Reward / Token</b> দিতে চাও "
        "সেটা পাঠাও।\n\n"
        "উদাহরণ:\n"
        "<code>100 Points</code>\n\n"
        "অথবা:\n"
        "<code>Premium Access</code>\n\n"
        "❌ Cancel: /cancel"
    )


# =========================================================
# ACTIVE CODES
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and
    message.text == "📋 Active Codes"
)
def active_codes(message):
    with db_lock:
        conn = get_db()

        rows = conn.execute("""
            SELECT redeem_code, reward_text, created_at
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

    text = "📋 <b>ACTIVE CODES</b>\n\n"

    for i, row in enumerate(rows, 1):
        text += (
            f"{i}️⃣ <code>{row['redeem_code']}</code>\n"
            f"🎁 {row['reward_text']}\n\n"
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
    and
    message.text == "📊 Statistics"
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

        active = conn.execute("""
            SELECT COUNT(*)
            FROM giveaways
            WHERE status='active'
        """).fetchone()[0]

        used = conn.execute("""
            SELECT COUNT(*)
            FROM giveaways
            WHERE status='used'
        """).fetchone()[0]

        total_redeem = conn.execute(
            "SELECT COUNT(*) FROM redeem_history"
        ).fetchone()[0]

        today_users = conn.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE DATE(registered_at)=DATE('now')
        """).fetchone()[0]

        conn.close()

    bot.send_message(
        message.chat.id,
        "📊 <b>BOT STATISTICS</b>\n\n"
        f"👥 Total Users: <b>{total_users}</b>\n"
        f"🆕 Today's Users: <b>{today_users}</b>\n\n"
        f"🎁 Total Codes: <b>{total_codes}</b>\n"
        f"🟢 Active Codes: <b>{active}</b>\n"
        f"🔴 Used Codes: <b>{used}</b>\n"
        f"🔑 Total Redeems: <b>{total_redeem}</b>"
    )


# =========================================================
# BROADCAST
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and
    message.text == "📢 Broadcast"
)
def broadcast_start(message):
    admin_states[
        message.from_user.id
    ] = {
        "action": "broadcast"
    }

    bot.send_message(
        message.chat.id,
        "📢 <b>Broadcast Mode</b>\n\n"
        "যে Message সবাইকে পাঠাতে চাও সেটা পাঠাও।\n\n"
        "❌ Cancel: /cancel"
    )


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

    progress = bot.send_message(
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

        try:
            bot.copy_message(
                row["user_id"],
                message.chat.id,
                message.message_id
            )
            success += 1

        except Exception:
            failed += 1

        if (
            index == 1
            or index % 10 == 0
            or index == total
        ):
            percent = int(
                (index / total) * 100
            )

            try:
                bot.edit_message_text(
                    "📢 <b>Broadcast Running...</b>\n\n"
                    f"👥 Total: {total}\n"
                    f"📤 Sent: {success}\n"
                    f"❌ Failed: {failed}\n"
                    f"📊 Progress: {percent}%",
                    ADMIN_ID,
                    progress.message_id
                )
            except Exception:
                pass

        time.sleep(0.05)

    cancelled = not broadcast_running
    broadcast_running = False

    title = (
        "🛑 <b>Broadcast Cancelled</b>"
        if cancelled
        else
        "✅ <b>Broadcast Completed</b>"
    )

    try:
        bot.edit_message_text(
            f"{title}\n\n"
            f"👥 Total: {total}\n"
            f"📤 Sent: {success}\n"
            f"❌ Failed: {failed}",
            ADMIN_ID,
            progress.message_id
        )
    except Exception:
        pass


@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and
    message.text == "🛑 Cancel Broadcast"
)
def cancel_broadcast(message):
    global broadcast_running

    broadcast_running = False

    admin_states.pop(
        message.from_user.id,
        None
    )

    bot.send_message(
        message.chat.id,
        "🛑 <b>Broadcast Cancelled!</b>",
        reply_markup=admin_keyboard()
    )


# =========================================================
# DIRECT CHAT
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and
    message.text == "💬 Direct User Chat"
)
def direct_start(message):
    admin_states[
        message.from_user.id
    ] = {
        "action": "direct_user"
    }

    bot.send_message(
        message.chat.id,
        "💬 <b>Direct User Chat</b>\n\n"
        "User Telegram ID পাঠাও।\n\n"
        "Example:\n"
        "<code>123456789</code>\n\n"
        "❌ Cancel: /cancel"
    )


# =========================================================
# ADMIN INPUT
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

    if (
        message.text
        and
        message.text.strip().lower() == "/cancel"
    ):
        admin_states.pop(
            user_id,
            None
        )

        bot.send_message(
            user_id,
            "❌ <b>Cancelled.</b>",
            reply_markup=admin_keyboard()
        )
        return

    # -----------------------------------------------------
    # CREATE GIVEAWAY FROM REWARD
    # -----------------------------------------------------

    if action == "add_reward":

        reward = message.text.strip()

        if not reward:
            bot.send_message(
                user_id,
                "❌ Reward খালি হতে পারবে না।"
            )
            return

        code = generate_redeem_code()

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

        admin_states.pop(
            user_id,
            None
        )

        bot.send_message(
            user_id,
            "🎉 <b>Giveaway Created!</b>\n\n"
            f"🔑 <b>Redeem Code:</b>\n"
            f"<code>{code}</code>\n\n"
            f"🎁 <b>Reward:</b>\n"
            f"{reward}\n\n"
            "✅ এই Code এখন User-রা একবার করে Redeem করতে পারবে।",
            reply_markup=admin_keyboard()
        )

        return

    # -----------------------------------------------------
    # BROADCAST
    # -----------------------------------------------------

    if action == "broadcast":

        admin_states.pop(
            user_id,
            None
        )

        threading.Thread(
            target=run_broadcast,
            args=(message,),
            daemon=True
        ).start()

        return

    # -----------------------------------------------------
    # DIRECT USER ID
    # -----------------------------------------------------

    if action == "direct_user":

        try:
            target_id = int(
                message.text.strip()
            )
        except Exception:
            bot.send_message(
                user_id,
                "❌ সঠিক Telegram User ID দিন।"
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
            f"🆔 User: <code>{target_id}</code>\n\n"
            "এখন Message পাঠান।\n"
            "শেষ করতে /endchat"
        )

        return

    # -----------------------------------------------------
    # DIRECT MESSAGE
    # -----------------------------------------------------

    if action == "direct_message":

        if (
            message.text
            and
            message.text.strip().lower()
            == "/endchat"
        ):
            admin_states.pop(
                user_id,
                None
            )

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
# USER MESSAGE -> ADMIN
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.from_user.id != ADMIN_ID
)
def user_message(message):
    user_id = message.from_user.id

    if message.text and message.text.startswith("/"):
        return

    if not check_membership(user_id):
        send_force_join(user_id)
        return

    name = (
        message.from_user.first_name
        or
        "Unknown"
    )

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else
        "No Username"
    )

    header = (
        "📩 <b>USER MESSAGE</b>\n\n"
        f"👤 {name}\n"
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
                "📎 Non-text message received."
            )

    except Exception:
        pass


# =========================================================
# USER MENU
# =========================================================

@bot.message_handler(
    func=lambda message:
    is_admin(message.from_user.id)
    and
    message.text == "🏠 User Menu"
)
def user_menu(message):
    admin_states.pop(
        message.from_user.id,
        None
    )

    bot.send_message(
        message.chat.id,
        "🏠 <b>User Menu</b>",
        reply_markup=main_keyboard(
            message.from_user.id
        )
    )


# =========================================================
# END CHAT
# =========================================================

@bot.message_handler(commands=["endchat"])
def endchat(message):
    if not is_admin(message.from_user.id):
        return

    admin_states.pop(
        message.from_user.id,
        None
    )

    bot.send_message(
        message.chat.id,
        "✅ <b>Direct Chat Ended.</b>",
        reply_markup=admin_keyboard()
    )


# =========================================================
# USERS
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
            else
            "No Username"
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
# FLASK
# =========================================================

def run_flask():
    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    bot.infinity_polling(
        skip_pending=True,
        allowed_updates=[
            "message",
            "callback_query"
        ],
        timeout=30,
        long_polling_timeout=30
    )
