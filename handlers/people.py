from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from db import SessionLocal, Person


async def list_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    db = SessionLocal()
    people = (
        db.query(Person)
        .filter(Person.owner_user_id == uid)
        .order_by(Person.id.desc())
        .all()
    )
    db.close()

    if not people:
        await update.message.reply_text("لا يوجد أشخاص بعد. أضف دين أولاً عبر /add")
        return

    text = "قائمة الأشخاص:\n\n"
    for p in people:
        text += f"- {p.name}\n"

    await update.message.reply_text(text)


def get_people_handlers():
    return [
        CommandHandler("people", list_people),
    ]
