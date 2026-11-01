"""Real PTB dispatch and API serialization, with network requests intercepted."""
import json
import os
import unittest
from unittest.mock import patch

from telegram import Update
from telegram.request import HTTPXRequest

import bot


class ApplicationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.reject_copy = False
        self.message_counter = 100

        async def fake_api(request, url, method, request_data=None, **kwargs):
            endpoint = url.rsplit("/", 1)[-1]
            parameters = request_data.parameters if request_data else {}
            # Exercise conversion to the actual wire payload too.
            if request_data:
                json.loads(request_data.json_payload)
            self.calls.append((endpoint, parameters))
            if endpoint == "getMe":
                result = {"id": 123456789, "is_bot": True, "first_name": "VSS", "username": "vss_test_bot"}
            elif endpoint == "getChat":
                result = {"id": -100, "type": "supergroup", "title": "Test team",
                          "accent_color_id": 0, "max_reaction_count": 1}
            elif endpoint == "setMyCommands":
                result = True
            elif endpoint == "copyMessage":
                if self.reject_copy:
                    return 403, json.dumps({"ok": False, "error_code": 403,
                                            "description": "Forbidden: insufficient permissions"}).encode()
                result = {"message_id": 500}
            elif endpoint == "sendMessage":
                self.message_counter += 1
                chat_id = parameters["chat_id"]
                result = {"message_id": self.message_counter, "date": 1700000000,
                          "chat": {"id": chat_id, "type": "private" if chat_id > 0 else "supergroup"},
                          "text": parameters["text"]}
            else:
                raise AssertionError(f"Unexpected API endpoint: {endpoint}")
            return 200, json.dumps({"ok": True, "result": result}).encode()

        self.transport = patch.object(HTTPXRequest, "do_request", fake_api)
        self.transport.start()
        env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
        with patch.dict(os.environ, env, clear=True):
            self.app = bot.build_application(bot.Settings("123456789:" + "a" * 35, -100, thread_id=8))
        await self.app.initialize()
        self.addAsyncCleanup(self.app.shutdown)
        self.addCleanup(self.transport.stop)
        await bot.post_init(self.app)

    def update(self, text=None, chat_type="private", **extra):
        message = {"message_id": 7, "date": 1700000000,
                   "chat": {"id": 42, "type": chat_type},
                   "from": {"id": 42, "is_bot": False, "first_name": "Student", "language_code": "fr"}}
        if text is not None:
            message["text"] = text
            if text.startswith("/"):
                message["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text)}]
        message.update(extra)
        return Update.de_json({"update_id": 1, "message": message}, self.app.bot)

    def payloads(self, endpoint):
        return [data for name, data in self.calls if name == endpoint]

    async def test_commands_dispatch_in_english_without_relay(self):
        for command, expected in (("/start", "exact location"), ("/help", "exact location"),
                                  ("/privacy", "not anonymous"), ("/unknown", "Unknown command")):
            await self.app.process_update(self.update(command))
            self.assertIn(expected, self.payloads("sendMessage")[-1]["text"])
        self.assertEqual(self.payloads("copyMessage"), [])
        commands = self.payloads("setMyCommands")[0]["commands"]
        self.assertEqual([item["description"] for item in commands],
                         ["Contact the event response team", "How it works", "Privacy and data sharing"])

    async def test_full_relay_wire_payload_and_duplicate(self):
        update = self.update("I feel unsafe near the entrance. " + "x" * 3900)
        await self.app.process_update(update)
        copies = self.payloads("copyMessage")
        self.assertEqual(len(copies), 1)
        copy = copies[0]
        self.assertEqual(copy["from_chat_id"], 42)
        self.assertEqual(copy["chat_id"], -100)
        self.assertEqual(copy["message_thread_id"], 8)
        self.assertTrue(copy["protect_content"])
        self.assertIn("reply_parameters", copy)
        self.assertNotIn("caption", copy)
        sends = self.payloads("sendMessage")
        self.assertEqual([entry["chat_id"] for entry in sends], [-100, 42])
        self.assertIn("response team", sends[0]["text"])
        self.assertEqual(sends[1]["text"], bot.TEXT["sent"])
        await self.app.process_update(update)
        self.assertEqual(len(self.payloads("copyMessage")), 1)

    async def test_photo_and_voice_reach_copy_api(self):
        for extra in ({"photo": [{"file_id": "photo", "file_unique_id": "unique", "width": 20, "height": 20}],
                       "caption": "Please find me near this door."},
                      {"voice": {"file_id": "voice", "file_unique_id": "voice_unique", "duration": 3}}):
            self.app.bot_data["state"] = bot.RelayState()
            await self.app.process_update(self.update(**extra))
            self.assertNotIn("caption", self.payloads("copyMessage")[-1])
            self.assertEqual(self.payloads("sendMessage")[-1]["text"], bot.TEXT["sent"])
        self.assertEqual(len(self.payloads("copyMessage")), 2)

    async def test_permission_failure_never_confirms_success(self):
        self.reject_copy = True
        await self.app.process_update(self.update("Please help."))
        self.assertEqual(self.payloads("sendMessage")[-1]["text"], bot.TEXT["failed"])
        self.assertFalse(self.app.bot_data["state"].deliveries[(42, 7)].copied)

    async def test_group_message_is_not_dispatched(self):
        await self.app.process_update(self.update("Do not relay", chat_type="group"))
        self.assertEqual(self.payloads("sendMessage"), [])
        self.assertEqual(self.payloads("copyMessage"), [])


if __name__ == "__main__":
    unittest.main()
