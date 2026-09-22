"""Public commands, subscription gates, and file delivery."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.exc import SQLAlchemyError

from app.services.access_service import AccessService
from app.services.delivery_service import DeliveryService
from app.services.file_service import FileService
from app.services.link_service import LinkService
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)
_CHECK_PREFIX = "check_sub:"


def build_start_router(
    bot: Bot,
    file_service: FileService,
    link_service: LinkService,
    access_service: AccessService,
    subscription_service: SubscriptionService,
    delivery_service: DeliveryService,
) -> Router:
    """Create the complete Phase 4/5 access flow."""
    router = Router(name=__name__)

    def subscription_keyboard(public_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Join required channel", url=subscription_service.join_url())],
                [InlineKeyboardButton(text="I've Joined / Check Again", callback_data=f"{_CHECK_PREFIX}{public_id}")],
            ]
        )

    async def deliver_file(message: Message, public_id: str, user_telegram_id: int) -> None:
        """Perform the required order: subscription, session, copy, delivery record."""
        try:
            stored_file = await file_service.get_by_public_id(public_id)
        except SQLAlchemyError:
            logger.exception("Database error while looking up public file ID")
            await message.answer("I could not verify this link right now. Please try again later.")
            return
        if stored_file is None:
            await message.answer("This share link is invalid or the file no longer exists.")
            return

        # Subscription verification intentionally happens before any session lookup/creation.
        try:
            subscribed = await subscription_service.is_subscribed(user_telegram_id)
        except TelegramAPIError:
            await message.answer(
                "I could not verify channel membership. Please try again later, or ask the bot administrator "
                "to check the bot's channel permissions."
            )
            return
        if not subscribed:
            await message.answer(
                "Please join the required channel before requesting this file.",
                reply_markup=subscription_keyboard(public_id),
            )
            return

        try:
            access_session = await access_service.get_or_create_valid_session(user_telegram_id)
        except SQLAlchemyError:
            logger.exception("Database error while creating an access session")
            await message.answer("I could not create an access session. Please try again later.")
            return
        logger.info("Using access session id=%s for user id=%s", access_session.id, user_telegram_id)

        try:
            copied_message = await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=stored_file.telegram_chat_id,
                message_id=stored_file.telegram_message_id,
            )
        except TelegramAPIError:
            logger.exception("Telegram failed to copy stored file id=%s", stored_file.id)
            await message.answer("Telegram could not deliver this file right now. Please try again later.")
            return

        try:
            delivery = await delivery_service.record_delivery(
                user_telegram_id=user_telegram_id,
                stored_file_id=stored_file.id,
                sent_chat_id=message.chat.id,
                sent_message_id=copied_message.message_id,
            )
        except SQLAlchemyError:
            logger.exception("File was copied but its deletion schedule could not be saved")
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=copied_message.message_id)
            except TelegramAPIError:
                logger.exception("Could not clean up the unscheduled copied message")
            await message.answer("The file was delivered, but its cleanup schedule could not be saved.")
            return
        await message.answer("This file copy will be automatically deleted after the configured time.")
        logger.info("Delivered stored file id=%s as delivery id=%s", stored_file.id, delivery.id)

    @router.message(CommandStart())
    async def command_start(message: Message, command: CommandObject) -> None:
        public_id = link_service.parse_file_id(command.args)
        if command.args is None:
            await message.answer(
                "Hello! This is a local-development file-sharing bot.\n\n"
                "Administrators can upload files and create share links.\n"
                "Use /help to see the commands available now."
            )
            return
        if public_id is None:
            await message.answer("This share link is invalid. Please ask the sender for a new link.")
            return
        await deliver_file(message, public_id, message.from_user.id if message.from_user else 0)

    @router.callback_query(F.data.startswith(_CHECK_PREFIX))
    async def check_subscription(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.message is None or callback.from_user is None:
            return
        public_id = link_service.parse_file_id("file_" + callback.data.removeprefix(_CHECK_PREFIX))
        if public_id is None:
            await callback.message.answer("This share link is invalid. Please request a new link.")
            return
        await deliver_file(callback.message, public_id, callback.from_user.id)

    @router.message(Command("help"))
    async def command_help(message: Message) -> None:
        await message.answer(
            "Available commands:\n"
            "/start - show the welcome message\n"
            "/help - show this help message\n\n"
            "Valid file links now check access, deliver the file, and schedule its user-facing copy for deletion."
        )

    return router
