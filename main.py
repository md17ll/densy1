import os
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from db import init_db, SessionLocal, User

# -----------------------
# Env
# -----------------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()}

# ضع يوزرك مثل: YourUsername (بدون @)
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "").strip()  # مثال: YourUsername


# -----------------------
# Helpers
# -----------------------
def is_admin(tg_user_id: int) -> bool:
    return tg_user_id in ADMIN_IDS


def admin_contact_url() -> str:
    if ADMIN_CONTACT:
        return f"https://t.me/{ADMIN_CONTACT}"
    # fallback (إذا ما حطيت يوزر الأدمن)
    return "https://t.me/"


def get_or_create_user(tg_user_id: int) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
        if not user:
            user = User(
                tg_user_id=tg_user_id,
                is_blocked=False,
                is_active=False,
                sub_expires_at=None,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def get_user(tg_user_id: int) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.tg_user_id == tg_user_id).first()
    finally:
        db.close()


def set_subscription(tg_user_id: int, days: int) -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
        if not user:
            user = User(tg_user_id=tg_user_id)
            db.add(user)
            db.commit()
            db.refresh(user)

        now = datetime.utcnow()
        base = user.sub_expires_at if user.sub_expires_at and user.sub_expires_at > now else now
        user.sub_expires_at = base + timedelta(days=days)
        user.is_active = True
        db.commit()
        return f"✅ تم تفعيل/تمديد الاشتراك لمدة {days} يوم.\n📅 ينتهي: {user.sub_expires_at} (UTC)"
    finally:
        db.close()


def cancel_subscription(tg_user_id: int) -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
        if not user:
            return "❌ المستخدم غير موجود في قاعدة البيانات."
        user.is_active = False
        user.sub_expires_at = None
        db.commit()
        return "✅ تم إلغاء الاشتراك."
    finally:
        db.close()


def set_block(tg_user_id: int, blocked: bool) -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
        if not user:
            user = User(tg_user_id=tg_user_id)
            db.add(user)
            db.commit()
            db.refresh(user)

        user.is_blocked = blocked
        db.commit()
        return "🚫 تم حظر المستخدم." if blocked else "✅ تم فك حظر المستخدم."
    finally:
        db.close()


def check_access(tg_user_id: int) -> tuple[bool, str]:
    """
    returns (allowed, message_if_denied)
    """
    # ✅ الأدمن مسموح له دائمًا (حتى بدون اشتراك)
    if is_admin(tg_user_id):
        user = get_or_create_user(tg_user_id)
        if user.is_blocked:
            return False, "🚫 تم حظرك من استخدام البوت."
        return True, ""

    user = get_or_create_user(tg_user_id)

    if user.is_blocked:
        return False, "🚫 تم حظرك من استخدام البوت."

    if not user.is_active or not user.sub_expires_at:
        return False, "🔒 هذا البوت مدفوع.\nلا يمكنك استخدامه بدون اشتراك فعّال.\n📩 تواصل مع الأدمن لتفعيل اشتراكك."

    if user.sub_expires_at <= datetime.utcnow():
        return False, "⛔ اشتراكك منتهي.\n📩 تواصل مع الأدمن لتجديد الاشتراك."

    return True, ""


def main_menu_keyboard(tg_user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("➕ إضافة دين", callback_data="add_debt")],
        [InlineKeyboardButton("📋 قائمة الديون", callback_data="list_debts")],
        [InlineKeyboardButton("📊 الملخص", callback_data="summary")],
        [InlineKeyboardButton("❓ المساعدة", callback_data="help")],
    ]
    if is_admin(tg_user_id):
        rows.append([InlineKeyboardButton("👑 لوحة المشرف", callback_data="admin_panel")])

    return InlineKeyboardMarkup(rows)


def back_home_keyboard(tg_user_id: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("⬅️ رجوع للقائمة", callback_data="home")]]
    if is_admin(tg_user_id):
        rows.append([InlineKeyboardButton("👑 لوحة المشرف", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)


def contact_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("📩 تواصل مع الأدمن", url=admin_contact_url())]])


HELP_TEXT = (
    "❓ المساعدة – دليل استخدام بوت الديون\n\n"
    "✅ فكرة البوت:\n"
    "دفتر ديون احترافي بعملتين (USD / SYP).\n"
    "كل دين يُسجّل بعملة واحدة، وعند فتح ملف الشخص يظهر إجمالي USD وإجمالي SYP مع تحويل تقريبي حسب (سعر الدولار اليوم).\n\n"
    "💱 سعر الدولار اليوم:\n"
    "سعر يومي يدخله المستخدم يدويًا، وإذا لم يُدخل سعر اليوم يتم استخدام آخر سعر محفوظ تلقائيًا.\n\n"
    "⭐ ميزات البوت:\n"
    "• تسديد جزئي/كامل\n"
    "• تذكيرات قبل الموعد وعند التأخير + تقارير دورية\n"
    "• ملف لكل شخص + سجل عمليات\n"
    "• بحث سريع\n"
    "• تصدير CSV/Excel\n"
    "• حماية PIN\n\n"
    "🧾 الأوامر:\n"
    "/start - تشغيل البوت\n"
    "/add - إضافة دين\n"
    "/list - قائمة الديون\n"
    "/summary - الملخص\n"
    "/rate - سعر الدولار اليوم\n"
    "/export - تصدير CSV/Excel\n"
    "/pin - حماية PIN\n"
    "/help - المساعدة\n"
    "/myid - عرض آيديك\n\n"
    "👑 أوامر الأدمن:\n"
    "/admin - لوحة الأدمن\n"
    "/sub <user_id> <days> - تفعيل/تمديد\n"
    "/unsub <user_id> - إلغاء اشتراك\n"
    "/ban <user_id> - حظر\n"
    "/unban <user_id> - فك حظر\n"
    "/who <user_id> - معلومات مستخدم\n"
)


# -----------------------
# User Commands
# -----------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)

    if not allowed:
        await update.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return

    await update.message.reply_text(
        "✅ أهلاً بك في بوت الديون (Premium)\n\nاختر من القائمة:",
        reply_markup=main_menu_keyboard(tg_id),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)
    if not allowed:
        await update.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return

    await update.message.reply_text(HELP_TEXT)


async def myid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    await update.message.reply_text(f"🆔 Your Telegram ID: `{tg_id}`", parse_mode="Markdown")


# Placeholder commands (حتى الآن)
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)
    if not allowed:
        await update.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return
    await update.message.reply_text("➕ إضافة دين (قريبًا عبر نموذج كامل من الأزرار).")


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)
    if not allowed:
        await update.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return
    await update.message.reply_text("📋 قائمة الديون (قريبًا).")


async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)
    if not allowed:
        await update.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return
    await update.message.reply_text("📊 الملخص (قريبًا).")


async def rate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)
    if not allowed:
        await update.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return
    await update.message.reply_text("💱 سعر الدولار اليوم (قريبًا).")


async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)
    if not allowed:
        await update.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return
    await update.message.reply_text("📤 تصدير CSV/Excel (قريبًا).")


async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)
    if not allowed:
        await update.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return
    await update.message.reply_text("🔐 PIN (قريبًا).")


# -----------------------
# Buttons (Inline)
# -----------------------
async def buttons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tg_id = query.from_user.id

    # مهم: يوقف Loading في تيليجرام
    await query.answer()

    allowed, msg = check_access(tg_id)
    if not allowed:
        # إذا ممنوع، نرسل رسالة جديدة (أضمن)
        await query.message.reply_text(msg, reply_markup=contact_admin_keyboard())
        return

    data = query.data

    if data == "home":
        await query.edit_message_text(
            "✅ أهلاً بك في بوت الديون (Premium)\n\nاختر من القائمة:",
            reply_markup=main_menu_keyboard(tg_id),
        )
        return

    if data == "add_debt":
        await query.edit_message_text(
            "➕ إضافة دين\n\n(قريبًا: نموذج إضافة دين خطوة بخطوة)",
            reply_markup=back_home_keyboard(tg_id),
        )
        return

    if data == "list_debts":
        await query.edit_message_text(
            "📋 قائمة الديون\n\n(قريبًا: عرض الأشخاص والديون + بحث + تصفية)",
            reply_markup=back_home_keyboard(tg_id),
        )
        return

    if data == "summary":
        await query.edit_message_text(
            "📊 الملخص\n\n(قريبًا: إجمالي USD / SYP + المتأخرة + سعر اليوم)",
            reply_markup=back_home_keyboard(tg_id),
        )
        return

    if data == "help":
        await query.edit_message_text(
            HELP_TEXT,
            reply_markup=back_home_keyboard(tg_id),
        )
        return

    if data == "admin_panel":
        if not is_admin(tg_id):
            await query.edit_message_text("❌ هذا القسم للأدمن فقط.")
            return

        await query.edit_message_text(
            "👑 لوحة الأدمن\n\n"
            "الأوامر:\n"
            "/sub <user_id> <days>  تفعيل/تمديد اشتراك\n"
            "/unsub <user_id>       إلغاء اشتراك\n"
            "/ban <user_id>         حظر\n"
            "/unban <user_id>       فك حظر\n"
            "/who <user_id>         معلومات عن مستخدم\n"
            "/myid                  عرض آيديك\n\n"
            "⬅️ اضغط رجوع للعودة للقائمة.",
            reply_markup=back_home_keyboard(tg_id),
        )
        return


# -----------------------
# Admin Commands
# -----------------------
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_admin(tg_id):
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط.")
        return

    await update.message.reply_text(
        "👑 لوحة الأدمن\n\n"
        "الأوامر:\n"
        "/sub <user_id> <days>  تفعيل/تمديد اشتراك\n"
        "/unsub <user_id>       إلغاء اشتراك\n"
        "/ban <user_id>         حظر\n"
        "/unban <user_id>       فك حظر\n"
        "/who <user_id>         معلومات عن مستخدم\n"
        "/myid                  عرض آيديك\n"
    )


async def sub_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_admin(tg_id):
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("الاستخدام: /sub <user_id> <days>")
        return

    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        msg = set_subscription(user_id, days)
        await update.message.reply_text(msg)
    except ValueError:
        await update.message.reply_text("❌ تأكد أن user_id و days أرقام صحيحة.")


async def unsub_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_admin(tg_id):
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("الاستخدام: /unsub <user_id>")
        return

    try:
        user_id = int(context.args[0])
        msg = cancel_subscription(user_id)
        await update.message.reply_text(msg)
    except ValueError:
        await update.message.reply_text("❌ user_id لازم يكون رقم.")


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_admin(tg_id):
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("الاستخدام: /ban <user_id>")
        return

    try:
        user_id = int(context.args[0])
        msg = set_block(user_id, True)
        await update.message.reply_text(msg)
    except ValueError:
        await update.message.reply_text("❌ user_id لازم يكون رقم.")


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_admin(tg_id):
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("الاستخدام: /unban <user_id>")
        return

    try:
        user_id = int(context.args[0])
        msg = set_block(user_id, False)
        await update.message.reply_text(msg)
    except ValueError:
        await update.message.reply_text("❌ user_id لازم يكون رقم.")


async def who_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_admin(tg_id):
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("الاستخدام: /who <user_id>")
        return

    try:
        user_id = int(context.args[0])
        u = get_user(user_id)
        if not u:
            await update.message.reply_text("❌ المستخدم غير موجود.")
            return

        await update.message.reply_text(
            f"👤 user_id: {u.tg_user_id}\n"
            f"🚫 محظور: {u.is_blocked}\n"
            f"💎 فعال: {u.is_active}\n"
            f"📅 انتهاء: {u.sub_expires_at}\n"
            f"🕒 إنشاء: {u.created_at}"
        )
    except ValueError:
        await update.message.reply_text("❌ user_id لازم يكون رقم.")


# -----------------------
# App
# -----------------------
def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Set it in Railway Variables.")
    if not ADMIN_IDS:
        raise RuntimeError("ADMIN_IDS is missing. Example: 123,456")

    init_db()

    app = Application.builder().token(TOKEN).build()

    # user commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("myid", myid_cmd))

    # placeholders for agreed commands (will be implemented later)
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("rate", rate_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("pin", pin_cmd))

    # admin commands
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("sub", sub_cmd))
    app.add_handler(CommandHandler("unsub", unsub_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("who", who_cmd))

    # buttons
    app.add_handler(CallbackQueryHandler(buttons_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
