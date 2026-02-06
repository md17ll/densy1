from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from db import SessionLocal, User


async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if len(context.args) != 1:
        await update.message.reply_text("الاستخدام:\n/rate 15000")
        return

    try:
        rate = float(context.args[0])
        if rate <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("اكتب رقم صحيح أكبر من 0")
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_user_id == uid).first()

        # إذا المستخدم غير موجود ننشئه لكن بدون تفعيل الاشتراك
        if not user:
            user = User(tg_user_id=uid, is_active=False, is_blocked=False)
            db.add(user)
            db.commit()
            db.refresh(user)

        # إذا محظور لا نسمح
        if user.is_blocked:
            await update.message.reply_text("🚫 أنت محظور من استخدام البوت.")
            return

        user.usd_rate = rate
        db.commit()

    except Exception:
        # أي خطأ بقاعدة البيانات يعطي رد بدل الصمت
        await update.message.reply_text("❌ صار خطأ أثناء حفظ السعر. جرّب مرة ثانية.")
        return
    finally:
        db.close()

    await update.message.reply_text(f"✅ تم تحديث سعر الدولار إلى: {rate}")


def get_rate_handlers():
    return [
        CommandHandler("rate", set_rate),
    ]
