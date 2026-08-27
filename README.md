# Cenacolo Vinciano Ticket Watcher

Checks the official Last Supper (Cenacolo Vinciano, Milan) ticket calendar
every 15 minutes for availability on 2026-10-30 and 2026-11-06, and sends 10
Telegram messages the first time either date opens up. The public calendar
does not expose an exact remaining-seat count, so an alert means you should
open the booking page immediately and try to select two adult tickets.
It also sends a daily health report at 09:00 Korea Standard Time with both
target statuses, or an error alert if the booking calendar cannot be read.

## One-time setup

1. This repository is already forked and ready to use.

2. **Create a Telegram bot**: message [@BotFather](https://t.me/BotFather)
   on Telegram, send `/newbot`, follow the prompts. It gives you a bot
   token — save it.

3. **Get your chat ID**: send any message to your new bot, then open
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and
   read the `chat.id` field from the JSON response. (Or message
   [@userinfobot](https://t.me/userinfobot) to get your own numeric user ID,
   which works as the chat ID for a DM.)

4. **Add repo secrets**: in your GitHub repo, go to Settings → Secrets and
   variables → Actions → New repository secret, and add:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

5. **Allow the workflow to push commits**: Settings → Actions → General →
   Workflow permissions → select "Read and write permissions". (The
   `permissions: contents: write` block in the workflow file requests this,
   but some repos/orgs also need the setting enabled here.)

6. **Verify Telegram wiring** (optional but recommended), locally:
   ```bash
   export TELEGRAM_BOT_TOKEN=...
   export TELEGRAM_CHAT_ID=...
   python send_test_message.py
   ```
   You should get a Telegram message immediately.

7. **Trigger the workflow manually once**: GitHub repo → Actions tab →
   "Check Cenacolo Vinciano tickets" → Run workflow. Confirm it finishes
   green. It won't send a Telegram message on this run unless a date is
   genuinely available yet — that's expected.

From here it runs itself every 15 minutes. You'll get a Telegram DM the
first time either date shows real availability, and never again for that
date afterward.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium
pytest -v
```
