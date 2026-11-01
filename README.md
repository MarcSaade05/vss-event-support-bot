# VSS — Telegram Support Bot

**A discreet way for students to alert trained responders when they feel unsafe at an École Polytechnique social event.**

Designed for École Polytechnique’s international student community, this English-language Telegram bot helps anyone who feels unsafe, uncomfortable or affected by harassment or sexual or gender-based violence reach the event’s designated VSS response team without having to approach someone in person.

Users can privately describe what is happening and share their location, allowing trained responders on duty to contact them and, where possible, come to them in person. Whether at a party, a student gathering or another social event, the goal is to make asking for help easier and more discreet.

VSS stands for *violences sexistes et sexuelles*, the French term for sexual and gender-based violence. The bot connects users with the volunteer response team; human responders provide assistance and can help people access professional support when appropriate. Event organizers are responsible for ensuring that trained responders are on duty and that attendees know how to reach them.

**Privacy:** the conversation is private, but the current implementation is **not anonymous to the support team**. The sender's Telegram name, user ID and profile link accompany the message so that responders can contact them. The bot does not publicly publish reports.

**Developed by Marc Saade** using Python and `python-telegram-bot`.

## How it works

1. The user opens the bot and sends `/start` or `/help` to read how the service works.
2. They share their exact location (event, room or nearby landmark) and describe what help they need, using text, photos, documents or voice messages.
3. The bot sends an identity header to the configured team group, then copies the original message as a reply to that header.
4. After Telegram confirms the copy, the user receives a delivery confirmation.
5. A trained responder on duty can contact the sender through Telegram, clarify their location and, where possible, come to help in person.

All bot messages and command descriptions are in English, regardless of the user’s Telegram profile language. Messages sent without `/start` are also relayed, so the bot's public description should explain that messages and identity are shared with the team.

## Features

- Asynchronous private-message handling.
- Original text and media captions preserved through Telegram message copying.
- Separate sender header with a profile link and report reference.
- Support for long texts without adding an identity header to the message body.
- Photos, videos, documents and voice messages when supported by Telegram's copy API.
- HTML escaping for names and usernames.
- Telegram content protection on relayed messages, restricting forwarding and saving; this does not prevent all manual copying or capture.
- Configurable group, supergroup and optional forum-topic destination.
- Configurable per-user message limit over a rolling 60-second window.
- Bounded, temporary delivery tracking to avoid repeating confirmed delivery steps for the same update.
- Bounded retries for explicit Telegram throttling responses.
- Failure notifications when delivery cannot be confirmed.
- Startup configuration and destination-group validation.
- Local `.env` support, with hosting environment variables taking precedence.
- Offline tests and GitHub Actions checks for Python 3.12 and 3.13.

## Privacy and human support

The application does not create a report database, download attachments, or write report content to its application logs. Telegram and members of the destination group may retain messages.

Delivery tracking and rate limits keep bounded identifiers and timestamps in memory. Delivery entries expire after one hour; inactive rate-limit entries expire on subsequent processing after one minute. Restarting the process clears this state. Do not enable detailed HTTP logging: Telegram request URLs can contain the bot token.

Access to the receiving group should be restricted to the relevant support team. The organization should establish appropriate response, access and retention procedures.

A delivery confirmation means Telegram accepted the message into the team group; it does not mean a responder has read it. Staffing and response times depend on the team operating the service. The bot is not an emergency service and does not replace professional support.

## Local setup — Linux / WSL

Requires Python 3.12 or 3.13.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit the local `.env` file with the token issued by BotFather and the destination group ID, then run:

```bash
python bot.py
```

Never commit `.env`; it is excluded by `.gitignore`.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Fill in .env before starting.
py bot.py
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `BOT_TOKEN` | Bot token issued by BotFather | Required |
| `TARGET_CHAT_ID` | Negative numeric ID of the destination group | Required |
| `TARGET_THREAD_ID` | Positive forum-topic ID, if applicable | Empty |
| `MESSAGES_PER_MINUTE` | Maximum new messages accepted per user over 60 seconds | `20` |

Add the bot to the destination group with permission to send the expected message types. If a forum topic is configured, it must exist in that group. Startup checks the destination group type; message permissions and forum-topic settings should also be checked during a live test.

## Deployment

The included `Procfile` defines a worker:

```text
worker: python bot.py
```

Install the dependencies and configure environment variables on the hosting platform. Run **one polling worker per bot token**. Continuous availability depends on hosting and Telegram connectivity. Pending updates are not deliberately discarded on restart (`drop_pending_updates=False`).

Coordinate changes with the support team before restarting an existing deployment. Use a separate test bot and group to verify behavior before handling real reports.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests simulate Telegram and cover long messages, caption preservation, HTML escaping, ignored group messages, duplicate handling, delivery confirmations, timeouts, throttling retries, per-user limits, English-only responses, configuration and cache expiry. Integration tests also exercise real Telegram-library request serialization and application dispatch against an in-memory API simulator. No real token or report is required.

For a live check, verify `/start`, `/privacy`, text, a captioned photo, a voice message, a document, sender profile links and any configured forum topic.

## Delivery behavior

Timeouts are not automatically retried because Telegram may already have received the message. In that situation, the user is told that delivery could not be confirmed. Temporary tracking avoids some duplicates but does not guarantee exactly-once delivery, particularly across restarts or ambiguous timeouts.

Album items are copied individually. Later edits are not relayed. Some Telegram message types cannot be copied; failures are reported to the user. Team members follow up directly through Telegram; this application does not implement a two-way relay or case-management system.

## Credentials and publication

Use placeholders in all configuration examples. **An old Telegram bot token was committed in the README's history and must be revoked through BotFather before publication.** Replace `BOT_TOKEN` in the hosting configuration and restart the worker. Removing a token from the current file does not remove it from history or invalidate it.

The destination group ID is not an authentication token, but real group IDs should still be kept out of public examples. GitHub access tokens used to push code are separate credentials and must never be committed.

## Repository structure

| File | Purpose |
| --- | --- |
| `bot.py` | Configuration, commands, relay and error handling |
| `tests/test_bot.py` | Unit tests and asynchronous handler tests |
| `tests/test_integration.py` | Application dispatch and Telegram API serialization tests |
| `.env.example` | Configuration template without real credentials |
| `requirements.txt` | Pinned Python dependencies |
| `Procfile` | Worker startup command |
| `.github/workflows/tests.yml` | Automated GitHub Actions tests |
