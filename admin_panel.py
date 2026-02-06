import os
from telegram.ext import CommandHandler
from db import SessionLocal,User

ADMIN_IDS={int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x}

async def sub(update,context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    uid=int(context.args[0])
    db=SessionLocal()
    u=db.query(User).filter(User.tg_user_id==uid).first()
    if not u:
        u=User(tg_user_id=uid,is_active=True)
        db.add(u)
    else:
        u.is_active=True
    db.commit(); db.close()
    await update.message.reply_text("تم التفعيل")

def get_admin_handlers():
    return [CommandHandler("sub",sub)]
