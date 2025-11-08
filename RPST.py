import os
import logging
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters,
    ContextTypes,
    PicklePersistence  # نحتاجه لحفظ بيانات المستخدم
)

# --- [ 1. Settings ] ---
try:
    TOKEN = os.environ['BOT_TOKEN']
    ADMIN_ID = int(os.environ['ADMIN_ID'])
except KeyError as e:
    logging.critical(f"CRITICAL: Missing environment variable {e}. Bot cannot start.")
    raise
except ValueError:
    logging.critical("CRITICAL: ADMIN_ID environment variable is not a valid number.")
    raise

PERSISTENCE_FILE = 'bot_data.pkl'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- [ 2. Bot Functions ] ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message"""
    user_id = update.message.from_user.id
    
    if user_id == ADMIN_ID:
        # [ 🟢 تم تعديل رسالة المدير ]
        await update.message.reply_text(
            "أهلاً أيها المدير.\n"
            "ستصلك رسائل المستخدمين (كنسخة) ومعها رسالة منفصلة بمعلومات المستخدم (ID والمعرف).\n"
            " للرد: قم 'بالرد' (Reply) على **رسالة المستخدم الأصلية** (النص أو الصورة)، وليس على رسالة المعلومات."
        )
    else:
        welcome_text = (
            "مرحباً بك في فريق دعم Random Partner 🎲\n\n"
            "إذا قمت بالدفع، أرسل لقطة شاشة لإشعار الدفع وانتظر رد الفريق التقني."
        )
        await update.message.reply_text(welcome_text)

# [ 🟢 تم إعادة كتابة هذه الدالة بالكامل 🟢 ]
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(للمستخدم العادي) يستقبل الرسالة، ينسخها، ويرسلها للمدير مع المعلومات"""
    user = update.message.from_user
    logger.info(f"New message from user {user.id} ({user.first_name})")
    
    # 1. إشعار المستخدم
    await update.message.reply_text("✅ تم إرسال رسالتك للدعم. فضلاً انتظر...")
    
    try:
        # 2. نقوم بنسخ رسالة المستخدم (صورة، نص، ...) إلى المدير
        copied_msg = await context.bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=user.id,
            message_id=update.message.message_id
        )
        
        # 3. تحضير رسالة المعلومات
        username = f"@{user.username}" if user.username else "لا يوجد"
        info_text = (
            f"--- رسالة دعم جديدة ---\n"
            f"👤 **الاسم:** {user.first_name}\n"
            f"🔗 **المعرف:** {username}\n"
            f"🆔 **الأي دي (ID):** `{user.id}`\n\n"
            f"(للرد، قم بالرد على الرسالة *أعلى* هذا النص)"
        )

        # 4. إرسال المعلومات للمدير كـ "رد" على الرسالة المنسوخة
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=info_text,
            reply_to_message_id=copied_msg.message_id,
            parse_mode='Markdown'
        )
        
        # 5. نقوم بتخزين هوية المستخدم وربطها بهوية الرسالة المنسوخة
        context.bot_data.setdefault('user_map', {})
        context.bot_data['user_map'][copied_msg.message_id] = user.id
        
    except Exception as e:
        logger.error(f"Failed to copy/send info for message from {user.id}: {e}")
        await update.message.reply_text("عذراً، حدث خطأ أثناء إرسال رسالتك. حاول مجدداً.")
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ فشل استقبال رسالة من المستخدم {user.id} ({user.first_name}). السبب: {e}"
        )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(للمدير) يستقبل الرد ويرسله للمستخدم الأصلي (باسم البوت)"""
    
    if not update.message.reply_to_message:
        await update.message.reply_text("لإرسال رد، يجب استخدام ميزة 'الرد' (Reply) على رسالة المستخدم.")
        return

    replied_msg = update.message.reply_to_message
    admin_message_id = update.message.message_id
    
    original_user_id = None
    
    # [ 🟢 هذا الكود سيعمل بشكل صحيح الآن 🟢 ]
    # نبحث عن الأي دي في قاعدة بياناتنا
    user_map = context.bot_data.get('user_map', {})
    
    # 1. هل المدير رد على الرسالة المنسوخة الأصلية؟
    original_user_id = user_map.get(replied_msg.message_id)
    
    # 2. هل المدير رد على "رسالة المعلومات" بدلاً من ذلك؟
    if not original_user_id and replied_msg.reply_to_message:
        # نعم، هو رد على رسالتنا. لنجلب الرسالة التي "قبلها"
        original_copied_msg = replied_msg.reply_to_message
        original_user_id = user_map.get(original_copied_msg.message_id)
        
    # 3. إذا فشلت كل الطرق
    if not original_user_id:
        await update.message.reply_text(
            "❌ خطأ: لا يمكن العثور على المستخدم.\n"
            "الرجاء الرد *مباشرة* على رسالة المستخدم (الصورة/النص)، وليس على رسالة المعلومات التي يرسلها البوت."
        )
        return
    
    logger.info(f"Admin replying to user {original_user_id}")
    
    try:
        # [ 🟢 هذه الدالة تخفي هوية المدير 🟢 ]
        # نسخ رسالة المدير وإرسالها للمستخدم (باسم البوت)
        await context.bot.copy_message(
            chat_id=original_user_id,
            from_chat_id=ADMIN_ID,
            message_id=admin_message_id
        )
        await update.message.reply_text("✅ تم إرسال ردك للمستخدم.")
        
    except Exception as e:
        logger.error(f"Failed to send admin reply to {original_user_id}: {e}")
        await update.message.reply_text(f"❌ فشل إرسال الرد للمستخدم {original_user_id}. السبب: {e}")

# --- [ 3. Main Function ] ---

def main():
    if not TOKEN:
        logger.critical("CRITICAL: BOT_TOKEN not found.")
        return
    logger.info("Support Bot starting up...")
    
    my_persistence = PicklePersistence(filepath=PERSISTENCE_FILE)
    
    application = Application.builder().token(TOKEN).persistence(my_persistence).build()

    application.add_handler(CommandHandler("start", start_command))

    application.add_handler(MessageHandler(
        filters.User(user_id=ADMIN_ID) & filters.REPLY, 
        handle_admin_reply
    ))
    
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (~filters.User(user_id=ADMIN_ID)), 
        handle_user_message
    ))

    logger.info("Bot setup complete. Starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
