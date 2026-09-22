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
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database.connection import Database
from app.handlers.admin import build_admin_router
from app.handlers.start import build_start_router
from app.services.access_service import AccessService
from app.services.delivery_service import DeliveryService
from app.services.deletion_service import DeletionService
from app.services.file_service import FileService
from app.services.link_service import LinkService
from app.services.subscription_service import SubscriptionService
from app.services.user_service import UserService
from app.services.vplink_service import VplinkService


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
    admin_ids = settings.parsed_admin_ids
    if not admin_ids:
        raise ValueError("ADMIN_IDS must contain at least one numeric Telegram user ID in Phase 2.")

    database = Database(settings.database_url)
    await database.create_tables()

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger = logging.getLogger(__name__)
    deletion_task: asyncio.Task[None] | None = None
    try:
        bot_info = await bot.get_me()
        file_service = FileService(database)
        link_service = LinkService(bot_info.username or "")
        access_service = AccessService(database)
        delivery_service = DeliveryService(database, settings.auto_delete_minutes)
        user_service = UserService(database)
        vplink_service = VplinkService(
            settings.vplink_api_token.get_secret_value() if settings.vplink_api_token else "",
            enabled=settings.vplink_enabled,
        )
        subscription_service = SubscriptionService(
            bot,
            settings.force_subscription_enabled,
            settings.required_channel_id,
            settings.required_channel_username,
        )
        deletion_service = DeletionService(bot, delivery_service)
        deletion_task = asyncio.create_task(deletion_service.run(), name="delivery-deletion-worker")
        dispatcher = Dispatcher()
        dispatcher.include_router(
            build_start_router(
                bot,
                file_service,
                link_service,
                access_service,
                subscription_service,
                delivery_service,
                user_service,
                vplink_service,
            )
        )
        dispatcher.include_router(build_admin_router(file_service, link_service, admin_ids, user_service, access_service,))
        logger.info("Authenticated as @%s (id=%s). Starting polling.", bot_info.username, bot_info.id)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    except TelegramAPIError as error:
        logger.error("Telegram API startup error: %s", error)
        raise
    finally:
        if deletion_task is not None:
            deletion_task.cancel()
            try:
                await deletion_task
            except asyncio.CancelledError:
                pass
        await bot.session.close()
        await database.close()


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
    except SQLAlchemyError:
        logger.exception("Database startup error. Check DATABASE_URL and local file permissions.")
        raise SystemExit(1)
    except TokenValidationError:
        logger.error("BOT_TOKEN is malformed. Copy the complete token from BotFather into .env.")
        raise SystemExit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
