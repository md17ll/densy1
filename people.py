from telegram.ext import CommandHandler
from db import SessionLocal,Person

async def list_people(update,context):
    db=SessionLocal()
    rows=db.query(Person).filter(Person.owner_user_id==update.effective_user.id).all()
    db.close()
    txt="\n".join([r.name for r in rows]) or "لا يوجد"
    await update.message.reply_text(txt)

def get_people_handlers():
    return [CommandHandler("people",list_people)]
