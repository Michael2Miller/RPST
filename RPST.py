import os
import logging
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters,
    ContextTypes
)

# --- [ 1. الإعدادات ] ---
# اقرأ المتغيرات من Railway
try:
    TOKEN = os.environ['BOT_TOKEN']
    ADMIN_ID = int(os.environ['ADMIN_ID'])
except KeyError as e:
    logging.critical(f"CRITICAL: Missing environment variable {e}. Bot cannot start.")
    raise
except ValueError:
    logging.critical("CRITICAL: ADMIN_ID environment variable is not a valid number.")
    raise

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- [ 2. دوال البوت ] ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة ترحيبية"""
    user_id = update.message.from_user.id
    
    if user_id == ADMIN_ID:
        await update.message.reply_text("مرحباً أيها الأدمن. هذا هو بوت الدعم الخاص بك. أي رسالة تصلك من هنا، قم بالرد عليها لإرسالها للمستخدم.")
    else:
        await update.message.reply_text("مرحباً بك في بوت الدعم. أرسل رسالتك (أو لقطة الشاشة) وسيقوم الأدمن بالرد عليك قريباً.")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(للمستخدم العادي) استلام الرسالة وإعادة توجيهها للأدمن"""
    user = update.message.from_user
    logger.info(f"New message from user {user.id} ({user.first_name})")
    
    # رسالة تنبيهية للمستخدم
    await update.message.reply_text("✅ تم إرسال رسالتك إلى الدعم. يرجى الانتظار...")
    
    # إعادة توجيه رسالة المستخدم الأصلية إلى الأدمن
    # هذا يحافظ على هوية المرسل (forward_from) ليتمكن الأدمن من الرد
    try:
        await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=user.id,
            message_id=update.message.message_id
        )
    except Exception as e:
        logger.error(f"Failed to forward message from {user.id}: {e}")
        await update.message.reply_text("عذراً، حدث خطأ أثناء إرسال رسالتك. حاول مجدداً.")
        # إرسال إشعار للأدمن في حال فشل التوجيه (بسبب إعدادات الخصوصية)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ فشل استلام رسالة من المستخدم {user.id} ({user.first_name}).\n"
                 f"السبب المحتمل: قام المستخدم بتفعيل إعدادات خصوصية تمنع إعادة التوجيه."
        )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(للأدمن) استلام الرد وإرساله للمستخدم الأصلي"""
    
    # التأكد أن الرسالة هي رد (Reply)
    if not update.message.reply_to_message:
        await update.message.reply_text("لإرسال رد، يجب أن تستخدم ميزة 'الرد' (Reply) على رسالة المستخدم.")
        return

    # التأكد أن الرد على رسالة مُعادة التوجيه (Forwarded)
    if not update.message.reply_to_message.forward_from:
        await update.message.reply_text("خطأ: أنت لا ترد على رسالة مستخدم. يرجى الرد على الرسالة الموجهة.")
        return
    
    # الحصول على ID المستخدم الأصلي
    original_user_id = update.message.reply_to_message.forward_from.id
    admin_message_id = update.message.message_id
    
    logger.info(f"Admin replying to user {original_user_id}")
    
    try:
        # نسخ رسالة الأدمن (سواء كانت نص، صورة، ملصق) وإرسالها للمستخدم
        await context.bot.copy_message(
            chat_id=original_user_id,
            from_chat_id=ADMIN_ID,
            message_id=admin_message_id
        )
        # إبلاغ الأدمن بنجاح الإرسال
        await update.message.reply_text("✅ تم إرسال ردك للمستخدم.")
        
    except Exception as e:
        logger.error(f"Failed to send admin reply to {original_user_id}: {e}")
        await update.message.reply_text(f"❌ فشل إرسال الرد للمستخدم {original_user_id}. السبب: {e}")

# --- [ 3. دالة التشغيل ] ---

def main():
    if not TOKEN:
        logger.critical("CRITICAL: BOT_TOKEN not found.")
        return
    logger.info("Support Bot starting up...")
    
    application = Application.builder().token(TOKEN).build()

    # أمر /start للجميع
    application.add_handler(CommandHandler("start", start_command))

    # مستجيب لردود الأدمن (فقط الأدمن + فقط الردود)
    application.add_handler(MessageHandler(
        filters.User(user_id=ADMIN_ID) & filters.REPLY, 
        handle_admin_reply
    ))
    
    # مستجيب لرسائل المستخدمين (فقط الرسائل الخاصة + ليس من الأدمن)
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (~filters.User(user_id=ADMIN_ID)), 
        handle_user_message
    ))

    logger.info("Bot setup complete. Starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
