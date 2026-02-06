from datetime import datetime
from decimal import Decimal, InvalidOperation

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)

from db import SessionLocal, Person, Debt

ASK_NAME, ASK_AMOUNT, ASK_CURRENCY, ASK_DATE, ASK_NOTE, CONFIRM = range(6)

def _parse_amount(text: str) -> Decimal | None:
    t = text.strip().replace(",", "")
    try:
        val = Decimal(t)
        if val <= 0:
            return None
        return val.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None

def _parse_date(text: str):
    t = text.strip()
    if t == "0":
        return None
    try:
        return datetime.strptime(t, "%Y-%m-%d").date()
    except ValueError:
        return "INVALID"

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✍️ اكتب اسم الشخص:")
    return ASK_NAME

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ الاسم لا يمكن أن يكون فارغًا. اكتب اسم الشخص:")
        return ASK_NAME

    context.user_data["person_name"] = name
    await update.message.reply_text("💰 اكتب المبلغ (مثال: 25 أو 25.50):")
    return ASK_AMOUNT

async def ask_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = _parse_amount(update.message.text)
    if amount is None:
        await update.message.reply_text("❌ مبلغ غير صحيح. اكتب المبلغ مرة ثانية (مثال: 25 أو 25.50):")
        return ASK_AMOUNT

    context.user_data["amount"] = amount

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("USD", callback_data="USD"),
         InlineKeyboardButton("SYP", callback_data="SYP")]
    ])
    await update.message.reply_text("💱 اختر العملة:", reply_markup=kb)
    return ASK_CURRENCY

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["currency"] = query.data

    await query.message.reply_text("📅 اكتب تاريخ السداد (YYYY-MM-DD) أو 0 للتخطي:")
    return ASK_DATE

async def ask_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = _parse_date(update.message.text)
    if parsed == "INVALID":
        await update.message.reply_text("❌ التاريخ غير صحيح. اكتب بصيغة YYYY-MM-DD أو 0 للتخطي:")
        return ASK_DATE

    context.user_data["due_date"] = parsed
    await update.message.reply_text("📝 اكتب ملاحظة أو 0 للتخطي:")
    return ASK_NOTE

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    context.user_data["note"] = None if note == "0" else note

    d = context.user_data
    txt = (
        "✅ تأكيد إضافة الدين:\n\n"
        f"👤 الاسم: {d['person_name']}\n"
        f"💰 المبلغ: {d['amount']}\n"
        f"💱 العملة: {d['currency']}\n"
        f"📅 تاريخ السداد: {d['due_date'] if d['due_date'] else '—'}\n"
        f"📝 ملاحظة: {d['note'] if d['note'] else '—'}\n"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد", callback_data="confirm"),
         InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
    ])
    await update.message.reply_text(txt, reply_markup=kb)
    return CONFIRM

async def save_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.message.reply_text("تم الإلغاء.")
        return ConversationHandler.END

    uid = query.from_user.id
    d = context.user_data

    db = SessionLocal()
    try:
        person = db.query(Person).filter(
            Person.owner_user_id == uid,
            Person.name == d["person_name"]
        ).first()

        if not person:
            person = Person(owner_user_id=uid, name=d["person_name"])
            db.add(person)
            db.commit()
            db.refresh(person)

        debt = Debt(
            owner_user_id=uid,
            person_id=person.id,
            amount=d["amount"],
            currency=d["currency"],
            due_date=d["due_date"],
            note=d["note"],
            created_at=datetime.utcnow(),
        )
        db.add(debt)
        db.commit()
    finally:
        db.close()

    await query.message.reply_text("✅ تم إضافة الدين بنجاح.")
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
