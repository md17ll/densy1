from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from db import SessionLocal, Person

async def list_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db = SessionLocal()
    try:
        rows = db.query(Person).filter(Person.owner_user_id == uid).order_by(Person.created_at.desc()).all()
    finally:
        db.close()

    if not rows:
        await update.message.reply_text("📋 لا يوجد أشخاص بعد. ابدأ بـ /add")
        return

    text = "📋 قائمة الأشخاص:\n\n" + "\n".join([f"• {p.name}" for p in rows])
    await update.message.reply_text(text)

def get_people_handlers():
    return [CommandHandler("people", list_people)]
