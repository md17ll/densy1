from telegram.ext import *
from telegram import Update
from db import SessionLocal, Person, Debt

ASK_NAME,ASK_AMOUNT=range(2)

async def add_start(update:Update,context):
    await update.message.reply_text("اسم الشخص:")
    return ASK_NAME

async def ask_amount(update:Update,context):
    context.user_data["name"]=update.message.text
    await update.message.reply_text("المبلغ:")
    return ASK_AMOUNT

async def save(update:Update,context):
    db=SessionLocal()
    p=Person(owner_user_id=update.effective_user.id,name=context.user_data["name"])
    db.add(p); db.commit(); db.refresh(p)
    d=Debt(owner_user_id=update.effective_user.id,person_id=p.id,amount=update.message.text)
    db.add(d); db.commit(); db.close()
    await update.message.reply_text("تم الحفظ")
    return ConversationHandler.END

def get_add_debt_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("add",add_start)],
        states={
            ASK_NAME:[MessageHandler(filters.TEXT,ask_amount)],
            ASK_AMOUNT:[MessageHandler(filters.TEXT,save)]
        },
        fallbacks=[]
    )
