# telegram-forwarder

Forward private DMs to a target group 24/7.

## Local test (Windows PowerShell)

From this folder:

```
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:BOT_TOKEN=8528522109:AAFV7pfVY2X9WI2DmdUxkWDPm5mdAkNHZbY
$env:TARGET_CHAT_ID="-5252943615"
py bot.py
```
