import os
import sqlite3
import secrets
import string
import threading
import time
from datetime import datetime, date
from functools import wraps

import telebot
from telebot import types
from flask import Flask


# =========================================================
# RAFIM GIVEAWAY BOT
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)

# New Channel + Group
CHANNEL_1 = os.getenv("CHANNEL_1", "@bdgiveaways24").strip()
GROUP_1 = os.getenv("GROUP_1", "@bdgivewaychat").strip()

SUPPORT_USERNAME = os.getenv(
    "SUPPORT_USERNAME",
    "rafimhossen"
).strip().lstrip("@")

DB_FILE = os.getenv("DB_FILE", "giveaway_bot.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

app = Flask(__name__)


# =========================================================
# FLASK / RENDER HEALTH
# =========================================================

@app.route("/")
def home():
    return "Giveaway Bot is running! ✅"


@app.route("/health")
def health():
    return "OK"


def run_flask():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


# =========================================================
# DATABASE
# =========================================================

db_lock = threading.Lock()


def db():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = db()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'bn',
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                alert_sent INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_lang (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'bn'
            )
        """)

        conn.execute("""
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                redeem_code TEXT NOT NULL,
                reward_text TEXT NOT NULL,
                redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message_text TEXT,
                total INTEGER DEFAULT 0,
                sent INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                banned_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()


init_db()


# =========================================================
# TRANSLATION
# IMPORTANT: tr() DOES NOT HAVE user_id KWARG CONFLICT
# =========================================================

TEXTS = {
    "welcome": {
        "bn": "👋 <b>স্বাগতম!</b>\n\n🎁 Giveaway Bot-এ তোমাকে স্বাগতম।",
        "en": "👋 <b>Welcome!</b>\n\n🎁 Welcome to the Giveaway Bot."
    },

    "join_required": {
        "bn": "🔒 <b>আগে Channel এবং Group-এ Join করুন।</b>\n\nতারপর নিচের <b>Verify</b> বাটনে চাপুন।",
        "en": "🔒 <b>Please join the Channel and Group first.</b>\n\nThen press <b>Verify</b>."
    },

    "join_success": {
        "bn": "✅ <b>Verification সফল!</b>\n\nএখন আপনি Bot ব্যবহার করতে পারবেন।",
        "en": "✅ <b>Verification successful!</b>\n\nYou can now use the bot."
    },

    "not_joined": {
        "bn": "❌ এখনো সব জায়গায় Join করা হয়নি।",
        "en": "❌ You have not joined all required places yet."
    },

    "redeem_prompt": {
        "bn": "🔑 আপনার Redeem Code পাঠান:",
        "en": "🔑 Send your Redeem Code:"
    },

    "invalid_code": {
        "bn": "❌ Code পাওয়া যায়নি অথবা এটি আর Active নেই।",
        "en": "❌ Code was not found or is no longer active."
    },

    "redeem_success": {
        "bn": "🎉 <b>Redeem Successful!</b>\n\n🎁 <b>Reward:</b>\n{reward}",
        "en": "🎉 <b>Redeem Successful!</b>\n\n🎁 <b>Reward:</b>\n{reward}"
    },

    "already_redeemed": {
        "bn": "⚠️ এই Code ইতিমধ্যে Redeem করা হয়েছে।",
        "en": "⚠️ This code has already been redeemed."
    },

    "daily": {
        "bn": "🎁 <b>Daily Giveaway</b>\n\nআজকের Active Giveaway:",
        "en": "🎁 <b>Daily Giveaway</b>\n\nToday's active giveaways:"
    },

    "no_giveaway": {
        "bn": "😔 বর্তমানে কোনো Active Giveaway নেই।",
        "en": "😔 There are no active giveaways right now."
    },

    "status": {
        "bn": "📊 <b>আমার স্ট্যাটাস</b>\n\n👤 ID: <code>{uid}</code>\n🎁 Redeemed: <b>{count}</b>",
        "en": "📊 <b>My Status</b>\n\n👤 ID: <code>{uid}</code>\n🎁 Redeemed: <b>{count}</b>"
    },

    "help": {
        "bn": "ℹ️ <b>Help</b>\n\n🔑 Redeem Code — Giveaway Code Redeem করুন\n🎁 Daily Giveaway — Active Giveaway দেখুন\n📊 My Status — আপনার তথ্য দেখুন\n⚙️ Settings — Language পরিবর্তন করুন\n\n🆘 Support: @{support}",
        "en": "ℹ️ <b>Help</b>\n\n🔑 Redeem Code — Redeem a giveaway code\n🎁 Daily Giveaway — View active giveaways\n📊 My Status — View your information\n⚙️ Settings — Change language\n\n🆘 Support: @{support}"
    }
}


def get_lang(uid):
    with db_lock:
        conn = db()
        row = conn.execute(
            "SELECT language FROM user_lang WHERE user_id=?",
            (uid,)
        ).fetchone()
        conn.close()

    if row and row["language"] in ("bn", "en"):
        return row["language"]

    return "bn"


def set_lang(uid, lang):
    with db_lock:
        conn = db()

        conn.execute("""
            INSERT INTO user_lang(user_id, language)
            VALUES(?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET language=excluded.language
        """, (uid, lang))

        conn.execute("""
            UPDATE users
            SET language=?
            WHERE user_id=?
        """, (lang, uid))

        conn.commit()
        conn.close()


def tr(uid, key, **kwargs):
    """
    IMPORTANT:
    uid is positional.
    Therefore calls such as:
        tr(user_id, "welcome")
    are safe.

    Also:
        tr(user_id, "redeem_success", reward="Netflix")
    is safe.

    There is NO duplicate user_id argument problem.
    """

    lang = get_lang(uid)

    item = TEXTS.get(key, {})

    text = item.get(lang) or item.get("bn") or key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass

    return text


# =========================================================
# USER FUNCTIONS
# =========================================================

def save_user(user):
    now = datetime.utcnow().isoformat()

    with db_lock:
        conn = db()

        existing = conn.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user.id,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE users
                SET username=?,
                    first_name=?,
                    last_name=?,
                    last_seen=?
                WHERE user_id=?
            """, (
                user.username or "",
                user.first_name or "",
                user.last_name or "",
                now,
                user.id
            ))
        else:
            lang = get_lang(user.id)

            conn.execute("""
                INSERT INTO users(
                    user_id,
                    username,
                    first_name,
                    last_name,
                    language,
                    joined_at,
                    last_seen
                )
                VALUES(?,?,?,?,?,?,?)
            """, (
                user.id,
                user.username or "",
                user.first_name or "",
                user.last_name or "",
                lang,
                now,
                now
            ))

        conn.commit()
        conn.close()


def is_banned(uid):
    with db_lock:
        conn = db()
        row = conn.execute(
            "SELECT user_id FROM banned_users WHERE user_id=?",
            (uid,)
        ).fetchone()
        conn.close()

    return row is not None


def is_admin(uid):
    return uid == ADMIN_ID


# =========================================================
# FORCE JOIN
# =========================================================

def check_member(chat_username, uid):
    try:
        member = bot.get_chat_member(chat_username, uid)

        return member.status in (
            "member",
            "administrator",
            "creator"
        )

    except Exception:
        return False


def joined_all(uid):
    return (
        check_member(CHANNEL_1, uid)
        and check_member(GROUP_1, uid)
    )


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


# =========================================================
# MAIN KEYBOARD
# =========================================================

def main_keyboard(uid):
    lang = get_lang(uid)

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    if lang == "bn":
        kb.row("🔑 কোড রিডিম", "⚙️ সেটিংস")
        kb.row("🎁 ডেইলি গিভঅ্যাওয়ে", "📊 আমার স্ট্যাটাস")
        kb.row("ℹ️ সাহায্য")
    else:
        kb.row("🔑 Redeem Code", "⚙️ Settings")
        kb.row("🎁 Daily Giveaway", "📊 My Status")
        kb.row("ℹ️ Help")

    if is_admin(uid):
        kb.row("👑 Admin Panel")

    return kb


def send_main_menu(message):
    uid = message.from_user.id

    bot.send_message(
        message.chat.id,
        tr(uid, "welcome"),
        reply_markup=main_keyboard(uid)
    )


# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def start_command(message):
    uid = message.from_user.id

    save_user(message.from_user)

    if is_banned(uid):
        bot.send_message(
            message.chat.id,
            "🚫 আপনার অ্যাকাউন্টটি বর্তমানে Block করা আছে।"
        )
        return

    if not joined_all(uid):
        bot.send_message(
            message.chat.id,
            tr(uid, "join_required"),
            reply_markup=join_keyboard()
        )
        return

    send_main_menu(message)


# =========================================================
# VERIFY
# =========================================================

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_join(call):
    uid = call.from_user.id

    if is_banned(uid):
        bot.answer_callback_query(
            call.id,
            "🚫 You are blocked.",
            show_alert=True
        )
        return

    if joined_all(uid):
        bot.answer_callback_query(
            call.id,
            "Verification successful!",
            show_alert=True
        )

        try:
            bot.edit_message_text(
                tr(uid, "join_success"),
                call.message.chat.id,
                call.message.message_id
            )
        except Exception:
            pass

        bot.send_message(
            call.message.chat.id,
            "🏠 Main Menu",
            reply_markup=main_keyboard(uid)
        )

        # New user admin alert
        with db_lock:
            conn = db()
            row = conn.execute(
                "SELECT alert_sent FROM users WHERE user_id=?",
                (uid,)
            ).fetchone()

            if row and row["alert_sent"] == 0:
                conn.execute(
                    "UPDATE users SET alert_sent=1 WHERE user_id=?",
                    (uid,)
                )
                conn.commit()
                should_alert = True
            else:
                should_alert = False

            conn.close()

        if should_alert and ADMIN_ID:
            username = (
                f"@{call.from_user.username}"
                if call.from_user.username
                else "No username"
            )

            try:
                bot.send_message(
                    ADMIN_ID,
                    "🆕 <b>New User Verified</b>\n\n"
                    f"👤 {username}\n"
                    f"🆔 <code>{uid}</code>"
                )
            except Exception:
                pass

    else:
        bot.answer_callback_query(
            call.id,
            tr(uid, "not_joined"),
            show_alert=True
        )


# =========================================================
# SETTINGS
# =========================================================

def settings_keyboard():
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


@bot.message_handler(
    func=lambda m: m.text in ("⚙️ সেটিংস", "⚙️ Settings")
)
def settings(message):
    bot.send_message(
        message.chat.id,
        "⚙️ <b>Language / ভাষা</b>",
        reply_markup=settings_keyboard()
    )


@bot.callback_query_handler(
    func=lambda call: call.data in ("lang_bn", "lang_en")
)
def change_language(call):
    lang = "bn" if call.data == "lang_bn" else "en"

    set_lang(call.from_user.id, lang)

    bot.answer_callback_query(
        call.id,
        "Language changed!"
    )

    bot.send_message(
        call.message.chat.id,
        "✅ Language updated.",
        reply_markup=main_keyboard(call.from_user.id)
    )


# =========================================================
# REDEEM STATE
# =========================================================

redeem_waiting = set()


@bot.message_handler(
    func=lambda m: m.text in (
        "🔑 কোড রিডিম",
        "🔑 Redeem Code"
    )
)
def redeem_start(message):
    uid = message.from_user.id

    redeem_waiting.add(uid)

    bot.send_message(
        message.chat.id,
        tr(uid, "redeem_prompt")
    )


@bot.message_handler(
    func=lambda m: m.from_user.id in redeem_waiting
)
def redeem_process(message):
    uid = message.from_user.id

    redeem_waiting.discard(uid)

    code = (message.text or "").strip().upper()

    with db_lock:
        conn = db()

        row = conn.execute("""
            SELECT *
            FROM giveaways
            WHERE redeem_code=?
              AND status='active'
        """, (code,)).fetchone()

        if not row:
            conn.close()

            bot.send_message(
                message.chat.id,
                tr(uid, "invalid_code")
            )
            return

        # Atomic one-time redemption
        cur = conn.execute("""
            UPDATE giveaways
            SET status='used',
                used_by=?,
                used_at=?
            WHERE redeem_code=?
              AND status='active'
        """, (
            uid,
            datetime.utcnow().isoformat(),
            code
        ))

        if cur.rowcount != 1:
            conn.rollback()
            conn.close()

            bot.send_message(
                message.chat.id,
                tr(uid, "already_redeemed")
            )
            return

        conn.execute("""
            INSERT INTO redemptions(
                user_id,
                redeem_code,
                reward_text
            )
            VALUES(?,?,?)
        """, (
            uid,
            code,
            row["reward_text"]
        ))

        conn.commit()
        conn.close()

    bot.send_message(
        message.chat.id,
        tr(
            uid,
            "redeem_success",
            reward=row["reward_text"]
        )
    )


# =========================================================
# DAILY GIVEAWAY
# =========================================================

@bot.message_handler(
    func=lambda m: m.text in (
        "🎁 ডেইলি গিভঅ্যাওয়ে",
        "🎁 Daily Giveaway"
    )
)
def daily_giveaway(message):
    uid = message.from_user.id

    with db_lock:
        conn = db()

        rows = conn.execute("""
            SELECT redeem_code, reward_text, category
            FROM giveaways
            WHERE status='active'
            ORDER BY id DESC
            LIMIT 20
        """).fetchall()

        conn.close()

    if not rows:
        bot.send_message(
            message.chat.id,
            tr(uid, "no_giveaway")
        )
        return

    text = tr(uid, "daily") + "\n\n"

    for i, row in enumerate(rows, 1):
        text += (
            f"🎁 <b>{i}. {row['category']}</b>\n"
            f"🔑 <code>{row['redeem_code']}</code>\n"
            f"🏆 {row['reward_text']}\n\n"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================================================
# MY STATUS
# =========================================================

@bot.message_handler(
    func=lambda m: m.text in (
        "📊 আমার স্ট্যাটাস",
        "📊 My Status"
    )
)
def my_status(message):
    uid = message.from_user.id

    with db_lock:
        conn = db()

        row = conn.execute("""
            SELECT COUNT(*) AS c
            FROM redemptions
            WHERE user_id=?
        """, (uid,)).fetchone()

        conn.close()

    bot.send_message(
        message.chat.id,
        tr(
            uid,
            "status",
            uid=uid,
            count=row["c"]
        )
    )


# =========================================================
# HELP
# =========================================================

@bot.message_handler(
    func=lambda m: m.text in (
        "ℹ️ সাহায্য",
        "ℹ️ Help"
    )
)
def help_command(message):
    bot.send_message(
        message.chat.id,
        tr(
            message.from_user.id,
            "help",
            support=SUPPORT_USERNAME
        )
    )


# =========================================================
# ADMIN STATE
# =========================================================

admin_state = {}


def admin_only(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if not is_admin(message.from_user.id):
            return

        return func(message, *args, **kwargs)

    return wrapper


def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    kb.row("🎁 Add Giveaway", "📋 Active Codes")
    kb.row("📊 Statistics", "📢 Broadcast")
    kb.row("❌ Cancel Broadcast", "💬 Direct User Chat")
    kb.row("👥 User Menu", "🏠 Main Menu")

    return kb


# =========================================================
# ADMIN COMMAND
# =========================================================

@bot.message_handler(commands=["admin"])
def admin_command(message):
    if not is_admin(message.from_user.id):
        return

    admin_state.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "👑 <b>Admin Panel</b>",
        reply_markup=admin_keyboard()
    )


@bot.message_handler(commands=["users"])
def users_command(message):
    if not is_admin(message.from_user.id):
        return

    with db_lock:
        conn = db()

        total = conn.execute(
            "SELECT COUNT(*) AS c FROM users"
        ).fetchone()["c"]

        conn.close()

    bot.send_message(
        message.chat.id,
        f"👥 <b>Total Users:</b> {total}"
    )


@bot.message_handler(commands=["cancel"])
def cancel_command(message):
    if not is_admin(message.from_user.id):
        return

    admin_state.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "❌ Cancelled.",
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADD GIVEAWAY
# =========================================================

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "🎁 Add Giveaway"
)
def add_giveaway_start(message):
    admin_state[message.from_user.id] = {
        "state": "reward"
    }

    bot.send_message(
        message.chat.id,
        "🎁 <b>Giveaway Reward/Token লিখুন:</b>\n\n"
        "উদাহরণ:\n"
        "<code>Netflix Premium 1 Month</code>"
    )


def generate_code():
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "GIVE-" + "".join(
            secrets.choice(alphabet)
            for _ in range(8)
        )

        with db_lock:
            conn = db()
            row = conn.execute(
                "SELECT id FROM giveaways WHERE redeem_code=?",
                (code,)
            ).fetchone()
            conn.close()

        if not row:
            return code


# =========================================================
# ACTIVE CODES
# =========================================================

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "📋 Active Codes"
)
def active_codes(message):
    with db_lock:
        conn = db()

        rows = conn.execute("""
            SELECT redeem_code, reward_text, category
            FROM giveaways
            WHERE status='active'
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()

        conn.close()

    if not rows:
        bot.send_message(
            message.chat.id,
            "📭 কোনো Active Code নেই।"
        )
        return

    text = "📋 <b>Active Codes</b>\n\n"

    for row in rows:
        text += (
            f"🔑 <code>{row['redeem_code']}</code>\n"
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
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "📊 Statistics"
)
def statistics(message):
    with db_lock:
        conn = db()

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

        redeemed = conn.execute(
            "SELECT COUNT(*) AS c FROM redemptions"
        ).fetchone()["c"]

        conn.close()

    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"🎁 Active Codes: <b>{active}</b>\n"
        f"✅ Used Codes: <b>{used}</b>\n"
        f"🔑 Total Redeems: <b>{redeemed}</b>"
    )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================================================
# DIRECT USER CHAT
# =========================================================

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "💬 Direct User Chat"
)
def direct_chat_start(message):
    admin_state[message.from_user.id] = {
        "state": "direct_user"
    }

    bot.send_message(
        message.chat.id,
        "💬 User ID পাঠান:"
    )


# =========================================================
# USER MENU
# =========================================================

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "👥 User Menu"
)
def user_menu(message):
    bot.send_message(
        message.chat.id,
        "👥 <b>User Management</b>\n\n"
        "ব্যবহার করুন:\n"
        "/users\n"
        "/ban USER_ID\n"
        "/unban USER_ID"
    )


# =========================================================
# BAN / UNBAN
# =========================================================

@bot.message_handler(commands=["ban"])
def ban_user(message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()

    if len(parts) != 2:
        bot.send_message(
            message.chat.id,
            "ব্যবহার: <code>/ban USER_ID</code>"
        )
        return

    try:
        uid = int(parts[1])
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Invalid User ID."
        )
        return

    with db_lock:
        conn = db()
        conn.execute("""
            INSERT OR IGNORE INTO banned_users(user_id)
            VALUES(?)
        """, (uid,))
        conn.commit()
        conn.close()

    bot.send_message(
        message.chat.id,
        f"🚫 User <code>{uid}</code> banned."
    )


@bot.message_handler(commands=["unban"])
def unban_user(message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()

    if len(parts) != 2:
        bot.send_message(
            message.chat.id,
            "ব্যবহার: <code>/unban USER_ID</code>"
        )
        return

    try:
        uid = int(parts[1])
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Invalid User ID."
        )
        return

    with db_lock:
        conn = db()
        conn.execute(
            "DELETE FROM banned_users WHERE user_id=?",
            (uid,)
        )
        conn.commit()
        conn.close()

    bot.send_message(
        message.chat.id,
        f"✅ User <code>{uid}</code> unbanned."
    )


# =========================================================
# ADMIN INPUT HANDLER
# IMPORTANT:
# It handles ONLY active admin states.
# Therefore /admin, /users etc. won't get swallowed.
# =========================================================

@bot.message_handler(
    func=lambda m: (
        is_admin(m.from_user.id)
        and m.from_user.id in admin_state
        and admin_state[m.from_user.id].get("state")
        in ("reward", "direct_user", "direct_message")
    )
)
def admin_state_handler(message):
    uid = message.from_user.id
    state = admin_state.get(uid, {}).get("state")

    # -----------------------------------------------------
    # ADD GIVEAWAY
    # -----------------------------------------------------

    if state == "reward":
        reward = (message.text or "").strip()

        if not reward:
            bot.send_message(
                message.chat.id,
                "❌ Reward empty হতে পারবে না।"
            )
            return

        code = generate_code()

        with db_lock:
            conn = db()

            conn.execute("""
                INSERT INTO giveaways(
                    redeem_code,
                    reward_text,
                    category,
                    status
                )
                VALUES(?,?,?,?)
            """, (
                code,
                reward,
                "Giveaway",
                "active"
            ))

            conn.commit()
            conn.close()

        admin_state.pop(uid, None)

        bot.send_message(
            message.chat.id,
            "✅ <b>Giveaway Created!</b>\n\n"
            f"🎁 Reward:\n{reward}\n\n"
            f"🔑 Code:\n<code>{code}</code>\n\n"
            "📢 এই Code ব্যবহার করে User একবার Redeem করতে পারবে।",
            reply_markup=admin_keyboard()
        )

        return

    # -----------------------------------------------------
    # DIRECT USER ID
    # -----------------------------------------------------

    if state == "direct_user":
        try:
            target_id = int(message.text.strip())
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ সঠিক User ID দিন।"
            )
            return

        admin_state[uid] = {
            "state": "direct_message",
            "target_id": target_id
        }

        bot.send_message(
            message.chat.id,
            f"💬 User <code>{target_id}</code>-কে যে Message পাঠাতে চান সেটি লিখুন:"
        )

        return

    # -----------------------------------------------------
    # DIRECT MESSAGE
    # -----------------------------------------------------

    if state == "direct_message":
        target_id = admin_state[uid].get("target_id")
        text = message.text or ""

        try:
            bot.send_message(
                target_id,
                "📩 <b>Message from Admin</b>\n\n" + text
            )

            bot.send_message(
                message.chat.id,
                "✅ Message sent."
            )

        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Message failed.\n<code>{str(e)[:500]}</code>"
            )

        admin_state.pop(uid, None)


# =========================================================
# BROADCAST
# =========================================================

broadcast_state = {}


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "📢 Broadcast"
)
def broadcast_start(message):
    broadcast_state[message.from_user.id] = {
        "running": False
    }

    bot.send_message(
        message.chat.id,
        "📢 <b>Broadcast Message পাঠান:</b>\n\n"
        "Cancel করতে /cancel লিখুন।"
    )

    broadcast_state[message.from_user.id]["waiting"] = True


@bot.message_handler(commands=["endchat"])
def end_chat(message):
    if not is_admin(message.from_user.id):
        return

    admin_state.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "💬 Direct chat ended."
    )


def perform_broadcast(admin_id, message_text, admin_chat_id):
    with db_lock:
        conn = db()

        rows = conn.execute(
            "SELECT user_id FROM users"
        ).fetchall()

        conn.close()

    total = len(rows)
    sent = 0
    failed = 0

    for row in rows:
        if not broadcast_state.get(admin_id, {}).get(
            "running",
            True
        ):
            break

        target = row["user_id"]

        try:
            bot.send_message(
                target,
                message_text
            )
            sent += 1

        except Exception:
            failed += 1

        time.sleep(0.05)

        if total:
            try:
                bot.send_message(
                    admin_chat_id,
                    f"📢 Broadcast Progress\n\n"
                    f"📊 {sent + failed}/{total}\n"
                    f"✅ Sent: {sent}\n"
                    f"❌ Failed: {failed}",
                    disable_notification=True
                )
            except Exception:
                pass

    with db_lock:
        conn = db()

        conn.execute("""
            INSERT INTO broadcast_history(
                admin_id,
                message_text,
                total,
                sent,
                failed
            )
            VALUES(?,?,?,?,?)
        """, (
            admin_id,
            message_text,
            total,
            sent,
            failed
        ))

        conn.commit()
        conn.close()

    broadcast_state.pop(admin_id, None)

    try:
        bot.send_message(
            admin_chat_id,
            "✅ <b>Broadcast Finished</b>\n\n"
            f"👥 Total: {total}\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}"
        )
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: (
        is_admin(m.from_user.id)
        and m.from_user.id in broadcast_state
        and broadcast_state[m.from_user.id].get("waiting") is True
    )
)
def broadcast_message(message):
    uid = message.from_user.id

    if message.text == "/cancel":
        broadcast_state.pop(uid, None)

        bot.send_message(
            message.chat.id,
            "❌ Broadcast cancelled.",
            reply_markup=admin_keyboard()
        )
        return

    text = message.text or ""

    broadcast_state[uid] = {
        "running": True,
        "waiting": False
    }

    bot.send_message(
        message.chat.id,
        "🚀 Broadcast started..."
    )

    thread = threading.Thread(
        target=perform_broadcast,
        args=(uid, text, message.chat.id),
        daemon=True
    )

    thread.start()


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "❌ Cancel Broadcast"
)
def cancel_broadcast(message):
    uid = message.from_user.id

    state = broadcast_state.get(uid)

    if state:
        state["running"] = False

    bot.send_message(
        message.chat.id,
        "🛑 Broadcast stopping..."
    )


# =========================================================
# ADMIN MAIN MENU BUTTON
# =========================================================

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "👑 Admin Panel"
)
def admin_panel_button(message):
    admin_command(message)


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id)
    and m.text == "🏠 Main Menu"
)
def main_menu_button(message):
    send_main_menu(message)


# =========================================================
# USER -> ADMIN DIRECT MESSAGE
# =========================================================

@bot.message_handler(
    func=lambda m: (
        m.from_user.id != ADMIN_ID
        and m.text
        and not m.text.startswith("/")
    )
)
def user_message_fallback(message):
    uid = message.from_user.id

    save_user(message.from_user)

    # Ignore known buttons
    known_buttons = {
        "🔑 কোড রিডিম",
        "🔑 Redeem Code",
        "⚙️ সেটিংস",
        "⚙️ Settings",
        "🎁 ডেইলি গিভঅ্যাওয়ে",
        "🎁 Daily Giveaway",
        "📊 আমার স্ট্যাটাস",
        "📊 My Status",
        "ℹ️ সাহায্য",
        "ℹ️ Help"
    }

    if message.text in known_buttons:
        return

    if is_banned(uid):
        return

    if not joined_all(uid):
        bot.send_message(
            message.chat.id,
            tr(uid, "join_required"),
            reply_markup=join_keyboard()
        )
        return

    if ADMIN_ID:
        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "No username"
        )

        try:
            bot.send_message(
                ADMIN_ID,
                "📩 <b>User Message</b>\n\n"
                f"👤 {username}\n"
                f"🆔 <code>{uid}</code>\n\n"
                f"💬 {message.text}"
            )
        except Exception:
            pass


# =========================================================
# HEALTH COMMAND
# =========================================================

@bot.message_handler(commands=["health"])
def health_command(message):
    if not is_admin(message.from_user.id):
        return

    bot.send_message(
        message.chat.id,
        "✅ Bot is running.\n"
        "🌐 Flask health server is active."
    )


# =========================================================
# ERROR-SAFE POLLING
# =========================================================

def start_bot():
    print("======================================")
    print("RAFIM GIVEAWAY BOT STARTING")
    print("======================================")
    print("Channel:", CHANNEL_1)
    print("Group:", GROUP_1)
    print("Admin:", ADMIN_ID)

    while True:
        try:
            print("Bot polling started...")

            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30,
                skip_pending=True,
                allowed_updates=[
                    "message",
                    "callback_query"
                ]
            )

        except Exception as e:
            print(
                "Polling error:",
                repr(e)
            )

            time.sleep(5)


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    start_bot()
