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

from handlers.people import get_people_handlers, list_people
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
        [InlineKeyboardButton("🔎 بحث عن شخص", callback_data="search")],
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
    "## ❓ المساعدة — بوت الديون (Premium)\n\n"
    "**هذا البوت لإدارة الديون بشكل منظم (دفتر ديون احترافي).**\n"
    "يدعم عملتين: **USD** و **SYP**، وكل دين يُسجَّل **بعملة واحدة** تختارها أثناء الإضافة.\n\n"
    "### 💱 سعر الدولار اليوم\n"
    "- من الزر **💱 سعر الدولار** (محادثة مباشرة)\n"
    "- أو بالأمر: `/rate 15000`\n\n"
    "### ➕ إضافة دين\n"
    "- من الزر **➕ إضافة دين** (محادثة مباشرة)\n"
    "- أو بالأمر: `/add`\n\n"
    "### 👥 الأشخاص\n"
    "- زر الأشخاص يعرض قائمة أشخاص\n"
    "- اضغط على اسم أي شخص لعرض ديونه\n\n"
    "### 🔎 البحث\n"
    "- من زر **بحث عن شخص** أو الأمر: `/search`\n\n"
)

# ---------------------------
# محادثة إضافة دين (زر + /add)
# ---------------------------

ADD_NAME, ADD_CURRENCY, ADD_AMOUNT = range(3)


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_access(uid):
        await update.effective_message.reply_text(PAID_MSG)
        return ConversationHandler.END

    await update.effective_message.reply_text("اكتب اسم الشخص:")
    return ADD_NAME


async def add_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    if not check_access(uid):
        await query.message.reply_text(PAID_MSG)
        return ConversationHandler.END

    await query.message.reply_text("اكتب اسم الشخص:")
    return ADD_NAME


async def add_ask_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("اكتب اسم صحيح:")
        return ADD_NAME

    context.user_data["add_name"] = name

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 USD", callback_data="add_currency_USD"),
            InlineKeyboardButton("🇸🇾 SYP", callback_data="add_currency_SYP"),
        ]
    ])
    await update.message.reply_text("اختر العملة:", reply_markup=keyboard)
    return ADD_CURRENCY


async def add_set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    if not check_access(uid):
        await query.message.reply_text(PAID_MSG)
        return ConversationHandler.END

    data = query.data
    if data == "add_currency_USD":
        context.user_data["add_currency"] = "USD"
    elif data == "add_currency_SYP":
        context.user_data["add_currency"] = "SYP"
    else:
        await query.message.reply_text("اختيار غير صحيح، جرّب مرة ثانية.")
        return ADD_CURRENCY

    await query.message.reply_text("اكتب المبلغ (رقم فقط):")
    return ADD_AMOUNT


async def add_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_access(uid):
        await update.message.reply_text(PAID_MSG)
        return ConversationHandler.END

    name = context.user_data.get("add_name")
    currency = context.user_data.get("add_currency", "USD")
    amount_txt = (update.message.text or "").strip()

    try:
        amount = float(amount_txt)
        if amount <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("اكتب مبلغ صحيح (مثال: 150 أو 150.5)")
        return ADD_AMOUNT

    db = SessionLocal()
    try:
        get_or_create_user(db, uid)

        person = (
            db.query(Person)
            .filter(Person.owner_user_id == uid, Person.name == name)
            .first()
        )
        if not person:
            person = Person(owner_user_id=uid, name=name)
            db.add(person)
            db.commit()
            db.refresh(person)

        debt = Debt(
            owner_user_id=uid,
            person_id=person.id,
            amount=amount,
            currency=currency,
        )
        db.add(debt)
        db.commit()

        await update.message.reply_text(
            f"✅ تمت إضافة الدين بنجاح:\n"
            f"👤 {name}\n"
            f"💰 {amount:g} {currency}",
            reply_markup=main_menu(uid),
        )
        return ConversationHandler.END

    except Exception:
        db.rollback()
        await update.message.reply_text("❌ صار خطأ أثناء حفظ الدين. جرّب مرة ثانية.")
        return ConversationHandler.END
    finally:
        db.close()


def build_add_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start),
            CallbackQueryHandler(add_start_cb, pattern=r"^add$"),
        ],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ask_currency)],
            ADD_CURRENCY: [CallbackQueryHandler(add_set_currency, pattern=r"^add_currency_(USD|SYP)$")],
            ADD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_save)],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=True,
    )

# ---------------------------
# محادثة سعر الدولار (زر + /rate)
# ---------------------------

RATE_WAIT = 100


async def rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_access(uid):
        await update.effective_message.reply_text(PAID_MSG)
        return ConversationHandler.END

    await update.effective_message.reply_text("💱 اكتب سعر الدولار الآن (مثال: 15000):")
    return RATE_WAIT


async def rate_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    if not check_access(uid):
        await query.message.reply_text(PAID_MSG)
        return ConversationHandler.END

    await query.message.reply_text("💱 اكتب سعر الدولار الآن (مثال: 15000):")
    return RATE_WAIT


async def rate_save_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_access(uid):
        await update.message.reply_text(PAID_MSG)
        return ConversationHandler.END

    txt = (update.message.text or "").strip()
    try:
        rate = float(txt)
        if rate <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("اكتب رقم صحيح (مثال: 15000)")
        return RATE_WAIT

    db = SessionLocal()
    try:
        user = get_or_create_user(db, uid)
        user.usd_rate = rate
        db.commit()
        await update.message.reply_text(f"✅ تم تحديث سعر الدولار إلى: {rate:g}")
        return ConversationHandler.END
    except Exception:
        db.rollback()
        await update.message.reply_text("❌ صار خطأ أثناء حفظ السعر. جرّب مرة ثانية.")
        return ConversationHandler.END
    finally:
        db.close()


async def rate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not check_access(uid):
        await update.message.reply_text(PAID_MSG)
        return

    if len(context.args) != 1:
        await update.message.reply_text("الاستخدام:\n/rate 15000")
        return

    try:
        rate = float(context.args[0])
        if rate <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("اكتب رقم صحيح")
        return

    db = SessionLocal()
    try:
        user = get_or_create_user(db, uid)
        user.usd_rate = rate
        db.commit()
        await update.message.reply_text(f"✅ تم تحديث سعر الدولار إلى: {rate:g}")
    except Exception:
        db.rollback()
        await update.message.reply_text("❌ صار خطأ أثناء حفظ السعر. جرّب مرة ثانية.")
    finally:
        db.close()


def build_rate_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("rate", rate_start),
            CallbackQueryHandler(rate_start_cb, pattern=r"^rate$"),
        ],
        states={
            RATE_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate_save_msg)],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=True,
    )

# ---------------------------
# أوامر عامة + أزرار عامة
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
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    if not check_access(uid):
        await query.message.reply_text(PAID_MSG)
        return

    # ⚠️ ملاحظة مهمة:
    # "add" و "rate" ماسكينهم ConversationHandler
    # "people/search/person_..." ماسكينهم handlers/people.py
    # هون نخلي فقط: help/admin/back

    if data == "help":
        await query.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)

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
    app.bot_data["ADMIN_IDS"] = list(ADMIN_IDS)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # /rate رقم يبقى شغال
    app.add_handler(CommandHandler("rate", rate_cmd))

    # محادثات (قبل buttons)
    app.add_handler(build_add_conversation())
    app.add_handler(build_rate_conversation())

    # هاندلرز الأشخاص + البحث (قبل buttons)
    for h in get_people_handlers():
        app.add_handler(h)

    # الأزرار العامة
    app.add_handler(CallbackQueryHandler(buttons))

    # الأدمن
    for h in get_admin_handlers():
        app.add_handler(h)

    app.run_polling()


if __name__ == "__main__":
    main()
