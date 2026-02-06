import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from db import init_db  # تهيئة الجداول

TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is running!")


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Set it in Railway Variables.")

    # إنشاء الجداول في Postgres (إذا لم تكن موجودة)
    init_db()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    app.run_polling()


if __name__ == "__main__":
    main()
