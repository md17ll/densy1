from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from db import SessionLocal, Person

async def list_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    rows = db.query(Person).filter(Person.owner_user_id == update.effective_user.id).all()
    db.close()

    if not rows:
        await update.message.reply_text("لا يوجد أشخاص بعد.")
        return

    text = "قائمة الأشخاص:\n"
    for p in rows:
        text += f"- {p.name}\n"
    await update.message.reply_text(text)

def get_people_handlers():
    return [
        CommandHandler("people", list_people),
    ]
