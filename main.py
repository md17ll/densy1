import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import init_db
from add_debt import get_add_debt_handler
from people import get_people_handlers
from admin_panel import get_admin_handlers

TOKEN = os.getenv("BOT_TOKEN")

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة دين", callback_data="add")],
        [InlineKeyboardButton("📋 قائمة الأشخاص", callback_data="people")],
        [InlineKeyboardButton("📊 الملخص", callback_data="summary")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً", reply_markup=menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "add":
        await q.message.reply_text("اكتب /add")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(get_add_debt_handler())

    for h in get_people_handlers():
        app.add_handler(h)
    for h in get_admin_handlers():
        app.add_handler(h)

    app.run_polling()

if __name__ == "__main__":
    main()
