import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from db import init_db, SessionLocal, User

from handlers.people import get_people_handlers
from handlers.admin_panel import get_admin_handlers
from handlers.add_debt import get_add_debt_handler
from handlers.rates import get_rate_handlers

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x}


# =========================
# Helpers
# =========================

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def main_menu(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("➕ إضافة دين", callback_data="add")],
        [InlineKeyboardButton("👥 الأشخاص", callback_data="people")],
        [InlineKeyboardButton("💱 سعر الدولار", callback_data="rate")],
        [InlineKeyboardButton("❓ المساعدة", callback_data="help")],
        [InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_global")],
    ]

    if is_admin(uid):
        rows.append([InlineKeyboardButton("👑 لوحة المشرف", callback_data="admin")])

    return InlineKeyboardMarkup(rows)


HELP_TEXT = (
    "📌 **المساعدة — بوت إدارة الديون**\n\n"
    "هذا البوت مخصص لإدارة الديون بطريقة سهلة ومنظمة بعملتين:\n"
    "USD و SYP.\n\n"
    "يمكنك إضافة الديون، متابعة الأشخاص، معرفة الإجماليات، "
    "وتسديد أو حذف الديون بسهولة.\n\n"
    "يعتمد التحويل بين العملات على آخر سعر دولار محفوظ داخل البوت، "
    "وتظهر القيم التقريبية تلقائيًا في كل صفحة."
)

PAID_MSG = (
    "🔒 هذا البوت مدفوع.\n"
    "لا يمكنك استخدامه بدون اشتراك فعّال.\n"
    "📩 تواصل مع الأدمن لتفعيل اشتراكك."
)


def check_access(uid: int) -> bool:
    if is_admin(uid):
        return True

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == uid).first()
        if not user:
            return False
        if user.is_blocked:
            return False
        if not user.is_active:
            return False
        return True
    finally:
        db.close()


# =========================
# Commands
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not check_access(uid):
        await update.message.reply_text(PAID_MSG)
        return

    await update.message.reply_text(
        "أهلاً بك في بوت إدارة الديون",
        reply_markup=main_menu(uid),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    if not check_access(uid):
        await query.message.reply_text(PAID_MSG)
        return

    if data == "help":
        await query.message.edit_text(
            HELP_TEXT,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
            ),
        )

    elif data == "back_main":
        await query.message.edit_text(
            "القائمة الرئيسية:",
            reply_markup=main_menu(uid),
        )

    elif data == "cancel_global":
        context.user_data.clear()
        await query.message.edit_text(
            "تم إلغاء العملية.",
            reply_markup=main_menu(uid),
        )

    elif data == "admin":
        if not is_admin(uid):
            return

        keyboard = [
            [InlineKeyboardButton("➕ تفعيل اشتراك", callback_data="admin_sub")],
            [InlineKeyboardButton("⏳ تمديد اشتراك", callback_data="admin_extend")],
            [InlineKeyboardButton("❌ إلغاء اشتراك", callback_data="admin_cancel")],
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban")],
            [InlineKeyboardButton("✅ فك الحظر", callback_data="admin_unban")],
            [InlineKeyboardButton("📢 رسالة جماعية", callback_data="admin_broadcast")],
            [InlineKeyboardButton("👥 المشتركين", callback_data="admin_subscribers")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
        ]

        await query.message.edit_text(
            "لوحة المشرف:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# =========================
# Run
# =========================

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
