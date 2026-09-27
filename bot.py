import telebot
import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ⚠️ শুধুমাত্র এই ৪টি তথ্য আপনার অরিজিনাল ডাটা দিয়ে পরিবর্তন করুন
BOT_TOKEN = "8668420820:AAFqB7lZmKJOA6nMFMSp5Ur-2JxEWbfwFwo"
ADMIN_ID = 8298133943  # @userinfobot থেকে আপনার নিজের আইডি বসান
CHANNEL_1 = "@hacksmethod6"    # Hacks Method Chat
CHANNEL_2 = "@rafimhossen3"    # Hacks Method

# 🖼️ প্রিমিয়াম হাই-কোয়ালিটি লোগো বা ছবির ইউআরএল (Visual Anchors)
LOGOS = {
    "MAIN": "https://unsplash.com", 
    "Netflix": "https://ctfassets.net",
    "Amazon": "https://wikimedia.org",
    "Prime Video": "https://wikimedia.org",
    "ChatGPT": "https://wikimedia.org",
    "Other": "https://unsplash.com"
}

bot = telebot.TeleBot(BOT_TOKEN)

# ডাটাবেজ টেবিল অটো-সেটআপ
def init_db():
    conn = sqlite3.connect("premium_giveaway.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            redeem_code TEXT UNIQUE,
            cookie_text TEXT,
            category TEXT,
            status TEXT DEFAULT 'Unused'
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

# ইউজারের ভাষা ডেটাবেজ থেকে রিড করার ফাংশন
def get_user_lang(user_id):
    conn = sqlite3.connect("premium_giveaway.db")
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM user_lang WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'bn'

# ইউজারের ভাষা আপডেট করার ফাংশন
def set_user_lang(user_id, lang):
    conn = sqlite3.connect("premium_giveaway.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO user_lang (user_id, lang) VALUES (?, ?)", (user_id, lang))
    conn.commit()
    conn.close()

# ফোর্সমোড চ্যানেল জয়েনিং ভেরিফায়ার
def is_user_subscribed(user_id):
    try:
        member1 = bot.get_chat_member(CHANNEL_1, user_id)
        is_in_ch1 = member1.status in ['creator', 'administrator', 'member']
        member2 = bot.get_chat_member(CHANNEL_2, user_id)
        is_in_ch2 = member2.status in ['creator', 'administrator', 'member']
        return is_in_ch1 and is_in_ch2
    except:
        return False

admin_states = {}

# 🛠️ পার্মানেন্ট রিপ্লাই কিবোর্ড (বটের নিচে স্থায়ী মেনু বাটন)
def get_reply_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("🔑 Redeem Code / কোড রিডিম"), KeyboardButton("⚙️ Settings / সেটিংস"))
    return keyboard

# ১. স্টার্ট কমান্ড হ্যান্ডলার (/start)
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add New Cookie", callback_data="admin_add"))
        markup.row(InlineKeyboardButton("🛠️ Edit / Delete Active Codes", callback_data="admin_edit"))
        welcome_text = "⚡ **WELCOME BACK, SUPREME LEADER!** ⚡\n\n🔥 অ্যাডমিন ড্যাশবোর্ড সম্পূর্ণ প্রস্তুত। ডেটাবেজে নতুন কুকি বোমা ফিট করতে নিচের প্যানেল ব্যবহার করুন:"
        bot.send_photo(message.chat.id, LOGOS["MAIN"], caption=welcome_text, reply_markup=markup, parse_mode="Markdown")
        return

    # সাধারণ ইউজারের ক্ষেত্রে ইনস্ট্যান্ট সাবস্ক্রিপশন গার্ড
    if not is_user_subscribed(user_id):
        send_force_join_menu(message.chat.id)
        return

    # জয়েন থাকলে মেইন ইন্টারফেস লোড হবে এবং পার্মানেন্ট মেনু বাটন সেট হবে
    lang = get_user_lang(user_id)
    if lang == 'bn':
        msg = "💎 **প্রিমিয়াম কুকি ভল্ট আনলকড!** 💎\n\nনিচের কিবোর্ড মেনু ব্যবহার করে আপনার কার্যক্রম সিলেক্ট করুন অথবা সরাসরি রিডিম কোডটি চ্যাটে টাইপ করে ফায়ার করুন!"
    else:
        msg = "💎 **PREMIUM COOKIE VAULT UNLOCKED!** 💎\n\nUse the keyboard menu below to select your operation or directly type your Redeem Code in the chat to fire!"
        
    bot.send_photo(message.chat.id, LOGOS["MAIN"], caption=msg, reply_markup=get_reply_keyboard(), parse_mode="Markdown")

# ফোর্স জয়েনিং মেনু মেসেজ মেকার (বাংলা + ইংলিশ হ্যাকার অ্যালার্ট টোন)
def send_force_join_menu(chat_id):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("💬 Join Chat Channel", url=f"https://t.me{CHANNEL_1.replace('@', '')}"))
    markup.row(InlineKeyboardButton("📢 Join Main Channel", url=f"https://t.me{CHANNEL_2.replace('@', '')}"))
    markup.row(InlineKeyboardButton("🔄 Verify Membership / ভেরিফাই করুন", callback_data="check_again"))
    
    alert_msg = (
        "🚨 **SECURITY ALERT / সিকিউরিটি অ্যালার্ট** 🚨\n\n"
        "🇺🇸 *English:*\n"
        "**Access Denied!** You have not joined our mandatory channels yet. "
        "Or did you just try to hack/bypass this system? 🤨 Nice try, but it won't work! "
        "Join both channels above and tap Verify to unlock the premium vault.\n\n"
        "🇧🇩 *বাংলা:*\n"
        "**অ্যাক্সেসড ব্লকড!** আপনি এখনো আমাদের চ্যানেলগুলোতে জয়েন করেননি। "
        "নাকি আপনি বট হ্যাক করে প্রিমিয়াম কুকি বাইপাস করার চেষ্টা করছেন? 🤨 চেষ্টা ভালো ছিল, কিন্তু ডাল গলবে না ভাই! "
        "উপরে দেওয়া দুটি চ্যানেলে দ্রুত জয়েন করে নিচের ভেরিফাই বাটনে চাপ দিন।"
    )
    bot.send_message(chat_id, alert_msg, reply_markup=markup, parse_mode="Markdown")

# ২. ইনলাইন বাটনের ক্লিকের রেসপন্স হ্যান্ডলার (Callback Query)
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    user_id = call.from_user.id
    
    # মেম্বারশিপ রি-ভেরিফিকেশন চেক বাটন
    if call.data == "check_again":
        if is_user_subscribed(user_id):
            bot.answer_callback_query(call.id, "✅ Verified Successfully! / ভেরিফিকেশন সফল!")
            lang = get_user_lang(user_id)
            if lang == 'bn':
                msg = "🎉 অ্যাক্সেস গ্রান্টেড! আপনি সিকিউরিটি ওয়াল সফলভাবে পার করেছেন।"
            else:
                msg = "🎉 Access Granted! You passed the security wall successfully."
            bot.send_message(call.message.chat.id, msg, reply_markup=get_reply_keyboard())
        else:
            bot.answer_callback_query(call.id, "❌ Still not joined! / এখনও জয়েন করেননি!", show_alert=True)
        return

    # ভাষা পরিবর্তনের বাটন হ্যান্ডলার
    if call.data.startswith("setlang_"):
        selected_lang = call.data.split("_")[1]
        set_user_lang(user_id, selected_lang)
        if selected_lang == 'bn':
            bot.answer_callback_query(call.id, "🇧🇩 ভাষা পরিবর্তন সম্পন্ন!")
            bot.send_message(call.message.chat.id, "⚙️ বটের ভাষা সফলভাবে **বাংলা** করা হয়েছে। এখন থেকে সকল কমান্ড বাংলায় রেসপন্স করবে।", reply_markup=get_reply_keyboard())
        else:
            bot.answer_callback_query(call.id, "🇺🇸 Language Updated!")
            bot.send_message(call.message.chat.id, "⚙️ Bot interface switched to **English** successfully. All actions will now respond in English.", reply_markup=get_reply_keyboard())
        return

    # 🔒 এডমিন কমান্ড সিকিউরিটি প্রোটেকশন
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ System Overridden! Admin privilege required.")
        return

    if call.data == "admin_add":
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🍿 Netflix Premium", callback_data="setcat_Netflix"))
        markup.row(InlineKeyboardButton("🛒 Amazon.in Premium", callback_data="setcat_Amazon"))
        markup.row(InlineKeyboardButton("🎬 Prime Video", callback_data="setcat_Prime Video"))
        markup.row(InlineKeyboardButton("🤖 ChatGPT Plus", callback_data="setcat_ChatGPT"))
        markup.row(InlineKeyboardButton("🛡️ Other Custom", callback_data="setcat_Other"))
        bot.send_message(call.message.chat.id, "📁 **Boss, choose the target platform/category:**", reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data.startswith("setcat_"):
        selected_category = call.data.split("_")[1]
        admin_states[user_id] = {"category": selected_category, "step": "waiting_for_code_cookie"}
        prompt_msg = (
            f"📥 **TARGET PLUGGED:** `{selected_category}`\n\n✍️ **বস, এবার আপনার সিক্রেট কোড এবং কুকি ড্রপ করুন:**\n"
            f"নিচের রাফ ফরম্যাটে ডিরেক্ট মেসেজ দিন, ডাটাবেজ লক করে নেবে:\n\n`[কোড] [স্পেস] [কুকি-টেক্সট]`\n\n"
            f"💡 *Example:* `NF-LOOT-7799 netflix_cookie_data_here...`"
        )
        bot.send_photo(call.message.chat.id, LOGOS.get(selected_category, LOGOS["Other"]), caption=prompt_msg, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data == "admin_edit":
        conn = sqlite3.connect("premium_giveaway.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, redeem_code, category FROM keys WHERE status = 'Unused' ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "📭 ডাটাবেজে বর্তমানে কোনো লাইভ কোড নেই, বস!")
            bot.answer_callback_query(call.id)
            return
        markup = InlineKeyboardMarkup()
        for row in rows:
            markup.row(InlineKeyboardButton(f"🗑️ Wipe {row[1]} - {row[2]}", callback_data=f"del_{row[0]}"))
        bot.send_message(call.message.chat.id, "🛠️ **LIVE CODES DATABASE:**\nযেকোনো কোড চিরতরে মুছে ফেলতে তার পাশের বাটনে ক্লিক করুন:", reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data.startswith("del_"):
        db_id = call.data.split("_")[1]
