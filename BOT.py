import os
import logging
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
    CallbackQueryHandler,
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configs (set these in Render environment variables)
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TINYURL_TOKEN = os.getenv("TINYURL_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Format: https://your-service-name.onrender.com

# Temporary storage for user URLs
user_urls = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command"""
    await update.message.reply_text(
        "🌟 Welcome! Send me a URL, and I'll:\n"
        "- Shorten it with TinyURL\n"
        "- Generate a QR code\n\n"
        "Try it now!"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process incoming URLs"""
    url = update.message.text.strip()
    user_id = update.message.from_user.id

    # Validate URL
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("⚠️ Please send a valid URL (e.g., https://example.com)")
        return

    # Store URL temporarily
    user_urls[user_id] = url

    # Show options
    keyboard = [
        [InlineKeyboardButton("🔗 Shorten URL", callback_data="shorten")],
        [InlineKeyboardButton("📲 QR Code", callback_data="qr")],
    ]
    await update.message.reply_text(
        "Choose an action:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    url = user_urls.get(user_id)

    if not url:
        await query.edit_message_text("❌ Session expired. Please send a new URL.")
        return

    if query.data == "shorten":
        await query.edit_message_text("⏳ Shortening URL...")
        short_url = await shorten_url(url)
        await query.message.reply_text(f"✅ Short URL:\n{short_url}" if short_url else "❌ Failed to shorten URL")

    elif query.data == "qr":
        await query.edit_message_text("⏳ Generating QR Code...")
        qr_file = await generate_qr(url)
        if qr_file:
            await query.message.reply_photo(photo=qr_file, caption="Here's your QR Code!")
        else:
            await query.message.reply_text("❌ Failed to generate QR code")

async def shorten_url(long_url: str) -> str:
    """Shorten URL using TinyURL API"""
    try:
        response = requests.post(
            "https://api.tinyurl.com/create",
            headers={"Authorization": f"Bearer {TINYURL_TOKEN}"},
            json={"url": long_url, "domain": "tiny.one"},
            timeout=5
        )
        return response.json()["data"]["tiny_url"]
    except Exception as e:
        logger.error(f"Shorten error: {e}")
        return None

async def generate_qr(url: str) -> BytesIO:
    """Generate QR code image"""
    try:
        img = qrcode.make(url)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.error(f"QR error: {e}")
        return None

def main():
    # Validate config
    if not all([BOT_TOKEN, TINYURL_TOKEN, WEBHOOK_URL]):
        logger.error("❌ Missing environment variables!")
        return

    # Build bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_click))

    # Start webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8443)),
        webhook_url=f"{WEBHOOK_URL}/webhook",
        secret_token=os.getenv("WEBHOOK_SECRET")  # Optional security
    )

if __name__ == "__main__":
    main()