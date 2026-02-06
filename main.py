import os
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

from db import init_db, SessionLocal, User

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()}


# -----------------------
# Helpers
# -----------------------
def is_admin(tg_user_id: int) -> bool:
    return tg_user_id in ADMIN_IDS


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


def set_subscription(tg_user_id: int, days: int) -> tuple[bool, str]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
        if not user:
            user = User(tg_user_id=tg_user_id)
            db.add(user)
            db.commit()
            db.refresh(user)

        now = datetime.utcnow()
        # إذا عنده اشتراك شغال، مدد من تاريخ الانتهاء، وإلا من الآن
        base = user.sub_expires_at if user.sub_expires_at and user.sub_expires_at > now else now
        user.sub_expires_at = base + timedelta(days=days)
        user.is_active = True
        db.commit()
        return True, f"✅ تم تفعيل/تمديد الاشتراك لمدة {days} يوم.\n📅 ينتهي: {user.sub_expires_at} (UTC)"
    finally:
        db.close()


def cancel_subscription(tg_user_id: int) -> tuple[bool, str]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
        if not user:
            return False, "❌ المستخدم غير موجود في قاعدة البيانات."
        user.is_active = False
        user.sub_expires_at = None
        db.commit()
        return True, "✅ تم إلغاء الاشتراك."
    finally:
        db.close()


def set_block(tg_user_id: int, blocked: bool) -> tuple[bool, str]:
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
        return True, ("🚫 تم حظر المستخدم." if blocked else "✅ تم فك حظر المستخدم.")
    finally:
        db.close()


def check_access(tg_user_id: int) -> tuple[bool, str]:
    """
    returns (allowed, message_if_denied)
    """
    user = get_or_create_user(tg_user_id)

    if user.is_blocked:
        return False, "🚫 تم حظرك من استخدام البوت."

    if not user.is_active or not user.sub_expires_at:
        return False, "🔒 هذا البوت مدفوع.\nلا يمكنك استخدامه بدون اشتراك فعّال.\n📩 تواصل مع الأدمن لتفعيل اشتراكك."

    # انتهاء الاشتراك
    if user.sub_expires_at <= datetime.utcnow():
        return False, "⛔ اشتراكك منتهي.\n📩 تواصل مع الأدمن لتجديد الاشتراك."

    return True, ""


# -----------------------
# User Commands
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)

    if not allowed:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 تواصل مع الأدمن", url="https://t.me/")]  # ضع يوزر الأدمن لاحقًا
        ])
        await update.message.reply_text(msg, reply_markup=kb)
        return

    # القائمة الرئيسية (مؤقتًا نص)
    await update.message.reply_text(
        "✅ أهلاً بك في بوت الديون (Premium)\n"
        "القائمة الرئيسية قريبًا:\n"
        "➕ إضافة دين\n"
        "📋 قائمة الديون\n"
        "📊 الملخص\n"
        "❓ المساعدة"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    allowed, msg = check_access(tg_id)

    if not allowed:
        await update.message.reply_text(msg)
        return

    await update.message.reply_text(
        "❓ المساعدة – دليل استخدام بوت الديون\n\n"
        "✅ فكرة البوت:\n"
        "يسجل ديون الأشخاص بعملتين (USD / SYP) ويعرض إجمالي كل عملة مع تحويل تقريبي حسب سعر الدولار اليوم.\n\n"
        "💱 سعر الدولار اليوم:\n"
        "استخدم /rate لإدخال سعر اليوم يدويًا، وإذا لم تدخل سعر اليوم سيستخدم آخر سعر محفوظ.\n\n"
        "🧾 الأوامر:\n"
        "/start - تشغيل البوت\n"
        "/add - إضافة دين\n"
        "/list - قائمة الديون\n"
        "/summary - الملخص\n"
        "/rate - سعر الدولار اليوم\n"
        "/export - تصدير CSV/Excel\n"
        "/pin - حماية PIN\n"
        "/help - المساعدة\n"
    )


# -----------------------
# Admin Commands
# -----------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        ok, msg = set_subscription(user_id, days)
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
        ok, msg = cancel_subscription(user_id)
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
        ok, msg = set_block(user_id, True)
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
        ok, msg = set_block(user_id, False)
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


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Set it in Railway Variables.")
    if not ADMIN_IDS:
        raise RuntimeError("ADMIN_IDS is missing. Set it in Railway Variables. Example: 123,456")

    init_db()

    app = Application.builder().token(TOKEN).build()

    # user
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # admin
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("sub", sub_cmd))
    app.add_handler(CommandHandler("unsub", unsub_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("who", who_cmd))

    app.run_polling()


if __name__ == "__main__":
    main()
