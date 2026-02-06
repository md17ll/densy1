import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import init_db
from add_debt import get_add_debt_handler
from people import get_people_handlers
from admin_panel import get_admin_handlers

TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()}


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def menu(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("➕ إضافة دين", callback_data="add")],
        [InlineKeyboardButton("📋 قائمة الأشخاص", callback_data="people")],
        [InlineKeyboardButton("❓ المساعدة", callback_data="help")],
    ]
    if is_admin(uid):
        rows.append([InlineKeyboardButton("👑 لوحة الأدمن", callback_data="admin")])

    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text("✅ أهلاً بك في بوت الديون", reply_markup=menu(uid))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ الأوامر المتاحة الآن:\n"
        "/start\n"
        "/add (إضافة دين خطوة بخطوة)\n"
        "/people (قائمة الأشخاص)\n\n"
        "👑 أوامر الأدمن:\n"
        "/sub <user_id> <days>\n"
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    data = q.data

    if data == "add":
        await q.message.reply_text("➕ ابدأ إضافة دين بالأمر: /add")
    elif data == "people":
        await q.message.reply_text("📋 اعرض الأشخاص بالأمر: /people")
    elif data == "help":
        await q.message.reply_text(
            "✅ الأوامر المتاحة الآن:\n"
            "/start\n"
            "/add\n"
            "/people\n\n"
            "👑 /sub <user_id> <days>\n"
        )
    elif data == "admin":
        if not is_admin(uid):
            await q.message.reply_text("❌ هذا القسم للأدمن فقط.")
        else:
            await q.message.reply_text(
                "👑 لوحة الأدمن\n\n"
                "الأوامر:\n"
                "/sub <user_id> <days>  تفعيل/تمديد اشتراك\n"
            )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing.")
    if not ADMIN_IDS:
        raise RuntimeError("ADMIN_IDS is missing. مثال: 123456789")

    init_db()

    app = Application.builder().token(TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # ✅ مهم جدًا: هذا الـ pattern يمنع خطف أزرار العملة داخل add_debt
    app.add_handler(CallbackQueryHandler(buttons, pattern=r"^(add|people|help|admin)$"))

    # add debt wizard
    app.add_handler(get_add_debt_handler())

    # other modules
    for h in get_people_handlers():
        app.add_handler(h)
    for h in get_admin_handlers():
        app.add_handler(h)

    app.run_polling()


if __name__ == "__main__":
    main()
