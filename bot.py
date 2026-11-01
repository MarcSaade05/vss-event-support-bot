"""Private-message intake for a volunteer VSS team. No report database."""
from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

LOG = logging.getLogger("vss_bot")
TEXT = {
    'start': 'Hello. If you feel unsafe or uncomfortable at an École Polytechnique social event, you can use this bot to discreetly alert the trained VSS responders on duty. Share your exact location (event, room or nearby landmark) and what help you need, at your own pace. Text, photos, documents and voice messages are accepted.\n\nYour message, Telegram name and profile will be shared with the response team so they can contact you and, where possible, come to your location. See /privacy for details. Availability depends on the team on duty; this bot is not an emergency service.',
    'privacy': 'Your messages and Telegram identity are shared with the configured VSS team group. This is not anonymous. The bot does not save report content or identities to files or a database. Telegram and group members may retain messages. Technical bot logs do not contain report text. Contact the team for requests concerning your messages. Avoid unnecessary personal information.',
    'sent': '✅ Your message has been sent to the VSS response team. A responder can contact you via Telegram and, where possible, come to your location. Delivery does not mean someone has read it yet; response depends on the team on duty.',
    'failed': '⚠️ Delivery could not be confirmed. Your message may have arrived. Contact the team directly if needed; if you retry, mention that it may be a duplicate.',
    'busy': 'You have sent many messages. Please wait a minute before trying again. This last message was not sent to the team.',
    'command': 'Unknown command. Use /help, or send a message without a command to contact the team.',
}


@dataclass(frozen=True)
class Settings:
    token: str
    chat_id: int
    thread_id: int | None = None
    messages_per_minute: int = 20

    @classmethod
    def from_env(cls):
        token = os.environ.get("BOT_TOKEN", "").strip()
        if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{20,}", token):
            raise ValueError("BOT_TOKEN must contain a valid BotFather token.")
        try:
            chat_id = int(os.environ.get("TARGET_CHAT_ID", ""))
            raw_thread = os.environ.get("TARGET_THREAD_ID", "").strip()
            thread_id = int(raw_thread) if raw_thread else None
            limit = int(os.environ.get("MESSAGES_PER_MINUTE", "20"))
        except ValueError:
            raise ValueError("Chat ID, topic ID and message limit must be integers.") from None
        if chat_id >= 0 or (thread_id is not None and thread_id <= 0) or limit <= 0:
            raise ValueError("Use a negative group ID, a positive optional topic ID and a positive message limit.")
        return cls(token, chat_id, thread_id, limit)


@dataclass
class Delivery:
    created: float
    header_id: int | None = None
    copied: bool = False
    acknowledged: bool = False


class RelayState:
    """Bounded, short-lived metadata only; deliberately not a report store."""
    def __init__(self, max_entries=2000, ttl=3600, clock=time.monotonic):
        self.max_entries, self.ttl, self.clock = max_entries, ttl, clock
        self.deliveries = OrderedDict()
        self.users = OrderedDict()

    def get_delivery(self, key):
        now = self.clock()
        while self.deliveries:
            first = next(iter(self.deliveries))
            if now - self.deliveries[first].created < self.ttl:
                break
            self.deliveries.popitem(last=False)
        if key in self.deliveries:
            return self.deliveries[key], False
        while len(self.deliveries) >= self.max_entries:
            self.deliveries.popitem(last=False)
        delivery = Delivery(now)
        self.deliveries[key] = delivery
        return delivery, True

    def allow(self, user_id, limit):
        now = self.clock()
        # Each entry is bounded to limit timestamps; inactive users expire.
        while self.users and now - next(iter(self.users.values()))[-1] >= 60:
            self.users.popitem(last=False)
        timestamps = self.users.pop(user_id, deque())
        while timestamps and now - timestamps[0] >= 60:
            timestamps.popleft()
        allowed = len(timestamps) < limit
        if allowed:
            timestamps.append(now)
        self.users[user_id] = timestamps
        # Sort by last accepted message, including after rejected attempts.
        self.users = OrderedDict(sorted(self.users.items(), key=lambda item: item[1][-1]))
        while len(self.users) > self.max_entries:
            self.users.popitem(last=False)
        return allowed


def private_message(update):
    return (update.message is not None and update.effective_user is not None
            and update.effective_chat is not None and update.effective_chat.type == "private")


async def telegram_call(operation, **kwargs):
    """Retry explicit throttling only. Timeouts may already have delivered."""
    for attempt in range(3):
        try:
            return await operation(**kwargs)
        except RetryAfter as exc:
            wait = exc.retry_after
            seconds = wait.total_seconds() if isinstance(wait, timedelta) else wait
            if attempt == 2 or seconds > 5:
                raise
            await asyncio.sleep(seconds + 0.1)


async def respond(message, text):
    try:
        await telegram_call(message.reply_text, text=text)
        return True
    except TelegramError as exc:
        LOG.warning("User notification failed (%s)", type(exc).__name__)
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if private_message(update):
        await respond(update.message, TEXT["start"])


async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if private_message(update):
        await respond(update.message, TEXT["privacy"])


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if private_message(update):
        await respond(update.message, TEXT["command"])


async def forward_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not private_message(update):
        return
    message, user = update.message, update.effective_user
    settings = context.bot_data["settings"]
    state = context.bot_data["state"]
    key = (message.chat_id, message.message_id)
    delivery, fresh = state.get_delivery(key)
    if delivery.acknowledged:
        return
    if fresh and not state.allow(user.id, settings.messages_per_minute):
        state.deliveries.pop(key, None)
        await respond(message, TEXT["busy"])
        return
    target = {"chat_id": settings.chat_id, "protect_content": True}
    if settings.thread_id is not None:
        target["message_thread_id"] = settings.thread_id
    try:
        if delivery.header_id is None:
            # Keep identity separate: long texts and original captions stay intact.
            name = html.escape((user.full_name or "Unknown")[:200])
            label = html.escape(f"@{user.username}" if user.username else "profile")
            header = (f"📩 VSS · Ref. {message.chat_id}:{message.message_id}\n"
                      f'{name} — <a href="tg://user?id={user.id}">{label}</a>\n'
                      "Identity shared with the response team")
            sent = await telegram_call(context.bot.send_message, **target,
                                       text=header, parse_mode="HTML", disable_web_page_preview=True)
            delivery.header_id = sent.message_id
        if not delivery.copied:
            await telegram_call(context.bot.copy_message, **target,
                                from_chat_id=message.chat_id, message_id=message.message_id,
                                reply_to_message_id=delivery.header_id)
            delivery.copied = True
    except (BadRequest, Forbidden, NetworkError, TelegramError) as exc:
        # Never log exception text/tracebacks: URLs may contain bot credentials.
        LOG.warning("Team delivery not confirmed (%s)", type(exc).__name__)
        await respond(message, TEXT["failed"])
        return
    delivery.acknowledged = await respond(message, TEXT["sent"])


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    LOG.error("Unhandled update failure (%s)", type(context.error).__name__)
    if isinstance(update, Update) and private_message(update):
        await respond(update.message, TEXT["failed"])


async def post_init(app):
    settings = app.bot_data["settings"]
    chat = await app.bot.get_chat(settings.chat_id)
    if chat.type not in ("group", "supergroup"):
        raise ValueError("TARGET_CHAT_ID must identify a group or supergroup.")
    await app.bot.set_my_commands([
        BotCommand("start", "Contact the event response team"),
        BotCommand("help", "How it works"),
        BotCommand("privacy", "Privacy and data sharing"),
    ])
    LOG.info("VSS relay initialized")


def build_application(settings):
    # Sequential handling makes the in-memory duplicate tracking deterministic.
    app = (Application.builder().token(settings.token).concurrent_updates(False)
           .post_init(post_init).build())
    app.bot_data.update(settings=settings, state=RelayState())
    app.add_handler(CommandHandler(["start", "help"], start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("privacy", privacy, filters=filters.ChatType.PRIVATE))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.COMMAND, unknown_command))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND & filters.UpdateType.MESSAGE,
                                   forward_to_group))
    app.add_error_handler(on_error)
    return app


def main():
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # HTTP request URLs embed the token; suppress third-party request logs.
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    logging.getLogger("httpcore").setLevel(logging.CRITICAL)
    logging.getLogger("telegram").setLevel(logging.CRITICAL)
    try:
        app = build_application(Settings.from_env())
        app.run_polling(allowed_updates=["message"], drop_pending_updates=False, bootstrap_retries=0)
    except ValueError as exc:
        LOG.error("Configuration: %s", exc)
        raise SystemExit(1) from None
    except Exception as exc:
        LOG.error("Bot stopped (%s); check credentials, connectivity and group permissions.", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
