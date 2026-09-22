# Telegram File-Sharing Bot (Local Development)

This project is built and tested locally on Windows. It has no Docker, cloud hosting, VPS, or deployment setup.

## Current status: complete local development version

Configured administrators can upload documents, videos, audio files, and animations. The bot stores the Telegram source-message reference and metadata in local SQLite, not file bytes. Each stored file now receives a random public ID and a Telegram share link.

Opening a valid link now checks optional channel membership first, creates or reuses a 24-hour access session only after that check passes, copies the original Telegram message to the user, and schedules only the copied message for deletion. The original stored message is never deleted.

The bot uses **aiogram 3.x** for async Telegram handling and SQLAlchemy 2.x with local SQLite. The database layer is structured so PostgreSQL can be introduced later without changing the bot features. Users, access sessions, deliveries, and deletion status are persisted locally.

## Local setup on Windows

1. Install [Python 3.12 or newer](https://www.python.org/downloads/) and confirm it:

   ```powershell
   python --version
   ```

2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this once in the current PowerShell window, then retry:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

3. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Create a bot using Telegram's **@BotFather**, then copy its token.

5. Create your private local configuration:

   ```powershell
   Copy-Item .env.example .env
   ```

6. Edit `.env` with your real values:

   ```dotenv
   BOT_TOKEN=your_real_token_from_botfather
   ADMIN_IDS=your_numeric_telegram_user_id
   DATABASE_URL=sqlite+aiosqlite:///data/bot.db
   ```

   `ADMIN_IDS` contains numeric Telegram account IDs, not `@usernames`. Use commas for multiple admins.

7. Start the bot:

   ```powershell
   python -m app
   ```

Stop it with `Ctrl+C`.

## Phase 4 and 5 manual tests

### Test 1 - upload and link generation

From an account in `ADMIN_IDS`, upload a supported file to the bot.

Expected: the bot replies with a Telegram URL beginning with `https://t.me/` and containing `?start=file_...`.

### Test 2 - retrieve a link for your earlier upload

If the file you uploaded in Phase 2 showed `Local record ID: 1`, send this command from an administrator account:

```text
/link 1
```

Expected: the bot returns that file's share link. This works because the Phase 3 startup migration gives existing records a public ID without removing their source reference.

### Test 3 - open a valid share link

Tap the generated link, choose your bot if Telegram asks, then press Start.

Expected with `FORCE_SUBSCRIPTION_ENABLED=false`: the bot copies the requested file to your chat and sends a cleanup notice.

### Test 4 - short deletion test

Temporarily set `AUTO_DELETE_MINUTES=1` in `.env`, restart the bot, open a valid link, and wait about one minute.

Expected: the user-facing copied message is deleted. The original admin upload and database record remain available. Restore `AUTO_DELETE_MINUTES=20` afterward.

### Test 5 - force subscription

Use a channel where the bot can check membership, then set:

```dotenv
FORCE_SUBSCRIPTION_ENABLED=true
REQUIRED_CHANNEL_ID=-1001234567890
REQUIRED_CHANNEL_USERNAME=your_channel_username
```

Restart the bot and open a link from an account that has not joined.

Expected: the bot does not send the file or create a 24-hour access session. It shows Join and “I've Joined / Check Again” buttons.

Join the channel and press “I've Joined / Check Again”.

Expected: the check passes, a 24-hour session is created, and the file is copied. Another valid link within 24 hours reuses that session.

## Automated checks

Run from the project folder with the virtual environment active:

```powershell
pytest -q
```

These tests verify link validation, local SQLite storage, duplicate upload protection, 24-hour session reuse, and configurable delivery deletion timing.

### Test 6 - invalid link

Send the bot a malformed command such as:

```text
/start file_not-a-real-id
```

Expected: the bot says the share link is invalid. No file is sent.

### Test 7 - unknown but well-formed ID

Send this example:

```text
/start file_AbCdEfGhIjKlMnOp
```

Expected: the bot says the link is invalid or the file no longer exists.

## How share links work

A public ID is generated with cryptographically secure random URL-safe characters. The stored link is conceptually:

```text
https://t.me/YourBotUsername?start=file_PUBLIC_ID
```

Telegram turns that URL into `/start file_PUBLIC_ID`. The bot validates the format and looks up the ID in SQLite before accepting it. It never trusts an arbitrary user-supplied ID as a Telegram file reference.

## Stored metadata

`users` tracks Telegram ID, username, first/last seen, and status. `stored_files` holds the original Telegram chat/message IDs, Telegram file identifiers, file metadata, a public ID, and creation time. `access_sessions` tracks subscription-approved 24-hour sessions. `deliveries` tracks copied user-facing messages and their cleanup state. The original source message remains on Telegram; deleting a delivery cannot delete it.

## Configuration reference

| Setting | Default | Used in |
| --- | --- | --- |
| `BOT_TOKEN` | required | Phase 1 |
| `ADMIN_IDS` | required | Phase 2 |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/bot.db` | Local database |
| `AUTO_DELETE_MINUTES` | `20` | Phase 4 |
| `FORCE_SUBSCRIPTION_ENABLED` | `false` | Phase 5 |
| `REQUIRED_CHANNEL_ID` | empty | Phase 5 |
| `REQUIRED_CHANNEL_USERNAME` | empty | Phase 5 |
