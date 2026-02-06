import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from db import SessionLocal, User

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x}

def is_admin(uid):
    return uid in ADMIN_IDS

async def sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid = int(context.args[0])
    days = int(context.args[1])

    db = SessionLocal()
    u = db.query(User).filter(User.tg_user_id == uid).first()
    if not u:
        u = User(tg_user_id=uid)
        db.add(u)
        db.commit()
        db.refresh(u)

    base = u.sub_expires_at if u.sub_expires_at and u.sub_expires_at > datetime.utcnow() else datetime.utcnow()
    u.sub_expires_at = base + timedelta(days=days)
    u.is_active = True
    db.commit()
    db.close()
    await update.message.reply_text("تم تفعيل الاشتراك.")

def get_admin_handlers():
    return [
        CommandHandler("sub", sub),
    ]
