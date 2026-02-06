from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from db import SessionLocal, Person, Debt
from datetime import datetime

ASK_NAME, ASK_AMOUNT, ASK_CURRENCY, ASK_DATE, ASK_NOTE, CONFIRM = range(6)


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اكتب اسم الشخص:")
    return ASK_NAME


async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["person_name"] = update.message.text
    await update.message.reply_text("اكتب المبلغ:")
    return ASK_AMOUNT


async def ask_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["amount"] = update.message.text

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("USD", callback_data="USD"),
            InlineKeyboardButton("SYP", callback_data="SYP"),
        ]
    ])
    await update.message.reply_text("اختر العملة:", reply_markup=kb)
    return ASK_CURRENCY


async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["currency"] = query.data
    await query.message.reply_text("اكتب تاريخ السداد (YYYY-MM-DD) أو 0 للتخطي:")
    return ASK_DATE


async def ask_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["due_date"] = update.message.text
    await update.message.reply_text("اكتب ملاحظة أو 0 للتخطي:")
    return ASK_NOTE


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["note"] = update.message.text

    data = context.user_data
    text = (
        f"الاسم: {data['person_name']}\n"
        f"المبلغ: {data['amount']}\n"
        f"العملة: {data['currency']}\n"
        f"التاريخ: {data['due_date']}\n"
        f"الملاحظة: {data['note']}\n\n"
        "تأكيد؟"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("تأكيد", callback_data="confirm"),
            InlineKeyboardButton("إلغاء", callback_data="cancel"),
        ]
    ])
    await update.message.reply_text(text, reply_markup=kb)
    return CONFIRM


async def save_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.message.reply_text("تم الإلغاء.")
        return ConversationHandler.END

    data = context.user_data
    db = SessionLocal()

    person = Person(name=data["person_name"], owner_user_id=update.effective_user.id)
    db.add(person)
    db.commit()
    db.refresh(person)

    debt = Debt(
        owner_user_id=update.effective_user.id,
        person_id=person.id,
        amount=data["amount"],
        currency=data["currency"],
        due_date=None if data["due_date"] == "0" else data["due_date"],
        note=None if data["note"] == "0" else data["note"],
        created_at=datetime.utcnow(),
    )

    db.add(debt)
    db.commit()
    db.close()

    await query.message.reply_text("تم إضافة الدين بنجاح.")
    return ConversationHandler.END


def get_add_debt_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_currency)],
            ASK_CURRENCY: [CallbackQueryHandler(ask_date)],
            ASK_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_note)],
            ASK_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
            CONFIRM: [CallbackQueryHandler(save_debt)],
        },
        fallbacks=[],
    )
