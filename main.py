import os
import logging
from pymongo import MongoClient
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# ---------------- CHECK ----------------
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")
if not MONGO_URI:
    raise ValueError("MONGO_URI missing")

# ---------------- DB ----------------
client = MongoClient(MONGO_URI)
db = client["network_bot"]

groups_col = db["groups"]
channels_col = db["channels"]
warns_col = db["warns"]

logging.basicConfig(level=logging.INFO)

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Connected Groups", callback_data="groups")],
        [InlineKeyboardButton("Connected Channels", callback_data="channels")]
    ]
    await update.message.reply_text(
        "Network Control Panel Active",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- PANEL ----------------
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "groups":
        groups = list(groups_col.find({}, {"_id": 0}))

        if not groups:
            await query.message.edit_text("No groups connected.\nSend @username or ID")
            context.user_data["mode"] = "add_group"
            return

        keyboard = []
        for g in groups:
            keyboard.append([
                InlineKeyboardButton(str(g["chat_id"]), callback_data="noop"),
                InlineKeyboardButton("❌", callback_data=f"remove_group_{g['chat_id']}")
            ])

        await query.message.edit_text(
            "Connected Groups:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "channels":
        channels = list(channels_col.find({}, {"_id": 0}))

        if not channels:
            await query.message.edit_text("No channels connected.\nSend @username or ID")
            context.user_data["mode"] = "add_channel"
            return

        keyboard = []
        for c in channels:
            keyboard.append([
                InlineKeyboardButton(str(c["chat_id"]), callback_data="noop"),
                InlineKeyboardButton("❌", callback_data=f"remove_channel_{c['chat_id']}")
            ])

        await query.message.edit_text(
            "Connected Channels:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ---------------- REMOVE ----------------
async def remove_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("remove_group_"):
        chat_id = int(data.split("_")[-1])
        groups_col.delete_one({"chat_id": chat_id})
        await query.message.edit_text("Group removed")

    elif data.startswith("remove_channel_"):
        chat_id = int(data.split("_")[-1])
        channels_col.delete_one({"chat_id": chat_id})
        await query.message.edit_text("Channel removed")

# ---------------- ADD ----------------
async def add_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    if not mode:
        return

    chat_input = update.message.text

    try:
        chat = await context.bot.get_chat(chat_input)

        member = await context.bot.get_chat_member(chat.id, update.effective_user.id)
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)

        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("You must be admin")
            return

        if bot_member.status not in ["administrator"]:
            await update.message.reply_text("Bot must be admin")
            return

        if mode == "add_group":
            groups_col.update_one({"chat_id": chat.id}, {"$set": {"chat_id": chat.id}}, upsert=True)
            await update.message.reply_text("Group connected")

        elif mode == "add_channel":
            channels_col.update_one({"chat_id": chat.id}, {"$set": {"chat_id": chat.id}}, upsert=True)
            await update.message.reply_text("Channel connected")

        context.user_data["mode"] = None

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# ---------------- GET ----------------
def get_all():
    groups = [g["chat_id"] for g in groups_col.find()]
    channels = [c["chat_id"] for c in channels_col.find()]
    return groups, channels

# ---------------- BAN ----------------
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = int(context.args[0])
    groups, channels = get_all()

    for chat in groups + channels:
        try:
            await context.bot.ban_chat_member(chat, target)
        except:
            pass

    await update.message.reply_text("Banned everywhere")

# ---------------- UNBAN ----------------
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = int(context.args[0])
    groups, channels = get_all()

    for chat in groups + channels:
        try:
            await context.bot.unban_chat_member(chat, target)
        except:
            pass

    await update.message.reply_text("Unbanned everywhere")

# ---------------- MUTE ----------------
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = int(context.args[0])
    groups, _ = get_all()

    perms = ChatPermissions(can_send_messages=False)

    for chat in groups:
        try:
            await context.bot.restrict_chat_member(chat, target, perms)
        except:
            pass

    await update.message.reply_text("Muted everywhere")

# ---------------- UNMUTE ----------------
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = int(context.args[0])
    groups, _ = get_all()

    perms = ChatPermissions(can_send_messages=True)

    for chat in groups:
        try:
            await context.bot.restrict_chat_member(chat, target, perms)
        except:
            pass

    await update.message.reply_text("Unmuted everywhere")

# ---------------- WARN ----------------
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = int(context.args[0])

    warns_col.update_one({"user_id": user}, {"$inc": {"count": 1}}, upsert=True)
    data = warns_col.find_one({"user_id": user})
    count = data["count"]

    if count >= 3:
        groups, _ = get_all()
        for chat in groups:
            try:
                await context.bot.ban_chat_member(chat, user)
            except:
                pass

        await update.message.reply_text("Auto banned (3 warns)")
    else:
        await update.message.reply_text(f"Warn: {count}")

# ---------------- LOCK ----------------
async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = context.args[0]
    groups, _ = get_all()

    perms = ChatPermissions()

    if arg == "all":
        perms = ChatPermissions(can_send_messages=False)

    for chat in groups:
        try:
            await context.bot.set_chat_permissions(chat, perms)
        except:
            pass

    await update.message.reply_text(f"Locked: {arg}")

# ---------------- BROADCAST ----------------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = " ".join(context.args)
    groups, channels = get_all()

    for chat in groups + channels:
        try:
            sent = await context.bot.send_message(chat, msg)
            await context.bot.pin_chat_message(chat, sent.message_id)
        except:
            pass

    await update.message.reply_text("Broadcast sent")

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(panel))
    app.add_handler(CallbackQueryHandler(remove_chat, pattern="^remove_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_chat))

    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("lock", lock))
    app.add_handler(CommandHandler("broadcast", broadcast))

    print("🔥 Network Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
