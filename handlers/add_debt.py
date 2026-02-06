from decimal import Decimal, InvalidOperation
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from db import SessionLocal, User, Person, Debt

ASK_NAME, ASK_AMOUNT = range(2)


def _normalize_number(text: str) -> str:
    arabic_digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    text = (text or "").strip().translate(arabic_digits)
    text = text.replace(",", "").replace(" ", "")
    return text


def _is_allowed(uid: int, admin_ids: set[int]) -> bool:
    if uid in admin_ids:
        return True
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == uid).first()
        if not user:
            return False
        if user.is_blocked:
            return False
        if not user.is_active:
            return False
        return True
    finally:
        db.close()


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    admin_ids = set(int(x) for x in (context.bot_data.get("ADMIN_IDS", []) or []))

    if not _is_allowed(uid, admin_ids):
        msg = update.message or update.callback_query.message
        await msg.reply_text("🔒 هذا البوت مدفوع.\nيرجى التواصل مع الأدمن لتفعيل الاشتراك.")
        return ConversationHandler.END

    msg = update.message or update.callback_query.message
    await msg.reply_text("اكتب اسم الشخص:")
    return ASK_NAME


async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["person_name"] = (update.message.text or "").strip()
    await update.message.reply_text("اكتب المبلغ (مثال: 1500 أو 1,500 أو ١٥٠٠):")
    return ASK_AMOUNT


async def save_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    admin_ids = set(int(x) for x in (context.bot_data.get("ADMIN_IDS", []) or []))

    if not _is_allowed(uid, admin_ids):
        await update.message.reply_text("🔒 هذا البوت مدفوع.\nيرجى التواصل مع الأدمن لتفعيل الاشتراك.")
        return ConversationHandler.END

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
        # ✅ إنشاء شخص مع created_at حتى لا يحدث NotNullViolation
        person = Person(
            owner_user_id=uid,
            name=name,
            created_at=datetime.utcnow(),
        )
        db.add(person)
        db.commit()
        db.refresh(person)

        # إنشاء دين
        debt = Debt(
            owner_user_id=uid,
            person_id=person.id,
            amount=amount,
            currency="USD",
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


def get_add_debt_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_debt)],
        },
        fallbacks=[],
    )
