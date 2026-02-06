import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from db import init_db, SessionLocal, User

from handlers.add_debt import get_add_debt_handler
from handlers.people import get_people_handlers, list_people
from handlers.admin_panel import get_admin_handlers
from handlers.rates import get_rate_handlers

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x}


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def check_access(uid: int) -> bool:
    # الأدمن دائمًا مسموح
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


HELP_TEXT = (
    "## 📌 المساعدة — بوت الديون (Premium)\n\n"
    "**هذا البوت لإدارة الديون بشكل منظم (دفتر ديون احترافي).**\n"
    "يدعم عملتين: **USD** و **SYP**، وكل دين يُسجَّل **بعملة واحدة** تختارها أثناء الإضافة.\n\n"
    "### ✅ فكرة العملات والتحويل\n"
    "- إذا كان الدين **بالدولار** يبقى USD.\n"
    "- إذا كان الدين **بالليرة** يبقى SYP.\n"
    "- عند عرض **الملخص** أو ملف الشخص، سيظهر:\n"
    "  - **إجمالي USD**\n"
    "  - **إجمالي SYP**\n"
    "  - **تحويل تقريبي** بينهما حسب **آخر سعر دولار محفوظ**.\n\n"
    "## 🧾 القائمة الرئيسية\n"
    "- **➕ إضافة دين**: تسجيل دين جديد خطوة بخطوة.\n"
    "- **📋 قائمة الديون / الأشخاص**: عرض الأشخاص ثم ديون كل شخص.\n"
    "- **📊 الملخص**: إجمالي الديون بالدولار والليرة + تحويل تقريبي.\n"
    "- **💱 سعر الدولار اليوم**: إدخال سعر الدولار يدويًا ليُستخدم في التحويلات.\n"
    "- **❓ المساعدة**: هذا الشرح.\n\n"
    "## 💱 سعر الدولار اليوم (يدوي)\n"
    "اكتب السعر مرة واحدة، وسيستخدمه البوت تلقائيًا في التحويلات.\n"
    "وإذا ما أدخلت سعر اليوم، البوت سيستخدم **آخر سعر محفوظ**.\n\n"
    "مثال:\n"
    "/rate 15000\n\n"
    "## 💵 إضافة دين\n"
    "اكتب:\n"
    "/add\n"
    "ثم اتبع الخطوات داخل الشات.\n\n"
    "## 👨‍💼 أوامر البوت\n"
    "/start بدء البوت وإظهار القائمة\n"
    "/add إضافة دين\n"
    "/people عرض الأشخاص\n"
    "/rate تحديد سعر الدولار\n"
    "/help المساعدة\n\n"
    "## 👑 الاشتراك (Premium)\n"
    "هذا البوت **مدفوع** ولا يمكن استخدامه بدون اشتراك فعّال.\n"
    "إذا ظهرت لك رسالة أن البوت مدفوع، تواصل مع الأدمن لتفعيل الاشتراك.\n"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not check_access(uid):
        await update.message.reply_text(
            "🔒 هذا البوت مدفوع.\nلا يمكنك استخدامه بدون اشتراك فعّال.\n📩 تواصل مع الأدمن لتفعيل اشتراكك."
        )
        return

    await update.message.reply_text(
        "✅ أهلاً بك في بوت إدارة الديون (Premium)\nاختر من القائمة:",
        reply_markup=main_menu(uid),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_access(uid):
        await update.message.reply_text(
            "🔒 هذا البوت مدفوع.\nلا يمكنك استخدامه بدون اشتراك فعّال.\n📩 تواصل مع الأدمن لتفعيل اشتراكك."
        )
        return

    await update.message.reply_text(HELP_TEXT)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    if not check_access(uid):
        await query.message.reply_text(
            "🔒 هذا البوت مدفوع.\nلا يمكنك استخدامه بدون اشتراك فعّال.\n📩 تواصل مع الأدمن لتفعيل اشتراكك."
        )
        return

    if data == "add":
        # سنجعل الزر يبدأ الإضافة مباشرة لاحقًا (زر زر)
        await query.message.reply_text("✍️ اكتب الأمر التالي لبدء إضافة الدين:\n/add")

    elif data == "people":
        await list_people(update, context)

    elif data == "rate":
        await query.message.reply_text("💱 أرسل السعر هكذا:\n/rate 15000")

    elif data == "help":
        await query.message.reply_text(HELP_TEXT)

    elif data == "admin":
        if not is_admin(uid):
            await query.message.reply_text("🚫 هذه اللوحة للأدمن فقط.")
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
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
        ]
        await query.message.reply_text("👑 لوحة المشرف:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back":
        await query.message.reply_text("القائمة الرئيسية:", reply_markup=main_menu(uid))

    # أزرار المشرف الآن تعطي تعليمات (ربطها الفعلي نعمله زر زر بالملف admin_panel.py)
    elif data == "admin_sub":
        await query.message.reply_text("اكتب:\n/sub USER_ID DAYS\nمثال:\n/sub 123456 30")

    elif data == "admin_extend":
        await query.message.reply_text("اكتب:\n/extend USER_ID DAYS\nمثال:\n/extend 123456 30")

    elif data == "admin_cancel":
        await query.message.reply_text("اكتب:\n/cancel USER_ID\nمثال:\n/cancel 123456")

    elif data == "admin_ban":
        await query.message.reply_text("اكتب:\n/ban USER_ID\nمثال:\n/ban 123456")

    elif data == "admin_unban":
        await query.message.reply_text("اكتب:\n/unban USER_ID\nمثال:\n/unban 123456")

    elif data == "admin_broadcast":
        await query.message.reply_text("اكتب:\n/broadcast نص الرسالة")

    elif data == "admin_subscribers":
        await query.message.reply_text("اكتب:\n/subscribers")

    elif data == "admin_stats":
        await query.message.reply_text("اكتب:\n/stats")


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    # نخزن ADMIN_IDS حتى تستخدمها handlers مثل add_debt.py
    app.bot_data["ADMIN_IDS"] = list(ADMIN_IDS)

    # أوامر عامة
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # الأزرار
    app.add_handler(CallbackQueryHandler(buttons))

    # إضافة دين
    app.add_handler(get_add_debt_handler())

    # الناس
    for h in get_people_handlers():
        app.add_handler(h)

    # الأدمن
    for h in get_admin_handlers():
        app.add_handler(h)

    # سعر الدولار
    for h in get_rate_handlers():
        app.add_handler(h)

    app.run_polling()


if __name__ == "__main__":
    main()
