"""Aiogram application creation and local polling startup."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.utils.token import TokenValidationError
from pydantic import ValidationError

from app.config import get_settings
from app.handlers.start import router as start_router


def configure_logging() -> None:
    """Configure concise logs for local development without exposing secrets."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("aiogram.event").setLevel(logging.INFO)


async def run_bot() -> None:
    """Create the bot and keep long polling active until stopped."""
    settings = get_settings()
    # Validate this early so malformed ADMIN_IDS produce a clear startup error.
    settings.parsed_admin_ids

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(start_router)

    logger = logging.getLogger(__name__)
    try:
        bot_info = await bot.get_me()
        logger.info("Authenticated as @%s (id=%s). Starting polling.", bot_info.username, bot_info.id)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    except TelegramAPIError as error:
        logger.error("Telegram API startup error: %s", error)
        raise
    finally:
        await bot.session.close()


def main() -> None:
    """Program entry point with beginner-friendly configuration failures."""
    configure_logging()
    logger = logging.getLogger(__name__)

    if sys.version_info < (3, 12):
        logger.error("Python 3.12 or newer is required; found %s.%s.", sys.version_info.major, sys.version_info.minor)
        raise SystemExit(1)

    try:
        asyncio.run(run_bot())
    except ValidationError as error:
        logger.error("Configuration error. Create .env from .env.example and fix its values: %s", error)
        raise SystemExit(1) from error
    except ValueError as error:
        logger.error("Configuration error: %s", error)
        raise SystemExit(1) from error
    except TelegramAPIError:
        logger.error("Bot stopped because Telegram rejected the API request. Check BOT_TOKEN and network access.")
        raise SystemExit(1)
    except TokenValidationError:
        logger.error("BOT_TOKEN is malformed. Copy the complete token from BotFather into .env.")
        raise SystemExit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
