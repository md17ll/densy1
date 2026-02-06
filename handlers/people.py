from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from db import SessionLocal, Person, Debt


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
            lines.append(f"- {d.amount} {d.currency}")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 حذف دين كامل", callback_data=f"delete_all_{person.id}")],
        [InlineKeyboardButton("✏️ تسديد جزئي", callback_data=f"partial_{person.id}")],
        [InlineKeyboardButton("🔙 رجوع للأشخاص", callback_data="people")],
        [InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")],
    ])

    await _send_or_edit(update, text, kb)


def get_people_handlers():
    return [
        CommandHandler("people", list_people),
        CallbackQueryHandler(list_people, pattern=r"^people$"),
        CallbackQueryHandler(show_person, pattern=r"^person_\d+$"),
    ]
