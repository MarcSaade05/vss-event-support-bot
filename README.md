# VSS Telegram Support Bot

A Python Telegram bot that routes private messages to a designated VSS team group, helping team members receive reports and contact the sender.

## How it works

1. A user opens the bot and sends `/start`.
2. The bot asks for the user's location and a description of the situation.
3. The user sends a message directly to the bot.
4. The bot sends text messages to the configured group with the sender's name, Telegram user ID, and profile link. Non-text messages are copied to the group with a sender header.
5. After the group delivery succeeds, the bot sends a confirmation to the user.

Team members contact the sender separately. The bot does not implement two-way conversations or track whether a report has been handled.

## Implementation

- Python with `python-telegram-bot==21.6`.
- Asynchronous command and message handlers.
- Private-chat filtering to avoid relaying messages from groups.
- HTML escaping for user-provided names and text.
- Environment variables for the bot token and destination group.
- Long polling to receive Telegram updates.
- A `Procfile` defining a worker process for deployment.

## Privacy

Messages sent to the bot are shared with the configured team group, together with the sender's Telegram identity. This is not an anonymous reporting service. The application does not implement a database; Telegram retains messages according to its own behavior.

## Configuration

Create a bot through Telegram's BotFather and add it to the destination group with permission to send messages.

Set these environment variables:

| Variable | Purpose |
| --- | --- |
| `BOT_TOKEN` | Bot token issued by BotFather |
| `TARGET_CHAT_ID` | Numeric ID of the destination Telegram group |

Never commit real tokens or personal reports. If a token was previously committed, revoke it through BotFather and update the deployment configuration with a replacement.

## Run locally

### Linux / WSL

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export BOT_TOKEN="YOUR_BOT_TOKEN"
export TARGET_CHAT_ID="YOUR_GROUP_CHAT_ID"
python bot.py
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:BOT_TOKEN="YOUR_BOT_TOKEN"
$env:TARGET_CHAT_ID="YOUR_GROUP_CHAT_ID"
py bot.py
```

The bot reads the process environment directly; it does not automatically load a `.env` file.

## Deployment

The included `Procfile` starts the bot as a worker:

```text
worker: python bot.py
```

Configure the environment variables on the hosting platform and keep the worker running to receive messages. The repository includes a worker definition; continuous availability depends on the hosting setup.

## Limitations

- A delivery confirmation means the message reached the group, not that a team member has read or acted on it.
- No custom retry, rate-limiting, case-tracking, or two-way reply system is implemented.
- Copying non-text messages replaces their caption with the sender header.
