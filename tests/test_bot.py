import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from telegram import Chat, Message, Update, User
from telegram.error import BadRequest, Forbidden, RetryAfter, TimedOut
from datetime import datetime, timezone

import bot


def fixture(text="hello", chat_type="private", language="en"):
    user = NS(id=42, full_name='<Marc & team>', username="marc", language_code=language)
    message = NS(chat_id=42, message_id=7, text=text, reply_text=AsyncMock())
    update = NS(message=message, effective_user=user, effective_chat=NS(type=chat_type))
    telegram = NS(send_message=AsyncMock(return_value=NS(message_id=99)), copy_message=AsyncMock())
    context = NS(bot=telegram, bot_data={"settings": bot.Settings("unused", -100), "state": bot.RelayState()})
    return update, context


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_copy_preserves_original_text_and_caption(self):
        for text in ("x" * 4096, None):
            update, ctx = fixture(text)
            await bot.forward_to_group(update, ctx)
            args = ctx.bot.copy_message.call_args.kwargs
            self.assertNotIn("caption", args)
            self.assertNotIn("text", args)
            self.assertEqual(args["reply_to_message_id"], 99)
            self.assertTrue(args["protect_content"])
            self.assertEqual(update.message.reply_text.call_args.kwargs["text"], bot.TEXT["sent"])

    async def test_html_identity_escaped(self):
        update, ctx = fixture()
        await bot.forward_to_group(update, ctx)
        header = ctx.bot.send_message.call_args.kwargs["text"]
        self.assertIn("&lt;Marc &amp; team&gt;", header)
        self.assertNotIn("<Marc", header)

    async def test_groups_are_ignored(self):
        update, ctx = fixture(chat_type="group")
        await bot.forward_to_group(update, ctx)
        ctx.bot.send_message.assert_not_awaited()

    async def test_missing_message_ignored(self):
        update, ctx = fixture()
        update.message = None
        await bot.forward_to_group(update, ctx)
        ctx.bot.send_message.assert_not_awaited()

    async def test_duplicate_update_not_delivered_twice(self):
        update, ctx = fixture()
        await bot.forward_to_group(update, ctx)
        await bot.forward_to_group(update, ctx)
        ctx.bot.send_message.assert_awaited_once()
        ctx.bot.copy_message.assert_awaited_once()
        update.message.reply_text.assert_awaited_once()

    async def test_ack_failure_does_not_repeat_team_delivery(self):
        update, ctx = fixture()
        update.message.reply_text.side_effect = [TimedOut(), None]
        await bot.forward_to_group(update, ctx)
        await bot.forward_to_group(update, ctx)
        ctx.bot.copy_message.assert_awaited_once()
        self.assertEqual(update.message.reply_text.await_count, 2)

    async def test_copy_failure_reuses_header_on_retry(self):
        update, ctx = fixture()
        ctx.bot.copy_message.side_effect = [BadRequest("unsupported"), None]
        await bot.forward_to_group(update, ctx)
        self.assertIn("could not be confirmed", update.message.reply_text.call_args.kwargs["text"])
        await bot.forward_to_group(update, ctx)
        ctx.bot.send_message.assert_awaited_once()
        self.assertEqual(ctx.bot.copy_message.await_count, 2)

    async def test_timeout_not_automatically_retried_or_reported_successful(self):
        update, ctx = fixture()
        ctx.bot.copy_message.side_effect = TimedOut()
        await bot.forward_to_group(update, ctx)
        ctx.bot.copy_message.assert_awaited_once()
        self.assertEqual(update.message.reply_text.call_args.kwargs["text"], bot.TEXT["failed"])

    async def test_rate_limit_blocks_new_message(self):
        update, ctx = fixture()
        ctx.bot_data["settings"] = bot.Settings("unused", -100, messages_per_minute=1)
        await bot.forward_to_group(update, ctx)
        update.message.message_id += 1
        await bot.forward_to_group(update, ctx)
        ctx.bot.copy_message.assert_awaited_once()
        self.assertEqual(update.message.reply_text.call_args.kwargs["text"], bot.TEXT["busy"])

    async def test_topic_and_sender_without_username(self):
        update, ctx = fixture()
        update.effective_user.username = None
        ctx.bot_data["settings"] = bot.Settings("unused", -100, thread_id=123)
        await bot.forward_to_group(update, ctx)
        self.assertEqual(ctx.bot.copy_message.call_args.kwargs["message_thread_id"], 123)
        self.assertIn("tg://user?id=42", ctx.bot.send_message.call_args.kwargs["text"])

    async def test_english_for_every_profile_language(self):
        for language in ("fr-FR", "en", "ar", None):
            update, ctx = fixture(language=language)
            await bot.start(update, ctx)
            self.assertIn("exact location", update.message.reply_text.call_args.kwargs["text"])
            await bot.privacy(update, ctx)
            self.assertIn("not anonymous", update.message.reply_text.call_args.kwargs["text"])
            await bot.forward_to_group(update, ctx)
            self.assertIn("Identity shared", ctx.bot.send_message.call_args.kwargs["text"])
            self.assertEqual(update.message.reply_text.call_args.kwargs["text"], bot.TEXT["sent"])

    async def test_unknown_command_does_not_relay(self):
        update, ctx = fixture()
        await bot.unknown_command(update, ctx)
        self.assertIn("Unknown command", update.message.reply_text.call_args.kwargs["text"])
        ctx.bot.copy_message.assert_not_awaited()

    async def test_explicit_throttling_retried(self):
        operation = AsyncMock(side_effect=[RetryAfter(1), "ok"])
        with patch("bot.asyncio.sleep", new_callable=AsyncMock) as sleep:
            self.assertEqual(await bot.telegram_call(operation), "ok")
        sleep.assert_awaited_once()

    async def test_long_throttle_not_blocking_loop(self):
        operation = AsyncMock(side_effect=RetryAfter(60))
        with self.assertRaises(RetryAfter):
            await bot.telegram_call(operation)
        operation.assert_awaited_once()

    async def test_errors_do_not_log_exception_secrets(self):
        update, ctx = fixture()
        ctx.bot.copy_message.side_effect = Forbidden("PRIVATE_TOKEN_AND_REPORT")
        with self.assertLogs("vss_bot", level="WARNING") as logs:
            await bot.forward_to_group(update, ctx)
        self.assertNotIn("PRIVATE_TOKEN_AND_REPORT", "".join(logs.output))

    async def test_post_init_rejects_non_group(self):
        app = NS(bot_data={"settings": bot.Settings("unused", -100)},
                 bot=NS(get_chat=AsyncMock(return_value=NS(type="channel"))))
        with self.assertRaises(ValueError):
            await bot.post_init(app)


class ConfigurationTests(unittest.TestCase):
    def test_env_validation(self):
        env = {"BOT_TOKEN": "123456789:" + "a" * 35, "TARGET_CHAT_ID": "-100"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(bot.Settings.from_env().chat_id, -100)
        for changed in ({"BOT_TOKEN": ""}, {"TARGET_CHAT_ID": "42"},
                        {"TARGET_CHAT_ID": "abc"}, {"TARGET_THREAD_ID": "0"},
                        {"MESSAGES_PER_MINUTE": "0"}):
            with patch.dict(os.environ, env | changed, clear=True), self.assertRaises(ValueError):
                bot.Settings.from_env()

    def test_state_expiry_and_bounds(self):
        now = [0]
        state = bot.RelayState(max_entries=2, ttl=60, clock=lambda: now[0])
        for i in range(3):
            state.get_delivery(i)
            state.allow(i, 2)
        self.assertEqual(len(state.deliveries), 2)
        self.assertEqual(len(state.users), 2)
        now[0] = 61
        state.get_delivery(4)
        state.allow(4, 2)
        self.assertEqual(len(state.deliveries), 1)
        self.assertEqual(len(state.users), 1)

    def test_rate_limit_resets_after_window(self):
        now = [0]
        state = bot.RelayState(clock=lambda: now[0])
        self.assertTrue(state.allow(42, 1))
        self.assertFalse(state.allow(42, 1))
        now[0] = 60
        self.assertTrue(state.allow(42, 1))

    def test_application_builds_and_real_update_matches_relay(self):
        # Building a client is offline; do not inherit a host's proxy setup.
        env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
        with patch.dict(os.environ, env, clear=True):
            app = bot.build_application(bot.Settings("123456789:" + "a" * 35, -100))
        msg = Message(message_id=1, date=datetime.now(timezone.utc),
                      chat=Chat(42, "private"), from_user=User(42, "Marc", False), text="hello")
        update = Update(1, message=msg)
        self.assertTrue(app.handlers[0][-1].check_update(update))
        self.assertEqual(len(app.error_handlers), 1)


if __name__ == "__main__":
    unittest.main()
