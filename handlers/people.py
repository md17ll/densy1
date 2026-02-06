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

def _uid(update: Update) -> int:
    return update.effective_user.id


async def _send_or_edit(update: Update, text: str, reply_markup=None, parse_mode=None):
    """
    إذا كان الضغط من زر (CallbackQuery): نعدل نفس الرسالة (edit)
    إذا كان أمر/رسالة: نرسل رسالة جديدة
    """
    if update.callback_query:
        q = update.callback_query
        try:
            await q.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            # لو ما قدر يedit (مثلاً نفس النص)، نرسل رسالة عادي
            await q.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


# =========================
# People list + Person details
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
        await _send_or_edit(update, "📭 ما في أشخاص بعد.\nاستخدم ➕ إضافة دين لإضافة أول شخص.", kb)
        return

    rows = []
    for p in people[:50]:
        rows.append([InlineKeyboardButton(p.name, callback_data=f"person_{p.id}")])

    rows.append([InlineKeyboardButton("🔎 بحث عن شخص", callback_data="search_person")])
    rows.append([InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")])

    kb = InlineKeyboardMarkup(rows)
    await _send_or_edit(update, "👥 اختر شخص لعرض ديونه:", kb)


async def show_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = _uid(update)
    data = q.data  # person_{id}

    try:
        person_id = int(data.split("_", 1)[1])
    except Exception:
        await q.message.reply_text("❌ اختيار غير صالح.")
        return

    db = SessionLocal()
    try:
        person = (
            db.query(Person)
            .filter(Person.id == person_id, Person.owner_user_id == uid)
            .first()
        )
        if not person:
            await q.message.reply_text("❌ ما لقيت هالشخص.")
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
        lines = [f"👤 **{person.name}**", "", "🧾 **الديون:**"]

        for d in debts[:30]:
            if d.currency == "USD":
                total_usd += float(d.amount)
            elif d.currency == "SYP":
                total_syp += float(d.amount)

            lines.append(f"- {d.amount:g} {d.currency}")

        lines += ["", "📌 **الإجمالي:**", f"💵 USD: {total_usd:g}", f"🇸🇾 SYP: {total_syp:g}"]

        if len(debts) > 30:
            lines += ["", "ℹ️ عرضت آخر 30 دين فقط."]

        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع للأشخاص", callback_data="people")],
        [InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")],
    ])

    # تعديل نفس الرسالة (بدون إرسال رسالة جديدة)
    await _send_or_edit(update, text, kb, parse_mode="Markdown")


# =========================
# Search conversation
# =========================

SEARCH_WAIT = 500

async def search_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🔎 اكتب اسم الشخص (أو جزء منه) للبحث:")
    return SEARCH_WAIT


async def search_start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 اكتب اسم الشخص (أو جزء منه) للبحث:")
    return SEARCH_WAIT


async def search_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    qtxt = (update.message.text or "").strip()

    if not qtxt:
        await update.message.reply_text("اكتب اسم صحيح للبحث:")
        return SEARCH_WAIT

    db = SessionLocal()
    try:
        results = (
            db.query(Person)
            .filter(Person.owner_user_id == uid, Person.name.ilike(f"%{qtxt}%"))
            .order_by(Person.id.desc())
            .all()
        )
    finally:
        db.close()

    if not results:
        await update.message.reply_text("❌ ما لقيت أي شخص بهذا الاسم.")
        return ConversationHandler.END

    rows = []
    for p in results[:50]:
        rows.append([InlineKeyboardButton(p.name, callback_data=f"person_{p.id}")])

    rows.append([InlineKeyboardButton("👥 رجوع للأشخاص", callback_data="people")])
    rows.append([InlineKeyboardButton("🏠 رجوع للقائمة", callback_data="back_main")])

    await update.message.reply_text("✅ نتائج البحث، اختر شخص:", reply_markup=InlineKeyboardMarkup(rows))
    return ConversationHandler.END


def build_search_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("search", search_start_cmd),
            CallbackQueryHandler(search_start_cb, pattern=r"^search_person$"),
        ],
        states={
            SEARCH_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_do)],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )


def get_people_handlers():
    return [
        CommandHandler("people", list_people),
        CallbackQueryHandler(list_people, pattern=r"^people$"),
        CallbackQueryHandler(show_person, pattern=r"^person_\d+$"),
        build_search_conversation(),
    ]
