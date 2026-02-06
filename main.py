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

# handlers
from handlers.people import get_people_handlers
from handlers.admin_panel import get_admin_handlers
from handlers.add_debt import build_add_conversation      # ← التعديل المهم
from handlers.rate import build_rate_conversation          # محادثة سعر الدولار

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x}

# ---------------------------
# أدوات عامة
# ---------------------------

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def get_or_create_user(db, uid: int) -> User:
    user = db.query(User).filter(User.tg_user_id == uid).first()
    if not user:
        user = User(
            tg_user_id=uid,
            is_active=is_admin(uid),
            is_blocked=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def check_access(uid: int) -> bool:
    if is_admin(uid):
        return True

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == uid).first()
        if not user:
            return False
        if getattr(user, "is_blocked", False):
            return False
        if not getattr(user, "is_active", False):
            return False
        return True
    finally:
        db.close()


def main_menu(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("➕ إضافة دين", callback_data="add")],
        [InlineKeyboardButton("👥 الأشخاص", callback_data="people")],
        [InlineKeyboardButton("💱 سعر الدولار", callback_data="rate")],
        [InlineKeyboardButton("❓ المساعدة", callback_data="help")],
    ]
    if is_admin(uid):
        rows.append([InlineKeyboardButton("👑 لوحة المشرف", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


PAID_MSG = (
    "🔒 هذا البوت مدفوع.\n"
    "لا يمكنك استخدامه بدون اشتراك فعّال.\n"
    "📩 تواصل مع الأدمن لتفعيل اشتراكك."
)

HELP_TEXT = (
    "❓ المساعدة\n\n"
    "• ➕ إضافة دين: لإضافة دين جديد\n"
    "• 👥 الأشخاص: عرض الأشخاص والديون الخاصة بهم\n"
    "• 💱 سعر الدولار: تحديد سعر الدولار للتحويل التلقائي\n"
)

# ---------------------------
# start
# ---------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db = SessionLocal()
    try:
        get_or_create_user(db, uid)
    finally:
        db.close()

    if not check_access(uid):
        await update.message.reply_text(PAID_MSG)
        return

    await update.message.reply_text(
        "✅ أهلاً بك في بوت إدارة الديون",
        reply_markup=main_menu(uid),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_access(uid):
        await update.message.reply_text(PAID_MSG)
        return
    await update.message.reply_text(HELP_TEXT)


# ---------------------------
# buttons
# ---------------------------

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    data = q.data

    if not check_access(uid):
        await q.message.reply_text(PAID_MSG)
        return

    if data == "help":
        await q.edit_message_text(HELP_TEXT, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")]
        ]))

    elif data == "back_main":
        await q.edit_message_text("القائمة الرئيسية:", reply_markup=main_menu(uid))

    elif data == "admin":
        if not is_admin(uid):
            await q.message.reply_text("🚫 هذه اللوحة للأدمن فقط.")
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
            [InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")],
        ]
        await q.edit_message_text("👑 لوحة المشرف:", reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------------------
# main
# ---------------------------

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start), group=0)
    app.add_handler(CommandHandler("help", help_cmd), group=0)

    # المحادثات أولاً
    app.add_handler(build_add_conversation(), group=0)
    app.add_handler(build_rate_conversation(), group=0)

    # people handlers
    for h in get_people_handlers():
        app.add_handler(h, group=1)

    # buttons العامة
    app.add_handler(CallbackQueryHandler(buttons), group=2)

    # admin
    for h in get_admin_handlers():
        app.add_handler(h, group=3)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
