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
# Helpers
# =========================

def _msg(update: Update):
    """Return the right message object whether it's a command message or callback query."""
    if update.callback_query:
        return update.callback_query.message
    return update.message


def _uid(update: Update) -> int:
    return update.effective_user.id


# =========================
# People list + Person details
# =========================

async def list_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show people list as inline buttons."""
    if update.callback_query:
        await update.callback_query.answer()

    uid = _uid(update)
    m = _msg(update)

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
        await m.reply_text("📭 ما في أشخاص بعد.\nاستخدم ➕ إضافة دين لإضافة أول شخص.")
        return

    rows = []
    for p in people[:50]:  # حد أقصى 50 زر حتى ما تطول
        rows.append([InlineKeyboardButton(p.name, callback_data=f"person_{p.id}")])

    rows.append([InlineKeyboardButton("🔎 بحث عن شخص", callback_data="search")])
    rows.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back")])

    await m.reply_text("👥 اختر شخص لعرض ديونه:", reply_markup=InlineKeyboardMarkup(rows))


async def show_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when user clicks a person button."""
    query = update.callback_query
    await query.answer()

    uid = _uid(update)
    m = query.message

    data = query.data  # person_{id}
    try:
        person_id = int(data.split("_", 1)[1])
    except Exception:
        await m.reply_text("❌ اختيار غير صالح.")
        return

    db = SessionLocal()
    try:
        person = (
            db.query(Person)
            .filter(Person.id == person_id, Person.owner_user_id == uid)
            .first()
        )
        if not person:
            await m.reply_text("❌ ما لقيت هالشخص.")
            return

        debts = (
            db.query(Debt)
            .filter(Debt.person_id == person.id, Debt.owner_user_id == uid)
            .order_by(Debt.id.desc())
            .all()
        )
    finally:
        db.close()

    if not debts:
        text = f"👤 **{person.name}**\n\n📭 ما في ديون مسجلة لهالشخص."
    else:
        total_usd = 0.0
        total_syp = 0.0

        lines = [f"👤 **{person.name}**", ""]
        lines.append("🧾 **الديون:**")

        for d in debts[:30]:  # نعرض آخر 30
            if d.currency == "USD":
                total_usd += float(d.amount)
            elif d.currency == "SYP":
                total_syp += float(d.amount)

            lines.append(f"- {d.amount:g} {d.currency}")

        lines.append("")
        lines.append(f"📌 **الإجمالي:**")
        lines.append(f"💵 USD: {total_usd:g}")
        lines.append(f"🇸🇾 SYP: {total_syp:g}")

        if len(debts) > 30:
            lines.append("")
            lines.append("ℹ️ عرضت آخر 30 دين فقط.")

        text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔙 رجوع للأشخاص", callback_data="people")],
            [InlineKeyboardButton("🔎 بحث عن شخص", callback_data="search")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back")],
        ]
    )

    await m.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


# =========================
# Search conversation
# =========================

SEARCH_WAIT = 500

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start search from /search command."""
    uid = _uid(update)
    m = _msg(update)
    await m.reply_text("🔎 اكتب اسم الشخص (أو جزء منه) للبحث:")
    return SEARCH_WAIT


async def search_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start search from button."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🔎 اكتب اسم الشخص (أو جزء منه) للبحث:")
    return SEARCH_WAIT


async def search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    m = update.message

    q = (m.text or "").strip()
    if not q:
        await m.reply_text("اكتب اسم صحيح للبحث:")
        return SEARCH_WAIT

    db = SessionLocal()
    try:
        results = (
            db.query(Person)
            .filter(Person.owner_user_id == uid, Person.name.ilike(f"%{q}%"))
            .order_by(Person.id.desc())
            .all()
        )
    finally:
        db.close()

    if not results:
        await m.reply_text("❌ ما لقيت أي شخص بهذا الاسم.\nجرّب اسم ثاني.")
        return ConversationHandler.END

    rows = []
    for p in results[:50]:
        rows.append([InlineKeyboardButton(p.name, callback_data=f"person_{p.id}")])

    rows.append([InlineKeyboardButton("👥 كل الأشخاص", callback_data="people")])
    rows.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back")])

    await m.reply_text("✅ نتائج البحث، اختر شخص:", reply_markup=InlineKeyboardMarkup(rows))
    return ConversationHandler.END


def build_search_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("search", search_start),
            CallbackQueryHandler(search_start_cb, pattern=r"^search$"),
        ],
        states={
            SEARCH_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_do)],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=True,
    )


# =========================
# Export handlers
# =========================

def get_people_handlers():
    return [
        CommandHandler("people", list_people),
        CallbackQueryHandler(list_people, pattern=r"^people$"),
        CallbackQueryHandler(show_person, pattern=r"^person_\d+$"),
        build_search_conversation(),
    ]
