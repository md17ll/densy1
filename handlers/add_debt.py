from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from db import SessionLocal, Person, Debt

ASK_NAME, ASK_AMOUNT = range(2)


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text("اكتب اسم الشخص:")
    return ASK_NAME


async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["person_name"] = update.message.text
    await update.message.reply_text("اكتب المبلغ:")
    return ASK_AMOUNT


async def save_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data["person_name"]

    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("اكتب رقم صحيح")
        return ASK_AMOUNT

    db = SessionLocal()

    person = Person(
        owner_user_id=update.effective_user.id,
        name=name,
    )
    db.add(person)
    db.commit()
    db.refresh(person)

    debt = Debt(
        owner_user_id=update.effective_user.id,
        person_id=person.id,
        amount=amount,
        currency="USD",
    )
    db.add(debt)
    db.commit()
    db.close()

    await update.message.reply_text("✅ تمت إضافة الدين بنجاح")
    return ConversationHandler.END


def get_add_debt_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_debt)],
        },
        fallbacks=[],
    )
