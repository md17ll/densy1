from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler

from db import SessionLocal, Person, Debt


def _get_reply_target(update: Update):
    """
    يرجّع object نقدر نعمل عليه reply_text سواء كان Command أو زر.
    """
    if update.callback_query:
        return update.callback_query.message
    return update.message


async def list_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = _get_reply_target(update)

    db = SessionLocal()
    try:
        people = (
            db.query(Person)
            .filter(Person.owner_user_id == uid)
            .order_by(Person.id.desc())
            .all()
        )
    finally:
        db.close()

    if not people:
        await msg.reply_text("لا يوجد أشخاص بعد. ابدأ بإضافة دين عبر زر ➕ أو /add")
        return

    # زر لكل شخص لعرض ديونه
    rows = []
    for p in people[:50]:
        rows.append([InlineKeyboardButton(f"👤 {p.name}", callback_data=f"person_{p.id}")])

    await msg.reply_text("اختر شخص لعرض ديونه:", reply_markup=InlineKeyboardMarkup(rows))


async def show_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data  # person_123

    try:
        person_id = int(data.split("_", 1)[1])
    except Exception:
        await query.message.reply_text("طلب غير صحيح.")
        return

    db = SessionLocal()
    try:
        person = db.query(Person).filter(Person.id == person_id, Person.owner_user_id == uid).first()
        if not person:
            await query.message.reply_text("الشخص غير موجود.")
            return

        debts = (
            db.query(Debt)
            .filter(Debt.owner_user_id == uid, Debt.person_id == person_id)
            .order_by(Debt.id.desc())
            .all()
        )
    finally:
        db.close()

    if not debts:
        await query.message.reply_text("لا يوجد ديون لهذا الشخص.")
        return

    # تجميع بسيط
    total_usd = 0.0
    total_syp = 0.0
    lines = [f"👤 الشخص: {person.name}\n"]

    for d in debts[:50]:
        if str(d.currency) == "USD":
            total_usd += float(d.amount)
        else:
            total_syp += float(d.amount)
        lines.append(f"• {d.amount} {d.currency}")

    lines.append("")
    lines.append(f"📌 الإجمالي USD: {total_usd}")
    lines.append(f"📌 الإجمالي SYP: {total_syp}")

    await query.message.reply_text("\n".join(lines))


def get_people_handlers():
    return [
        CommandHandler("people", list_people),
        CallbackQueryHandler(show_person, pattern=r"^person_\d+$"),
    ]
