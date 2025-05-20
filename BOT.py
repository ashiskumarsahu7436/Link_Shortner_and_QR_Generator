import logging
import os
import requests
import qrcode
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get tokens from environment variables
TINYURL_TOKEN = os.getenv("TINYURL_TOKEN", "IZf4x5CzR0BgBDnfccljA0hLNW7sXxlqkhMJGxAzFQ9NnDWhpWVlLZF4fAzy")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7761119758:AAG4tpaHHCa4ktrBQtHybABI-RVl1zRErYg")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set this in Render

# Dictionary to temporarily store user URLs
user_url_map = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me any URL and I'll either shorten it or generate a QR code."
    )

def shorten_url(long_url: str) -> str | None:
    api_url = "https://api.tinyurl.com/create"
    headers = {
        "Authorization": f"Bearer {TINYURL_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "url": long_url,
        "domain": "tiny.one"
    }
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data['data']['tiny_url']
    except Exception as e:
        logger.error(f"Error shortening URL: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.message.from_user.id

    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ Please send a valid URL starting with http:// or https://")
        return

    user_url_map[user_id] = url  # Store the URL temporarily

    keyboard = [
        [
            InlineKeyboardButton("Shorten it", callback_data="shorten"),
            InlineKeyboardButton("Generate QR Code", callback_data="qr")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("What would you like to do with this URL?", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    url = user_url_map.get(user_id)

    if not url:
        await query.edit_message_text("❌ No URL found. Please send a new one.")
        return

    if query.data == "shorten":
        await query.edit_message_text("⏳ Shortening your link...")
        short_url = shorten_url(url)
        if short_url:
            await query.message.reply_text(f"✅ Here is your shortened URL:\n{short_url}")
        else:
            await query.message.reply_text("❌ Failed to shorten the link.")

    elif query.data == "qr":
        await query.edit_message_text("⏳ Generating QR code...")
        try:
            img = qrcode.make(url)
            bio = BytesIO()
            bio.name = 'qr.png'
            img.save(bio, 'PNG')
            bio.seek(0)
            await query.message.reply_photo(photo=bio, caption="✅ Here is your QR code.")
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            await query.message.reply_text("❌ Failed to generate QR code.")

async def set_webhook(app):
    if WEBHOOK_URL:
        await app.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Webhook or polling based on environment
    if WEBHOOK_URL:
        # For Render/Production
        port = int(os.environ.get('PORT', 5000))
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=WEBHOOK_URL,
            secret_token='WEBHOOK_SECRET_TOKEN'  # Optional security
        )
    else:
        # For local development
        print("🤖 Bot is running in polling mode...")
        app.run_polling()

if __name__ == "__main__":
    main()
