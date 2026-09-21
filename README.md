# Telegram File-Sharing Bot (Local Development)

This project is being built in small phases for local testing on Windows. It does not include Docker, cloud hosting, a VPS, or deployment configuration.

## Current status: Phase 1

The bot can start locally and responds to `/start` and `/help`. Admin uploads, file links, deliveries, deletion, subscription checks, sessions, and the database are deliberately not implemented yet.

The selected framework is **aiogram 3.x**. It provides an asynchronous Telegram Bot API interface and clean routing for the handlers this bot will need. Its structure is a little more formal than a minimal bot library, but it makes the growing feature set easier to maintain.

## Local setup on Windows

1. Install [Python 3.12 or newer](https://www.python.org/downloads/). In PowerShell, confirm it:

   ```powershell
   python --version
   ```

2. Create and activate a virtual environment in the project folder:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this once for the current window and retry:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

3. Install the Phase 1 dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Create a bot through Telegram's **@BotFather**. Copy its token and keep it private.

5. Copy `.env.example` to a new `.env` file:

   ```powershell
   Copy-Item .env.example .env
   ```

6. Open `.env` and set these values:

   ```dotenv
   BOT_TOKEN=your_real_token_from_botfather
   ADMIN_IDS=your_numeric_telegram_user_id
   ```

   `ADMIN_IDS` is reserved for Phase 2 but is useful to set now. You can obtain your numeric Telegram ID from a reputable ID bot, or we can cover it in the admin-upload phase.

7. Start the bot:

   ```powershell
   python -m app
   ```

8. Stop it with `Ctrl+C`.

## Phase 1 manual tests

### Test 1 — startup

Run:

```powershell
python -m app
```

Expected: the terminal logs that it authenticated as your bot and started polling. The token is never printed.

### Test 2 — `/start`

In Telegram, open a chat with your bot and send:

```text
/start
```

Expected: a welcome message saying this is the local-development bot.

### Test 3 — `/help`

Send:

```text
/help
```

Expected: a short list containing `/start` and `/help`.

### Test 4 — invalid or missing token

Temporarily stop the bot, clear or change `BOT_TOKEN` in `.env`, then run it again.

Expected: it exits with a clear configuration or Telegram API error. Restore the real token afterward.

## Configuration reference

`BOT_TOKEN` is required now. The remaining settings are present to make later phases predictable:

| Setting | Default | Used in |
| --- | --- | --- |
| `ADMIN_IDS` | empty | Phase 2 |
| `DATABASE_URL` | local SQLite URL | Phase 6 foundation |
| `AUTO_DELETE_MINUTES` | `20` | Phase 4 |
| `FORCE_SUBSCRIPTION_ENABLED` | `false` | Phase 5 |
| `REQUIRED_CHANNEL_ID` | empty | Phase 5 |
| `REQUIRED_CHANNEL_USERNAME` | empty | Phase 5 |
