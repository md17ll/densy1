from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from db import SessionLocal, Person, Debt


# =========================
# أدوات
# =========================

def _uid(update: Update) -> int:
    return update.effective_user.id


async def _send_or_edit(update: Update, text: str, reply_markup=None, parse_mode=None):
    if update.callback_query:
        q = update.callback_query
        try:
            await q.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            await q.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


# =========================
# قائمة الأشخاص
# =========================

async def list_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    uid = _uid(update)

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
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")]
        ])
        await _send_or_edit(update, "📭 ما في أشخاص بعد.", kb)
        return

    rows = []
    for p in people[:50]:
        rows.append([InlineKeyboardButton(p.name, callback_data=f"person_{p.id}")])

    rows.append([InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")])

    await _send_or_edit(update, "👥 اختر شخص:", InlineKeyboardMarkup(rows))


# =========================
# عرض شخص
# =========================

async def show_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = _uid(update)
    person_id = int(q.data.split("_")[1])

    db = SessionLocal()
    try:
        person = (
            db.query(Person)
            .filter(Person.id == person_id, Person.owner_user_id == uid)
            .first()
        )

        debts = (
            db.query(Debt)
            .filter(Debt.person_id == person.id)
            .all()
        )
    finally:
        db.close()

    if not debts:
        text = f"👤 {person.name}\n\nلا يوجد ديون."
    else:
        lines = [f"👤 {person.name}", "", "الديون:"]
        for d in debts:
            lines.append(f"- {d.amount:g} {d.currency}")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 حذف كل الديون", callback_data=f"delete_all_{person.id}")],
        [InlineKeyboardButton("✏️ تسديد جزئي", callback_data=f"partial_{person.id}")],
        [InlineKeyboardButton("🔙 رجوع للأشخاص", callback_data="people")],
        [InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")],
    ])

    await _send_or_edit(update, text, kb)


# =========================
# حذف كامل
# =========================

async def delete_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = _uid(update)
    person_id = int(q.data.split("_")[2])

    db = SessionLocal()
    try:
        db.query(Debt).filter(
            Debt.person_id == person_id,
            Debt.owner_user_id == uid
        ).delete()
        db.commit()
    finally:
        db.close()

    await q.edit_message_text("✅ تم حذف جميع ديون الشخص.")


# =========================
# تسديد جزئي
# =========================

PARTIAL_WAIT = 1000

async def partial_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    person_id = int(q.data.split("_")[1])
    context.user_data["partial_person"] = person_id

    await q.edit_message_text("اكتب مبلغ التسديد:")
    return PARTIAL_WAIT


async def partial_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    person_id = context.user_data.get("partial_person")

    try:
        paid = float(update.message.text)
    except:
        await update.message.reply_text("اكتب رقم صحيح")
        return PARTIAL_WAIT

    db = SessionLocal()
    try:
        debt = (
            db.query(Debt)
            .filter(Debt.person_id == person_id, Debt.owner_user_id == uid)
            .first()
        )

        if not debt:
            await update.message.reply_text("لا يوجد دين")
            return ConversationHandler.END

        debt.amount -= paid
        if debt.amount <= 0:
            db.delete(debt)

        db.commit()
    finally:
        db.close()

    await update.message.reply_text("✅ تم تسجيل التسديد")
    return ConversationHandler.END


def build_partial_conv():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(partial_start, pattern=r"^partial_\d+$")
        ],
        states={
            PARTIAL_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, partial_save)],
        },
        fallbacks=[],
    )


def get_people_handlers():
    return [
        CommandHandler("people", list_people),
        CallbackQueryHandler(list_people, pattern=r"^people$"),
        CallbackQueryHandler(show_person, pattern=r"^person_\d+$"),
        CallbackQueryHandler(delete_all, pattern=r"^delete_all_\d+$"),
        build_partial_conv(),
    ]
