import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from db import init_db
from add_debt import get_add_debt_handler

TOKEN = os.getenv("BOT_TOKEN")


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة دين", callback_data="add")],
        [InlineKeyboardButton("📋 قائمة الأشخاص", callback_data="people")],
        [InlineKeyboardButton("📊 الملخص", callback_data="summary")],
        [InlineKeyboardButton("❓ المساعدة", callback_data="help")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت الديون",
        reply_markup=main_keyboard()
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add":
        await query.message.reply_text("اكتب /add لبدء إضافة الدين")


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(get_add_debt_handler())

    app.run_polling()


if __name__ == "__main__":
    main()
