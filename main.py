import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from db import init_db, SessionLocal, User

from handlers.add_debt import get_add_debt_handler, add_start
from handlers.people import get_people_handlers, list_people
from handlers.admin_panel import get_admin_handlers
from handlers.rates import get_rate_handlers

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x}


def is_admin(uid: int):
    return uid in ADMIN_IDS


def check_access(uid: int):
    if is_admin(uid):
        return True

    db = SessionLocal()
    user = db.query(User).filter(User.tg_user_id == uid).first()
    db.close()

    if not user:
        return False
    if user.is_blocked:
        return False
    if not user.is_active:
        return False

    return True


def main_menu(uid):
    rows = [
        [InlineKeyboardButton("➕ إضافة دين", callback_data="add")],
        [InlineKeyboardButton("👥 الأشخاص", callback_data="people")],
        [InlineKeyboardButton("💱 سعر الدولار", callback_data="rate")],
        [InlineKeyboardButton("❓ المساعدة", callback_data="help")],
    ]

    if is_admin(uid):
        rows.append([InlineKeyboardButton("👑 لوحة المشرف", callback_data="admin")])

    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not check_access(uid):
        await update.message.reply_text(
            "🔒 هذا البوت مدفوع.\nتواصل مع الأدمن لتفعيل الاشتراك."
        )
        return

    await update.message.reply_text(
        "أهلاً بك في بوت إدارة الديون",
        reply_markup=main_menu(uid),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if not check_access(uid):
        await query.message.reply_text("🔒 اشتراكك غير مفعل")
        return

    if query.data == "add":
        await add_start(update, context)

    elif query.data == "people":
        await list_people(update, context)

    elif query.data == "rate":
        await query.message.reply_text("أرسل السعر هكذا:\n/rate 15000")

    elif query.data == "help":
        await query.message.reply_text(
            "📌 شرح البوت:\n\n"
            "➕ إضافة دين: تسجيل دين جديد\n"
            "👥 الأشخاص: عرض جميع الأشخاص\n"
            "💱 سعر الدولار: تحديد سعر الدولار الخاص بك\n"
            "👑 لوحة الأدمن: إدارة الاشتراكات\n\n"
            "الأوامر:\n"
            "/add إضافة دين\n"
            "/people عرض الأشخاص\n"
            "/rate تحديد السعر\n"
            "/sub تفعيل مستخدم (للأدمن)"
        )

    elif query.data == "admin":
        await query.message.reply_text(
            "لوحة الأدمن:\n"
            "/sub USER_ID تفعيل\n"
            "/ban USER_ID حظر\n"
            "/unban USER_ID فك الحظر"
        )


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

    for h in get_rate_handlers():
        app.add_handler(h)

    app.run_polling()


if __name__ == "__main__":
    main()
