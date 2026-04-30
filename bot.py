import html
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
TARGET_CHAT_ID = int(os.environ["TARGET_CHAT_ID"])

START_TEXT = (
    "Please tell us where you are located and describe the situation you are in."
)
SENT_TEXT = "✅ Sent. An active VSS will contact you."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(START_TEXT)


async def forward_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # only forward private DMs to the bot
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    display_name = html.escape(user.full_name or "Unknown")
    profile_link = f"tg://user?id={user.id}"
    if user.username:
        link_text = f"@{html.escape(user.username)}"
    else:
        link_text = "profile"
    header = (
        f"📩 From {display_name} "
        f'(<a href="{profile_link}">{link_text}</a>, id={user.id})'
    )

    if update.message.text:
        message_text = html.escape(update.message.text)
        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"{header}\n\n{message_text}",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    else:
        await context.bot.copy_message(
            chat_id=TARGET_CHAT_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            caption=header,
            parse_mode="HTML",
        )

    await update.message.reply_text(SENT_TEXT)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_to_group))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
