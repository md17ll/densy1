from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from db import SessionLocal, User


async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if len(context.args) != 1:
        await update.message.reply_text("الاستخدام:\n/rate 15000")
        return

    rate = float(context.args[0])

    db = SessionLocal()
    user = db.query(User).filter(User.tg_user_id == uid).first()

    if not user:
        user = User(tg_user_id=uid, is_active=True)
        db.add(user)

    user.usd_rate = rate
    db.commit()
    db.close()

    await update.message.reply_text("تم تحديث سعر الدولار بنجاح")


def get_rate_handlers():
    return [CommandHandler("rate", set_rate)]
