import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from db import init_db, SessionLocal, User, Person, Debt

from handlers.people import get_people_handlers
from handlers.admin_panel import get_admin_handlers

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
        [InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_global")],
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
    "📌 المساعدة — بوت إدارة الديون\n\n"
    "هذا البوت يساعدك على إدارة الديون بسهولة بعملتين:\n"
    "USD و SYP.\n\n"
    "يمكنك إضافة ديون، متابعة الأشخاص، تسديد الديون أو حذفها، "
    "ويتم حساب التحويل التقريبي بين العملات حسب آخر سعر دولار محفوظ داخل البوت."
)

# ---------------------------
# أزرار عامة
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
        "✅ أهلاً بك في بوت إدارة الديون (Premium)\nاختر من القائمة:",
        reply_markup=main_menu(uid),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_access(uid):
        await update.message.reply_text(PAID_MSG)
        return
    await update.message.reply_text(HELP_TEXT)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    data = q.data

    if not check_access(uid):
        await q.message.reply_text(PAID_MSG)
        return

    # لا نمسك add ولا people ولا rate (محادثات أخرى تمسكهم)
    if data == "help":
        await q.edit_message_text(
            HELP_TEXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")]
            ]),
        )

    elif data == "cancel_global":
        context.user_data.clear()
        await q.edit_message_text(
            "تم إلغاء العملية.",
            reply_markup=main_menu(uid),
        )

    elif data == "back_main":
        await q.edit_message_text("القائمة الرئيسية:", reply_markup=main_menu(uid))

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
            [InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")],
        ]
        await q.edit_message_text("👑 لوحة المشرف:", reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------------------
# تشغيل
# ---------------------------

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start), group=0)
    app.add_handler(CommandHandler("help", help_cmd), group=0)

    # محادثات أولاً
    app.add_handler(build_add_conversation(), group=0)
    app.add_handler(build_rate_conversation(), group=0)

    # people
    for h in get_people_handlers():
        app.add_handler(h, group=1)

    # أزرار عامة
    app.add_handler(CallbackQueryHandler(buttons), group=2)

    # admin
    for h in get_admin_handlers():
        app.add_handler(h, group=3)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
