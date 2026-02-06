from telegram.ext import CommandHandler
from db import SessionLocal,User

async def set_rate(update,context):
    rate=context.args[0]
    db=SessionLocal()
    u=db.query(User).filter(User.tg_user_id==update.effective_user.id).first()
    if u:
        u.usd_rate=rate
        db.commit()
    db.close()
    await update.message.reply_text("تم تحديث السعر")

def get_rate_handlers():
    return [CommandHandler("rate",set_rate)]
