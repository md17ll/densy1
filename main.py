import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from db import init_db, SessionLocal, User
from handlers.add_debt import get_add_debt_handler
from handlers.people import get_people_handlers
from handlers.admin_panel import get_admin_handlers
from handlers.rates import get_rate_handlers

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x}

def is_admin(uid):
    return uid in ADMIN_IDS

def check_access(uid):
    if is_admin(uid):
        return True
    db=SessionLocal()
    u=db.query(User).filter(User.tg_user_id==uid).first()
    db.close()
    return u and u.is_active

def menu(uid):
    rows=[
        [InlineKeyboardButton("➕ إضافة دين",callback_data="add")],
        [InlineKeyboardButton("👥 الأشخاص",callback_data="people")],
        [InlineKeyboardButton("💱 سعر الدولار",callback_data="rate")],
        [InlineKeyboardButton("❓ المساعدة",callback_data="help")]
    ]
    if is_admin(uid):
        rows.append([InlineKeyboardButton("👑 لوحة الأدمن",callback_data="admin")])
    return InlineKeyboardMarkup(rows)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if not check_access(uid):
        await update.message.reply_text("🔒 هذا البوت مدفوع. تواصل مع الأدمن.")
        return
    await update.message.reply_text("مرحباً بك",reply_markup=menu(uid))

async def buttons(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    uid=q.from_user.id

    if not check_access(uid):
        await q.message.reply_text("🔒 غير مفعل الاشتراك")
        return

    if q.data=="add":
        await q.message.reply_text("اكتب /add")
    elif q.data=="people":
        await q.message.reply_text("اكتب /people")
    elif q.data=="rate":
        await q.message.reply_text("اكتب /rate 15000")

def main():
    init_db()
    app=Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(get_add_debt_handler())

    for h in get_people_handlers():
        app.add_handler(h)
    for h in get_admin_handlers():
        app.add_handler(h)
    for h in get_rate_handlers():
        app.add_handler(h)

    app.run_polling()

if __name__=="__main__":
    main()
