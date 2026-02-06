from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from db import SessionLocal, User


def _is_admin(context: ContextTypes.DEFAULT_TYPE, uid: int) -> bool:
    return uid in context.application.bot_data.get("ADMIN_IDS", [])


# -------------------
# تفعيل اشتراك
# /sub USER_ID DAYS
# -------------------
async def sub_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _is_admin(context, uid):
        return

    if len(context.args) != 2:
        await update.message.reply_text("الاستخدام:\n/sub USER_ID DAYS")
        return

    user_id = int(context.args[0])
    days = int(context.args[1])

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == user_id).first()
        if not user:
            user = User(tg_user_id=user_id)

        user.is_active = True
        user.sub_expires_at = datetime.utcnow() + timedelta(days=days)

        db.add(user)
        db.commit()

        await update.message.reply_text("✅ تم تفعيل الاشتراك")
    finally:
        db.close()


# -------------------
# تمديد
# -------------------
async def extend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _is_admin(context, uid):
        return

    if len(context.args) != 2:
        await update.message.reply_text("الاستخدام:\n/extend USER_ID DAYS")
        return

    user_id = int(context.args[0])
    days = int(context.args[1])

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == user_id).first()
        if not user:
            await update.message.reply_text("المستخدم غير موجود")
            return

        if not user.sub_expires_at:
            user.sub_expires_at = datetime.utcnow()

        user.sub_expires_at += timedelta(days=days)
        db.commit()

        await update.message.reply_text("✅ تم التمديد")
    finally:
        db.close()


# -------------------
# إلغاء اشتراك
# -------------------
async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _is_admin(context, uid):
        return

    user_id = int(context.args[0])

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == user_id).first()
        if not user:
            return

        user.is_active = False
        db.commit()

        await update.message.reply_text("❌ تم إلغاء الاشتراك")
    finally:
        db.close()


# -------------------
# حظر
# -------------------
async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(context, update.effective_user.id):
        return

    user_id = int(context.args[0])

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == user_id).first()
        if not user:
            return

        user.is_blocked = True
        db.commit()
        await update.message.reply_text("🚫 تم الحظر")
    finally:
        db.close()


# -------------------
# فك الحظر
# -------------------
async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(context, update.effective_user.id):
        return

    user_id = int(context.args[0])

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == user_id).first()
        if not user:
            return

        user.is_blocked = False
        db.commit()
        await update.message.reply_text("✅ تم فك الحظر")
    finally:
        db.close()


# -------------------
# رسالة جماعية
# -------------------
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(context, update.effective_user.id):
        return

    text = " ".join(context.args)

    db = SessionLocal()
    try:
        users = db.query(User).all()
    finally:
        db.close()

    for u in users:
        try:
            await context.bot.send_message(chat_id=u.tg_user_id, text=text)
        except:
            pass

    await update.message.reply_text("📢 تم الإرسال")


# -------------------
# إحصائيات
# -------------------
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(context, update.effective_user.id):
        return

    db = SessionLocal()
    try:
        total = db.query(User).count()
        active = db.query(User).filter(User.is_active == True).count()
    finally:
        db.close()

    await update.message.reply_text(
        f"👥 المستخدمين: {total}\n⭐ المشتركين: {active}"
    )


def get_admin_handlers():
    return [
        CommandHandler("sub", sub_cmd),
        CommandHandler("extend", extend_cmd),
        CommandHandler("cancel", cancel_cmd),
        CommandHandler("ban", ban_cmd),
        CommandHandler("unban", unban_cmd),
        CommandHandler("broadcast", broadcast_cmd),
        CommandHandler("stats", stats_cmd),
    ]
