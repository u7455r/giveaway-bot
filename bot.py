# ============================================================
# RAFIM GIVEAWAY BOT
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
# ENVIRONMENT
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_ID_RAW = os.getenv("ADMIN_ID", "0").strip()

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except Exception:
    ADMIN_ID = 0

CHANNEL_1 = os.getenv("CHANNEL_1", "@bdgiveaways24").strip()
GROUP_1 = os.getenv("GROUP_1", "@bdgivewaychat").strip()

SUPPORT_USERNAME = (
    os.getenv("SUPPORT_USERNAME", "rafimhossen")
    .strip()
    .lstrip("@")
)

DB_FILE = os.getenv("DB_FILE", "giveaway_bot.db").strip()

PORT_RAW = os.getenv("PORT", "10000").strip()

try:
    PORT = int(PORT_RAW)
except Exception:
    PORT = 10000


# ============================================================
# BASIC VALIDATION
# ============================================================

print("=" * 60)
print("RAFIM GIVEAWAY BOT")
print("=" * 60)

print("Channel:", CHANNEL_1)
print("Group:", GROUP_1)
print("Admin:", ADMIN_ID)
print("Port:", PORT)

if not BOT_TOKEN:
    print()
    print("FATAL ERROR: BOT_TOKEN is missing.")
    print("Render Environment-এ BOT_TOKEN সেট করুন।")
    print("=" * 60)
    sys.exit(1)

if ADMIN_ID == 0:
    print()
    print("WARNING: ADMIN_ID is 0.")
    print("Admin panel কাজ করবে না যতক্ষণ সঠিক ADMIN_ID না দেওয়া হয়.")


# ============================================================
# BOT
# ============================================================

try:
    bot = telebot.TeleBot(
        BOT_TOKEN,
        parse_mode="HTML",
        threaded=True,
        num_threads=8
    )
except Exception as e:
    print("FATAL: Bot initialization failed:")
    print(repr(e))
    sys.exit(1)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Rafim Giveaway Bot is Running ✅", 200


@app.route("/health")
def health():
    return "OK", 200


# ============================================================
# DATABASE
# ============================================================

db_lock = threading.RLock()


def db_connect():
    conn = sqlite3.connect(
        DB_FILE,
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass

    return conn


def init_db():
    with db_lock:
        conn = db_connect()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'bn',
                banned INTEGER DEFAULT 0,
                joined_verified INTEGER DEFAULT 0,
                alert_sent INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redeem_code TEXT UNIQUE NOT NULL,
                reward_text TEXT NOT NULL,
                category TEXT DEFAULT 'Giveaway',
                status TEXT DEFAULT 'active',
                used_by INTEGER,
                used_at TEXT,
                created_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                redeem_code TEXT NOT NULL,
                reward_text TEXT NOT NULL,
                redeemed_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'bn',
                updated_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message_text TEXT,
                status TEXT DEFAULT 'running',
                total INTEGER DEFAULT 0,
                sent INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                created_at TEXT,
                finished_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                user_id INTEGER,
                error TEXT,
                created_at TEXT
            )
        """)

        conn.commit()
        conn.close()


# ============================================================
# TIME
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# DATABASE HELPERS
# ============================================================

def save_user(user):
    now = utc_now()

    with db_lock:
        conn = db_connect()

        conn.execute("""
            INSERT INTO users (
                user_id,
                username,
                first_name,
                last_name,
                language,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, 'bn', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                updated_at=excluded.updated_at
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            user.last_name or "",
            now,
            now
        ))

        conn.execute("""
            INSERT INTO user_settings(user_id, language, updated_at)
            VALUES (?, 'bn', ?)
            ON CONFLICT(user_id) DO NOTHING
        """, (user.id, now))

        conn.commit()
        conn.close()


def get_user(user_id):
    with db_lock:
        conn = db_connect()
        row = conn.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()
        conn.close()
        return row


def is_banned(user_id):
    row = get_user(user_id)
    return bool(row and row["banned"])


def set_banned(user_id, value):
    with db_lock:
        conn = db_connect()
        conn.execute(
            "UPDATE users SET banned=?, updated_at=? WHERE user_id=?",
            (1 if value else 0, utc_now(), user_id)
        )
        conn.commit()
        conn.close()


def get_language(user_id):
    with db_lock:
        conn = db_connect()

        row = conn.execute(
            "SELECT language FROM user_settings WHERE user_id=?",
            (user_id,)
        ).fetchone()

        conn.close()

    if row and row["language"]:
        return row["language"]

    return "bn"


def set_language(user_id, language):
    if language not in ("bn", "en"):
        language = "bn"

    with db_lock:
        conn = db_connect()

        conn.execute("""
            INSERT INTO user_settings(user_id, language, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                language=excluded.language,
                updated_at=excluded.updated_at
        """, (user_id, language, utc_now()))

        conn.execute(
            "UPDATE users SET language=?, updated_at=? WHERE user_id=?",
            (language, utc_now(), user_id)
        )

        conn.commit()
        conn.close()


# ============================================================
# TRANSLATION
# ============================================================

TEXTS = {
    "bn": {
        "welcome": (
            "🎉 <b>Rafim Giveaway Bot-এ স্বাগতম!</b>\n\n"
            "🎁 বিভিন্ন Giveaway Code Redeem করতে পারবেন।\n"
            "📢 আগে নিচের Channel ও Group-এ Join করুন।"
        ),

        "join_required":
            "🔒 <b>আগে আমাদের Channel এবং Group-এ Join করুন।</b>\n\n"
            "তারপর নিচের <b>✅ Verify</b> বাটনে চাপ দিন।",

        "verified":
            "🎉 <b>Verification সফল!</b>\n\n"
            "এখন আপনি Bot-এর সব সুবিধা ব্যবহার করতে পারবেন।",

        "verify_fail":
            "❌ এখনও সব জায়গায় Join করা হয়নি।\n\n"
            "দয়া করে Channel এবং Group দুটোতেই Join করে আবার Verify করুন।",

        "redeem_prompt":
            "🔑 <b>Redeem Code পাঠান:</b>\n\n"
            "উদাহরণ: <code>GIVE-XXXXXXX</code>",

        "invalid_code":
            "❌ এই Redeem Code সঠিক নয় অথবা ইতিমধ্যে ব্যবহার হয়ে গেছে।",

        "redeem_success":
            "🎉 <b>Redeem Successful!</b>\n\n"
            "🎁 আপনার Reward:\n<b>{reward}</b>\n\n"
            "✅ এই Code সফলভাবে Redeem হয়েছে।",

        "daily":
            "🎁 <b>Daily Giveaway</b>\n\n"
            "আজকের Giveaway পেতে Active Code ব্যবহার করুন।",

        "status":
            "📊 <b>My Status</b>\n\n"
            "🆔 User ID: <code>{user_id}</code>\n"
            "👤 Username: @{username}\n"
            "🎁 Redeemed: {count}",

        "help":
            "ℹ️ <b>Help</b>\n\n"
            "🔑 Redeem Code — Giveaway Code ব্যবহার করুন\n"
            "🎁 Daily Giveaway — দৈনিক Giveaway দেখুন\n"
            "📊 My Status — আপনার তথ্য দেখুন\n"
            "⚙️ Settings — Language পরিবর্তন করুন\n\n"
            "🆘 Support: @{support}",

        "language_changed":
            "✅ Language পরিবর্তন হয়েছে।",

        "banned":
            "🚫 আপনার অ্যাকাউন্টটি Bot থেকে নিষিদ্ধ করা হয়েছে।",

        "admin_only":
            "🚫 এই অপশন শুধুমাত্র Admin-এর জন্য।"
    },

    "en": {
        "welcome": (
            "🎉 <b>Welcome to Rafim Giveaway Bot!</b>\n\n"
            "🎁 You can redeem Giveaway Codes here.\n"
            "📢 Please join our Channel and Group first."
        ),

        "join_required":
            "🔒 <b>Please join our Channel and Group first.</b>\n\n"
            "Then press <b>✅ Verify</b>.",

        "verified":
            "🎉 <b>Verification successful!</b>\n\n"
            "You can now use all bot features.",

        "verify_fail":
            "❌ You have not joined all required places yet.\n\n"
            "Join both and press Verify again.",

        "redeem_prompt":
            "🔑 <b>Send your Redeem Code:</b>\n\n"
            "Example: <code>GIVE-XXXXXXX</code>",

        "invalid_code":
            "❌ Invalid or already-used Redeem Code.",

        "redeem_success":
            "🎉 <b>Redeem Successful!</b>\n\n"
            "🎁 Your Reward:\n<b>{reward}</b>\n\n"
            "✅ This code has been redeemed successfully.",

        "daily":
            "🎁 <b>Daily Giveaway</b>\n\n"
            "Use an active Giveaway Code to claim your reward.",

        "status":
            "📊 <b>My Status</b>\n\n"
            "🆔 User ID: <code>{user_id}</code>\n"
            "👤 Username: @{username}\n"
            "🎁 Redeemed: {count}",

        "help":
            "ℹ️ <b>Help</b>\n\n"
            "🔑 Redeem Code — Redeem a Giveaway Code\n"
            "🎁 Daily Giveaway — Daily Giveaway\n"
            "📊 My Status — Your information\n"
            "⚙️ Settings — Change language\n\n"
            "🆘 Support: @{support}",

        "language_changed":
            "✅ Language changed.",

        "banned":
            "🚫 Your account has been banned from this bot.",

        "admin_only":
            "🚫 Admin only."
    }
}


def tr(user_id, key, **kwargs):
    lang = get_language(user_id)

    if lang not in TEXTS:
        lang = "bn"

    text = TEXTS[lang].get(key, TEXTS["bn"].get(key, key))

    try:
        return text.format(**kwargs)
    except Exception:
        return text


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard(user_id):
    lang = get_language(user_id)

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    if lang == "en":
        kb.add(
            types.KeyboardButton("🔑 Redeem Code"),
            types.KeyboardButton("⚙️ Settings")
        )
        kb.add(
            types.KeyboardButton("🎁 Daily Giveaway"),
            types.KeyboardButton("📊 My Status")
        )
        kb.add(
            types.KeyboardButton("ℹ️ Help")
        )
    else:
        kb.add(
            types.KeyboardButton("🔑 কোড রিডিম"),
            types.KeyboardButton("⚙️ সেটিংস")
        )
        kb.add(
            types.KeyboardButton("🎁 ডেইলি গিভঅ্যাওয়ে"),
            types.KeyboardButton("📊 আমার স্ট্যাটাস")
        )
        kb.add(
            types.KeyboardButton("ℹ️ সাহায্য")
        )

    if user_id == ADMIN_ID:
        kb.add(types.KeyboardButton("🛠 Admin Panel"))

    return kb


def join_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)

    kb.add(
        types.InlineKeyboardButton(
            "📢 Join Channel",
            url="https://t.me/bdgiveaways24"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "👥 Join Group",
            url="https://t.me/bdgivewaychat"
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


def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    kb.add(
        types.KeyboardButton("🎁 Add Giveaway"),
        types.KeyboardButton("📋 Active Codes")
    )

    kb.add(
        types.KeyboardButton("📊 Statistics"),
        types.KeyboardButton("📢 Broadcast")
    )

    kb.add(
        types.KeyboardButton("❌ Cancel Broadcast"),
        types.KeyboardButton("💬 Direct User Chat")
    )

    kb.add(
        types.KeyboardButton("👤 User Menu"),
        types.KeyboardButton("🏠 Main Menu")
    )

    return kb


# ============================================================
# FORCE JOIN
# ============================================================

def check_member(chat_username, user_id):
    try:
        member = bot.get_chat_member(
            chat_username,
            user_id
        )

        return member.status in (
            "member",
            "administrator",
            "creator"
        )

    except Exception as e:
        print(
            f"Join check failed: "
            f"{chat_username} / {user_id} / {repr(e)}"
        )
        return False


def joined_all(user_id):
    channel_ok = check_member(
        CHANNEL_1,
        user_id
    )

    group_ok = check_member(
        GROUP_1,
        user_id
    )

    return channel_ok and group_ok


# ============================================================
# STATES
# ============================================================

user_states = {}
admin_states = {}

broadcast_cancel_event = threading.Event()


# ============================================================
# ADMIN CHECK
# ============================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


# ============================================================
# CODE GENERATOR
# ============================================================

def generate_code():
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "GIVE-" + "".join(
            secrets.choice(alphabet)
            for _ in range(8)
        )

        with db_lock:
            conn = db_connect()
            row = conn.execute(
                "SELECT id FROM giveaways WHERE redeem_code=?",
                (code,)
            ).fetchone()
            conn.close()

        if not row:
            return code


# ============================================================
# GIVEAWAY FUNCTIONS
# ============================================================

def create_giveaway(reward_text, category="Giveaway"):
    code = generate_code()

    with db_lock:
        conn = db_connect()

        conn.execute("""
            INSERT INTO giveaways (
                redeem_code,
                reward_text,
                category,
                status,
                created_at
            )
            VALUES (?, ?, ?, 'active', ?)
        """, (
            code,
            reward_text,
            category,
            utc_now()
        ))

        conn.commit()
        conn.close()

    return code


def redeem_code(user_id, code):
    code = code.strip().upper()

    with db_lock:
        conn = db_connect()

        try:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT *
                FROM giveaways
                WHERE redeem_code=?
                AND status='active'
                LIMIT 1
            """, (code,)).fetchone()

            if not row:
                conn.rollback()
                conn.close()
                return None

            updated = conn.execute("""
                UPDATE giveaways
                SET status='used',
                    used_by=?,
                    used_at=?
                WHERE id=?
                AND status='active'
            """, (
                user_id,
                utc_now(),
                row["id"]
            )).rowcount

            if updated != 1:
                conn.rollback()
                conn.close()
                return None

            conn.execute("""
                INSERT INTO redemptions (
                    user_id,
                    redeem_code,
                    reward_text,
                    redeemed_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                code,
                row["reward_text"],
                utc_now()
            ))

            conn.commit()

            reward = row["reward_text"]

            conn.close()

            return reward

        except Exception:
            conn.rollback()
            conn.close()
            raise


# ============================================================
# START
# ============================================================

@bot.message_handler(commands=["start"])
def start_command(message):
    try:
        save_user(message.from_user)

        uid = message.from_user.id

        if is_banned(uid):
            bot.send_message(
                message.chat.id,
                tr(uid, "banned")
            )
            return

        if not joined_all(uid):
            bot.send_message(
                message.chat.id,
                tr(uid, "join_required"),
                reply_markup=join_keyboard()
            )
            return

        with db_lock:
            conn = db_connect()

            conn.execute("""
                UPDATE users
                SET joined_verified=1,
                    updated_at=?
                WHERE user_id=?
            """, (utc_now(), uid))

            conn.commit()
            conn.close()

        bot.send_message(
            message.chat.id,
            tr(uid, "welcome"),
            reply_markup=main_keyboard(uid)
        )

        send_admin_join_alert(message.from_user)

    except Exception:
        print("START HANDLER ERROR:")
        traceback.print_exc()


# ============================================================
# ADMIN ALERT
# ============================================================

def send_admin_join_alert(user):
    if ADMIN_ID == 0:
        return

    try:
        with db_lock:
            conn = db_connect()

            row = conn.execute("""
                SELECT alert_sent
                FROM users
                WHERE user_id=?
            """, (user.id,)).fetchone()

            if not row:
                conn.close()
                return

            if row["alert_sent"]:
                conn.close()
                return

            conn.execute("""
                UPDATE users
                SET alert_sent=1,
                    updated_at=?
                WHERE user_id=?
            """, (utc_now(), user.id))

            conn.commit()
            conn.close()

        username = (
            f"@{user.username}"
            if user.username
            else "No username"
        )

        text = (
            "🎉 <b>New Verified User</b>\n\n"
            f"👤 {username}\n"
            f"🆔 <code>{user.id}</code>\n"
            f"📛 {user.first_name or ''}"
        )

        bot.send_message(
            ADMIN_ID,
            text
        )

    except Exception:
        traceback.print_exc()


# ============================================================
# VERIFY
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data == "verify_join"
)
def verify_join(call):
    uid = call.from_user.id

    try:
        save_user(call.from_user)

        if is_banned(uid):
            bot.answer_callback_query(
                call.id,
                "🚫 Banned"
            )
            return

        if joined_all(uid):
            with db_lock:
                conn = db_connect()

                conn.execute("""
                    UPDATE users
                    SET joined_verified=1,
                        updated_at=?
                    WHERE user_id=?
                """, (utc_now(), uid))

                conn.commit()
                conn.close()

            bot.answer_callback_query(
                call.id,
                "✅ Verified!"
            )

            try:
                bot.edit_message_text(
                    tr(uid, "verified"),
                    call.message.chat.id,
                    call.message.message_id
                )
            except Exception:
                pass

            bot.send_message(
                call.message.chat.id,
                tr(uid, "welcome"),
                reply_markup=main_keyboard(uid)
            )

            send_admin_join_alert(call.from_user)

        else:
            bot.answer_callback_query(
                call.id,
                "❌ Join both first",
                show_alert=True
            )

    except Exception:
        traceback.print_exc()


# ============================================================
# REDEEM
# ============================================================

@bot.message_handler(
    func=lambda m: m.text in (
        "🔑 কোড রিডিম",
        "🔑 Redeem Code"
    )
)
def redeem_button(message):
    uid = message.from_user.id

    if is_banned(uid):
        bot.send_message(
            message.chat.id,
            tr(uid, "banned")
        )
        return

    if not joined_all(uid):
        bot.send_message(
            message.chat.id,
            tr(uid, "join_required"),
            reply_markup=join_keyboard()
        )
        return

    user_states[uid] = "redeem"

    bot.send_message(
        message.chat.id,
        tr(uid, "redeem_prompt")
    )


# ============================================================
# DAILY
# ============================================================

@bot.message_handler(
    func=lambda m: m.text in (
        "🎁 ডেইলি গিভঅ্যাওয়ে",
        "🎁 Daily Giveaway"
    )
)
def daily_button(message):
    uid = message.from_user.id

    if is_banned(uid):
        bot.send_message(
            message.chat.id,
            tr(uid, "banned")
        )
        return

    bot.send_message(
        message.chat.id,
        tr(uid, "daily")
    )


# ============================================================
# STATUS
# ============================================================

@bot.message_handler(
    func=lambda m: m.text in (
        "📊 আমার স্ট্যাটাস",
        "📊 My Status"
    )
)
def status_button(message):
    uid = message.from_user.id

    with db_lock:
        conn = db_connect()

        row = conn.execute("""
            SELECT COUNT(*) AS total
            FROM redemptions
            WHERE user_id=?
        """, (uid,)).fetchone()

        conn.close()

    username = message.from_user.username or "none"

    bot.send_message(
        message.chat.id,
        tr(
            uid,
            "status",
            user_id=uid,
            username=username,
            count=row["total"]
        )
    )


# ============================================================
# HELP
# ============================================================

@bot.message_handler(
    func=lambda m: m.text in (
        "ℹ️ সাহায্য",
        "ℹ️ Help"
    )
)
def help_button(message):
    uid = message.from_user.id

    bot.send_message(
        message.chat.id,
        tr(
            uid,
            "help",
            support=SUPPORT_USERNAME
        )
    )


# ============================================================
# SETTINGS
# ============================================================

@bot.message_handler(
    func=lambda m: m.text in (
        "⚙️ সেটিংস",
        "⚙️ Settings"
    )
)
def settings_button(message):
    bot.send_message(
        message.chat.id,
        "🌐 <b>Select Language / ভাষা নির্বাচন করুন</b>",
        reply_markup=language_keyboard()
    )


@bot.callback_query_handler(
    func=lambda call: call.data in (
        "lang_bn",
        "lang_en"
    )
)
def language_callback(call):
    uid = call.from_user.id

    language = (
        "bn"
        if call.data == "lang_bn"
        else "en"
    )

    set_language(uid, language)

    bot.answer_callback_query(
        call.id,
        "✅"
    )

    bot.send_message(
        call.message.chat.id,
        tr(uid, "language_changed"),
        reply_markup=main_keyboard(uid)
    )


# ============================================================
# ADMIN PANEL
# ============================================================

@bot.message_handler(
    commands=["admin"]
)
def admin_command(message):
    if not is_admin(message.from_user.id):
        bot.send_message(
            message.chat.id,
            tr(message.from_user.id, "admin_only")
        )
        return

    bot.send_message(
        message.chat.id,
        "🛠 <b>Admin Panel</b>",
        reply_markup=admin_keyboard()
    )


@bot.message_handler(
    func=lambda m:
        m.text == "🛠 Admin Panel"
)
def admin_button(message):
    admin_command(message)


# ============================================================
# ADD GIVEAWAY
# ============================================================

@bot.message_handler(
    func=lambda m:
        m.text == "🎁 Add Giveaway"
)
def add_giveaway_button(message):
    if not is_admin(message.from_user.id):
        return

    admin_states[message.from_user.id] = "add_giveaway"

    bot.send_message(
        message.chat.id,
        "🎁 <b>Reward / Token Text পাঠান:</b>\n\n"
        "উদাহরণ:\n"
        "<code>Premium 7 Days</code>"
    )


# ============================================================
# ACTIVE CODES
# ============================================================

@bot.message_handler(
    func=lambda m:
        m.text == "📋 Active Codes"
)
def active_codes(message):
    if not is_admin(message.from_user.id):
        return

    with db_lock:
        conn = db_connect()

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
            "📭 কোনো Active Giveaway Code নেই।"
        )
        return

    text = "📋 <b>Active Giveaway Codes</b>\n\n"

    for row in rows:
        text += (
            f"🔑 <code>{row['redeem_code']}</code>\n"
            f"🎁 {row['reward_text']}\n\n"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# ============================================================
# STATISTICS
# ============================================================

@bot.message_handler(
    func=lambda m:
        m.text == "📊 Statistics"
)
def statistics(message):
    if not is_admin(message.from_user.id):
        return

    with db_lock:
        conn = db_connect()

        users = conn.execute(
            "SELECT COUNT(*) AS c FROM users"
        ).fetchone()["c"]

        active = conn.execute("""
            SELECT COUNT(*) AS c
            FROM giveaways
            WHERE status='active'
        """).fetchone()["c"]

        used = conn.execute("""
            SELECT COUNT(*) AS c
            FROM giveaways
            WHERE status='used'
        """).fetchone()["c"]

        redemptions = conn.execute(
            "SELECT COUNT(*) AS c FROM redemptions"
        ).fetchone()["c"]

        conn.close()

    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"🎁 Active Codes: <b>{active}</b>\n"
        f"✅ Used Codes: <b>{used}</b>\n"
        f"🔑 Redemptions: <b>{redemptions}</b>"
    )

    bot.send_message(
        message.chat.id,
        text
    )


# ============================================================
# USER MENU
# ============================================================

@bot.message_handler(
    func=lambda m:
        m.text == "👤 User Menu"
)
def user_menu(message):
    if not is_admin(message.from_user.id):
        return

    bot.send_message(
        message.chat.id,
        "👤 User Management\n\n"
        "ব্যবহার করুন:\n"
        "/users\n"
        "/ban USER_ID\n"
        "/unban USER_ID"
    )


# ============================================================
# USERS
# ============================================================

@bot.message_handler(
    commands=["users"]
)
def users_command(message):
    if not is_admin(message.from_user.id):
        return

    with db_lock:
        conn = db_connect()

        rows = conn.execute("""
            SELECT user_id, username, first_name, banned
            FROM users
            ORDER BY created_at DESC
            LIMIT 50
        """).fetchall()

        conn.close()

    if not rows:
        bot.send_message(
            message.chat.id,
            "📭 No users."
        )
        return

    text = "👥 <b>Users</b>\n\n"

    for row in rows:
        username = (
            "@" + row["username"]
            if row["username"]
            else "No username"
        )

        status = (
            "🚫 Banned"
            if row["banned"]
            else "✅ Active"
        )

        text += (
            f"🆔 <code>{row['user_id']}</code>\n"
            f"👤 {username}\n"
            f"📛 {row['first_name'] or ''}\n"
            f"{status}\n\n"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# ============================================================
# BAN / UNBAN
# ============================================================

@bot.message_handler(
    commands=["ban", "unban"]
)
def ban_command(message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()

    if len(parts) != 2:
        bot.send_message(
            message.chat.id,
            "ব্যবহার:\n"
            "/ban USER_ID\n"
            "/unban USER_ID"
        )
        return

    try:
        uid = int(parts[1])
    except Exception:
        bot.send_message(
            message.chat.id,
            "❌ Invalid User ID."
        )
        return

    value = message.text.startswith("/ban")

    set_banned(uid, value)

    bot.send_message(
        message.chat.id,
        "🚫 User banned."
        if value
        else "✅ User unbanned."
    )


# ============================================================
# DIRECT CHAT
# ============================================================

@bot.message_handler(
    func=lambda m:
        m.text == "💬 Direct User Chat"
)
def direct_chat_button(message):
    if not is_admin(message.from_user.id):
        return

    admin_states[message.from_user.id] = "direct_user_id"

    bot.send_message(
        message.chat.id,
        "💬 যে User ID-তে message পাঠাতে চান সেটি পাঠান।"
    )


# ============================================================
# END CHAT
# ============================================================

@bot.message_handler(
    commands=["endchat"]
)
def endchat_command(message):
    admin_states.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "✅ Direct Chat বন্ধ হয়েছে।"
    )


# ============================================================
# BROADCAST
# ============================================================

@bot.message_handler(
    func=lambda m:
        m.text == "📢 Broadcast"
)
def broadcast_button(message):
    if not is_admin(message.from_user.id):
        return

    admin_states[message.from_user.id] = "broadcast"

    broadcast_cancel_event.clear()

    bot.send_message(
        message.chat.id,
        "📢 <b>Broadcast Message পাঠান:</b>\n\n"
        "Cancel করতে /cancel লিখুন।"
    )


@bot.message_handler(
    func=lambda m:
        m.text == "❌ Cancel Broadcast"
)
def cancel_broadcast_button(message):
    if not is_admin(message.from_user.id):
        return

    broadcast_cancel_event.set()

    bot.send_message(
        message.chat.id,
        "⛔ Broadcast cancel signal পাঠানো হয়েছে।"
    )


@bot.message_handler(
    commands=["cancel"]
)
def cancel_command(message):
    if not is_admin(message.from_user.id):
        return

    admin_states.pop(message.from_user.id, None)

    broadcast_cancel_event.set()

    bot.send_message(
        message.chat.id,
        "❌ Current operation cancelled."
    )


def run_broadcast(admin_id, message_text, status_chat_id):
    broadcast_cancel_event.clear()

    with db_lock:
        conn = db_connect()

        users = conn.execute("""
            SELECT user_id
            FROM users
            WHERE banned=0
            ORDER BY user_id
        """).fetchall()

        cur = conn.execute("""
            INSERT INTO broadcast_jobs (
                admin_id,
                message_text,
                status,
                total,
                created_at
            )
            VALUES (?, ?, 'running', ?, ?)
        """, (
            admin_id,
            message_text,
            len(users),
            utc_now()
        ))

        job_id = cur.lastrowid

        conn.commit()
        conn.close()

    sent = 0
    failed = 0

    total = len(users)

    for index, row in enumerate(users, start=1):

        if broadcast_cancel_event.is_set():
            status = "cancelled"
            break

        uid = row["user_id"]

        try:
            bot.send_message(
                uid,
                message_text
            )

            sent += 1

        except Exception as e:
            failed += 1

            with db_lock:
                conn = db_connect()

                conn.execute("""
                    INSERT INTO broadcast_failures (
                        job_id,
                        user_id,
                        error,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    job_id,
                    uid,
                    str(e)[:1000],
                    utc_now()
                ))

                conn.commit()
                conn.close()

        if index % 10 == 0 or index == total:
            try:
                bot.send_message(
                    status_chat_id,
                    "📢 <b>Broadcast Progress</b>\n\n"
                    f"📊 Total: {total}\n"
                    f"✅ Sent: {sent}\n"
                    f"❌ Failed: {failed}\n"
                    f"📈 Progress: {index}/{total}"
                )
            except Exception:
                pass

        time.sleep(0.05)

    else:
        status = "completed"

    with db_lock:
        conn = db_connect()

        conn.execute("""
            UPDATE broadcast_jobs
            SET status=?,
                sent=?,
                failed=?,
                finished_at=?
            WHERE id=?
        """, (
            status,
            sent,
            failed,
            utc_now(),
            job_id
        ))

        conn.commit()
        conn.close()

    try:
        bot.send_message(
            status_chat_id,
            "📢 <b>Broadcast Finished</b>\n\n"
            f"📊 Total: {total}\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}\n"
            f"📌 Status: {status}"
        )
    except Exception:
        pass


# ============================================================
# MAIN TEXT HANDLER
# ============================================================

@bot.message_handler(
    content_types=["text"]
)
def text_handler(message):
    uid = message.from_user.id
    text = (message.text or "").strip()

    try:
        save_user(message.from_user)

        if is_banned(uid):
            bot.send_message(
                message.chat.id,
                tr(uid, "banned")
            )
            return

        # -----------------------------
        # ADMIN STATES
        # -----------------------------

        if is_admin(uid):

            state = admin_states.get(uid)

            if state == "add_giveaway":
                if text.startswith("/"):
                    return

                code = create_giveaway(text)

                admin_states.pop(uid, None)

                bot.send_message(
                    message.chat.id,
                    "🎉 <b>Giveaway Created!</b>\n\n"
                    f"🔑 Code:\n<code>{code}</code>\n\n"
                    f"🎁 Reward:\n{text}",
                    reply_markup=admin_keyboard()
                )
                return

            if state == "direct_user_id":
                try:
                    target_id = int(text)

                    admin_states[uid] = (
                        "direct_message",
                        target_id
                    )

                    bot.send_message(
                        message.chat.id,
                        "💬 এখন যে message পাঠাতে চান সেটি লিখুন।"
                    )

                except Exception:
                    bot.send_message(
                        message.chat.id,
                        "❌ সঠিক User ID দিন।"
                    )

                return

            if (
                isinstance(state, tuple)
                and state[0] == "direct_message"
            ):
                target_id = state[1]

                try:
                    bot.send_message(
                        target_id,
                        "📩 <b>Message from Admin</b>\n\n"
                        + text
                    )

                    bot.send_message(
                        message.chat.id,
                        "✅ Message পাঠানো হয়েছে।"
                    )

                except Exception as e:
                    bot.send_message(
                        message.chat.id,
                        "❌ Message পাঠানো যায়নি:\n"
                        + str(e)[:500]
                    )

                admin_states.pop(uid, None)
                return

            if state == "broadcast":
                if text == "/cancel":
                    admin_states.pop(uid, None)
                    broadcast_cancel_event.set()
                    return

                admin_states.pop(uid, None)

                bot.send_message(
                    message.chat.id,
                    "📢 Broadcast শুরু হচ্ছে..."
                )

                thread = threading.Thread(
                    target=run_broadcast,
                    args=(
                        uid,
                        text,
                        message.chat.id
                    ),
                    daemon=True
                )

                thread.start()
                return

        # -----------------------------
        # USER REDEEM STATE
        # -----------------------------

        if user_states.get(uid) == "redeem":

            user_states.pop(uid, None)

            reward = redeem_code(
                uid,
                text
            )

            if reward is None:
                bot.send_message(
                    message.chat.id,
                    tr(uid, "invalid_code")
                )
                return

            bot.send_message(
                message.chat.id,
                tr(
                    uid,
                    "redeem_success",
                    reward=reward
                )
            )
            return

        # -----------------------------
        # NORMAL FALLBACK
        # -----------------------------

        if text.startswith("/"):
            return

        bot.send_message(
            message.chat.id,
            tr(uid, "welcome"),
            reply_markup=main_keyboard(uid)
        )

    except Exception:
        print("TEXT HANDLER ERROR:")
        traceback.print_exc()

        try:
            bot.send_message(
                message.chat.id,
                "⚠️ একটি সাময়িক সমস্যা হয়েছে। আবার চেষ্টা করুন।"
            )
        except Exception:
            pass


# ============================================================
# ADMIN -> USER REPLY / USER -> ADMIN SUPPORT
# ============================================================

@bot.message_handler(
    func=lambda m:
        m.chat.id != ADMIN_ID and
        m.reply_to_message is not None and
        m.reply_to_message.from_user is not None and
        m.reply_to_message.from_user.id == ADMIN_ID
)
def user_reply_to_admin(message):
    try:
        bot.forward_message(
            ADMIN_ID,
            message.chat.id,
            message.message_id
        )
    except Exception:
        pass


# ============================================================
# TELEGRAM API VALIDATION
# ============================================================

def validate_telegram():
    print()
    print("Checking Telegram API...")

    try:
        me = bot.get_me()

        print("Telegram API: OK")
        print(
            f"Bot: @{me.username} "
            f"(ID: {me.id})"
        )

        return True

    except Exception as e:
        print()
        print("!!! TELEGRAM API ERROR !!!")
        print(repr(e))
        print()

        error_text = str(e)

        if "401" in error_text:
            print(
                "CAUSE: BOT_TOKEN is invalid, "
                "expired or revoked."
            )

        elif "409" in error_text:
            print(
                "CAUSE: Another instance of this bot "
                "is already using getUpdates."
            )

        else:
            print(
                "CAUSE: Telegram API connection/configuration problem."
            )

        print("=" * 60)

        return False


# ============================================================
# FLASK SERVER
# ============================================================

def run_flask():
    try:
        print(
            f"Starting Flask on 0.0.0.0:{PORT}"
        )

        app.run(
            host="0.0.0.0",
            port=PORT,
            debug=False,
            use_reloader=False,
            threaded=True
        )

    except Exception:
        print("FLASK ERROR:")
        traceback.print_exc()


# ============================================================
# TELEGRAM POLLING
# ============================================================

def run_polling():
    print()
    print("Preparing Telegram polling...")

    try:
        # Remove webhook before polling.
        try:
            bot.delete_webhook(
                drop_pending_updates=True
            )
            print("Webhook removed successfully.")
        except Exception as e:
            print(
                "Webhook removal warning:",
                repr(e)
            )

        # Validate token before polling.
        if not validate_telegram():
            print()
            print(
                "Bot polling NOT started because "
                "Telegram API validation failed."
            )
            return

        print()
        print("Bot polling started...")
        print("Waiting for Telegram updates...")
        print("=" * 60)

        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=30,
            skip_pending=True,
            allowed_updates=[
                "message",
                "callback_query"
            ],
            logger_level=20
        )

    except Exception as e:
        print()
        print("POLLING ERROR:")
        print(repr(e))
        traceback.print_exc()

        # Do not silently pretend the bot is running.
        # Retry only for temporary errors.
        time.sleep(5)

        try:
            print("Retrying Telegram polling...")
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30,
                skip_pending=True,
                allowed_updates=[
                    "message",
                    "callback_query"
                ],
                logger_level=20
            )

        except Exception:
            print("SECOND POLLING ATTEMPT FAILED:")
            traceback.print_exc()


# ============================================================
# STARTUP
# ============================================================

def main():
    print()
    print("=" * 60)
    print("RAFIM GIVEAWAY BOT STARTING")
    print("=" * 60)

    # Database first.
    try:
        init_db()
        print("Database: OK")
    except Exception as e:
        print("DATABASE ERROR:")
        print(repr(e))
        traceback.print_exc()
        sys.exit(1)

    # Start Flask in background.
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    # Give Flask a moment to bind.
    time.sleep(2)

    # Telegram polling stays in main thread.
    run_polling()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
