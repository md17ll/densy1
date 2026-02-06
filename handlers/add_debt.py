from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from db import SessionLocal, User, Person, Debt

ASK_NAME, ASK_AMOUNT = range(2)


def _normalize_number(text: str) -> str:
    arabic_digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    text = (text or "").strip().translate(arabic_digits)
    text = text.replace(",", "").replace(" ", "")
    return text


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if update.callback_query:
        await update.callback_query.answer()

    if not msg:
        return ConversationHandler.END

    await msg.reply_text("اكتب اسم الشخص:")
    return ASK_NAME


async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["person_name"] = (update.message.text or "").strip()
    await update.message.reply_text("اكتب المبلغ (مثال: 1500 أو 1,500 أو ١٥٠٠):")
    return ASK_AMOUNT


async def save_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = (context.user_data.get("person_name") or "").strip()
    raw_amount = update.message.text or ""

    try:
        normalized = _normalize_number(raw_amount)
        amount = Decimal(normalized)
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await update.message.reply_text("❌ اكتب رقم صحيح أكبر من 0 (مثال: 1500)")
        return ASK_AMOUNT

    db = SessionLocal()
    try:
        person = Person(owner_user_id=uid, name=name)
        db.add(person)
        db.commit()
        db.refresh(person)

        debt = Debt(
            owner_user_id=uid,
            person_id=person.id,
            amount=amount,
            currency="USD",
            note=None,
            due_date=None,
        )
        db.add(debt)
        db.commit()

    except Exception as e:
        db.rollback()
        print("SAVE_DEBT_ERROR:", repr(e))
        await update.message.reply_text("❌ صار خطأ أثناء حفظ الدين. جرّب مرة ثانية.")
        return ConversationHandler.END
    finally:
        db.close()

    await update.message.reply_text("✅ تمت إضافة الدين بنجاح")
    return ConversationHandler.END


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم إلغاء الإضافة.")
    return ConversationHandler.END


def get_add_debt_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start),
            CallbackQueryHandler(add_start, pattern="^add$"),
        ],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_debt)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
        allow_reentry=True,
    )
