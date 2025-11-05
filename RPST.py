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

# --- [ 1. Settings ] ---
# Read variables from Railway
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

# --- [ 2. Bot Functions ] ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message"""
    user_id = update.message.from_user.id
    
    if user_id == ADMIN_ID:
        # --- [ 🟢 تم تعديل هذا السطر 🟢 ] ---
        await update.message.reply_text("Hello Admin. This is your support bot. Any message you receive here, reply to it to send your response to the user.")
    else:
        welcome_text = (
            "Welcome to the Random Partner Support Team 🎲\n\n"
            "If you have made a payment, please send a screenshot of the payment notification and wait for our technical team to respond."
        )
        await update.message.reply_text(welcome_text)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(For normal user) Receive message and forward to admin"""
    user = update.message.from_user
    logger.info(f"New message from user {user.id} ({user.first_name})")
    
    # Alert message for the user
    await update.message.reply_text("✅ Your message has been sent to support. Please wait...")
    
    # Forward the user's original message to the admin
    try:
        await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=user.id,
            message_id=update.message.message_id
        )
    except Exception as e:
        logger.error(f"Failed to forward message from {user.id}: {e}")
        await update.message.reply_text("Sorry, an error occurred while sending your message. Please try again.")
        # Send a notification to the admin if forwarding fails (due to privacy settings)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ Failed to receive message from user {user.id} ({user.first_name}).\n"
                 f"Possible reason: User's privacy settings prevent forwarding."
        )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(For Admin) Receive reply and send to the original user"""
    
    # Check if the message is a reply
    if not update.message.reply_to_message:
        await update.message.reply_text("To send a reply, you must use the 'Reply' feature on the user's message.")
        return

    # Check if replying to a forwarded message
    if not update.message.reply_to_message.forward_from:
        await update.message.reply_text("Error: You are not replying to a user's message. Please reply to the forwarded message.")
        return
    
    # Get the original user's ID
    original_user_id = update.message.reply_to_message.forward_from.id
    admin_message_id = update.message.message_id
    
    logger.info(f"Admin replying to user {original_user_id}")
    
    try:
        # Copy the admin's message (text, photo, sticker, etc.) and send to the user
        await context.bot.copy_message(
            chat_id=original_user_id,
            from_chat_id=ADMIN_ID,
            message_id=admin_message_id
        )
        # Notify the admin of success
        await update.message.reply_text("✅ Your reply has been sent to the user.")
        
    except Exception as e:
        logger.error(f"Failed to send admin reply to {original_user_id}: {e}")
        await update.message.reply_text(f"❌ Failed to send reply to user {original_user_id}. Reason: {e}")

# --- [ 3. Main Function ] ---

def main():
    if not TOKEN:
        logger.critical("CRITICAL: BOT_TOKEN not found.")
        return
    logger.info("Support Bot starting up...")
    
    application = Application.builder().token(TOKEN).build()

    # /start command for everyone
    application.add_handler(CommandHandler("start", start_command))

    # Handler for Admin replies (only admin + only replies)
    application.add_handler(MessageHandler(
        filters.User(user_id=ADMIN_ID) & filters.REPLY, 
        handle_admin_reply
    ))
    
    # Handler for user messages (only private messages + not from admin)
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (~filters.User(user_id=ADMIN_ID)), 
        handle_user_message
    ))

    logger.info("Bot setup complete. Starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
