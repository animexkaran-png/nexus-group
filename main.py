import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

DATA_FILE = "data.json"

print("🔥 Starting Bot...")

logging.basicConfig(level=logging.INFO)

# ---------------- FILE DB ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"groups": [], "channels": []}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Connected Groups", callback_data="groups")],
        [InlineKeyboardButton("Connected Channels", callback_data="channels")]
    ]
    await update.message.reply_text(
        "Network Control Panel Active 🚀",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- PANEL ----------------
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()

    if query.data == "groups":
        groups = data["groups"]

        if not groups:
            context.user_data["mode"] = "add_group"
            await query.message.edit_text("No groups connected.\nSend @username or ID")
            return

        keyboard = []
        for g in groups:
            keyboard.append([
                InlineKeyboardButton(str(g), callback_data="noop"),
                InlineKeyboardButton("❌", callback_data=f"remove_group_{g}")
            ])

        await query.message.edit_text("Connected Groups:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "channels":
        channels = data["channels"]

        if not channels:
            context.user_data["mode"] = "add_channel"
            await query.message.edit_text("No channels connected.\nSend @username or ID")
            return

        keyboard = []
        for c in channels:
            keyboard.append([
                InlineKeyboardButton(str(c), callback_data="noop"),
                InlineKeyboardButton("❌", callback_data=f"remove_channel_{c}")
            ])

        await query.message.edit_text("Connected Channels:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- REMOVE ----------------
async def remove_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()

    if query.data.startswith("remove_group_"):
        chat_id = int(query.data.split("_")[-1])
        data["groups"] = [g for g in data["groups"] if g != chat_id]
        save_data(data)
        await query.message.edit_text("Group removed")

    elif query.data.startswith("remove_channel_"):
        chat_id = int(query.data.split("_")[-1])
        data["channels"] = [c for c in data["channels"] if c != chat_id]
        save_data(data)
        await query.message.edit_text("Channel removed")

# ---------------- ADD ----------------
async def add_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    if not mode:
        return

    chat_input = update.message.text
    data = load_data()

    try:
        chat = await context.bot.get_chat(chat_input)

        member = await context.bot.get_chat_member(chat.id, update.effective_user.id)
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)

        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("You must be admin")
            return

        if bot_member.status not in ["administrator"]:
            await update.message.reply_text("Bot must be admin in that chat")
            return

        if mode == "add_group":
            if chat.id not in data["groups"]:
                data["groups"].append(chat.id)
            await update.message.reply_text("Group connected ✅")

        elif mode == "add_channel":
            if chat.id not in data["channels"]:
                data["channels"].append(chat.id)
            await update.message.reply_text("Channel connected ✅")

        save_data(data)
        context.user_data["mode"] = None

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# ---------------- GET ALL ----------------
def get_all():
    data = load_data()
    return data["groups"], data["channels"]

# ---------------- BAN ----------------
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /ban user_id")

    target = int(context.args[0])
    groups, channels = get_all()

    for chat in groups + channels:
        try:
            await context.bot.ban_chat_member(chat, target)
        except:
            pass

    await update.message.reply_text("Banned everywhere 🔥")

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(panel))
    app.add_handler(CallbackQueryHandler(remove_chat, pattern="^remove_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_chat))
    app.add_handler(CommandHandler("ban", ban))

    print("🔥 Bot Running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
