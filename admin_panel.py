import os
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from db import SessionLocal, User

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x}


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def activate_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("هذا الأمر للأدمن فقط")
        return

    if len(context.args) != 1:
        await update.message.reply_text("الاستخدام: /sub USER_ID")
        return

    uid = int(context.args[0])

    db = SessionLocal()
    user = db.query(User).filter(User.tg_user_id == uid).first()

    if not user:
        user = User(tg_user_id=uid, is_active=True)
        db.add(user)
    else:
        user.is_active = True

    db.commit()
    db.close()

    await update.message.reply_text("تم تفعيل الاشتراك")


async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    uid = int(context.args[0])

    db = SessionLocal()
    user = db.query(User).filter(User.tg_user_id == uid).first()
    if user:
        user.is_blocked = True
        db.commit()
    db.close()

    await update.message.reply_text("تم حظر المستخدم")


async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    uid = int(context.args[0])

    db = SessionLocal()
    user = db.query(User).filter(User.tg_user_id == uid).first()
    if user:
        user.is_blocked = False
        db.commit()
    db.close()

    await update.message.reply_text("تم فك الحظر")


def get_admin_handlers():
    return [
        CommandHandler("sub", activate_sub),
        CommandHandler("ban", block_user),
        CommandHandler("unban", unblock_user),
    ]
