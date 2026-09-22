"""Public commands, subscription gates, VPLINK unlock, and file delivery."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.exc import SQLAlchemyError

from app.services.access_service import AccessService
from app.services.delivery_service import DeliveryService
from app.services.file_service import FileService
from app.services.link_service import LinkService
from app.services.subscription_service import SubscriptionService
from app.services.user_service import UserService
from app.services.vplink_service import VplinkError, VplinkService

logger = logging.getLogger(__name__)

_CHECK_PREFIX = "check_sub:"
_UNLOCK_PREFIX = "unlock_"


def build_start_router(
    bot: Bot,
    file_service: FileService,
    link_service: LinkService,
    access_service: AccessService,
    subscription_service: SubscriptionService,
    delivery_service: DeliveryService,
    user_service: UserService,
    vplink_service: VplinkService,
) -> Router:
    """Create the public access and file-delivery router."""

    router = Router(name=__name__)

    def subscription_keyboard(public_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Join required channel",
                        url=subscription_service.join_url(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="I've Joined / Check Again",
                        callback_data=f"{_CHECK_PREFIX}{public_id}",
                    )
                ],
            ]
        )

    async def deliver_file(
        message: Message,
        public_id: str,
        user_telegram_id: int,
        *,
        unlocked: bool = False,
    ) -> None:
        """
        Access flow:

        1. Validate file.
        2. Check subscription.
        3. Check existing 24-hour session.
        4. If no session:
           - normal request -> VPLINK
           - unlocked request -> create session
        5. Deliver file.
        """

        try:
            stored_file = await file_service.get_by_public_id(public_id)
        except SQLAlchemyError:
            logger.exception("Database error while looking up public file ID")
            await message.answer(
                "I could not verify this link right now. Please try again later."
            )
            return

        if stored_file is None:
            await message.answer(
                "This share link is invalid or the file no longer exists."
            )
            return

        # ---------------------------------------------------------
        # 1. SUBSCRIPTION MUST ALWAYS COME FIRST
        # ---------------------------------------------------------

        try:
            subscribed = await subscription_service.is_subscribed(
                user_telegram_id
            )
        except TelegramAPIError:
            await message.answer(
                "I could not verify channel membership. Please try again later."
            )
            return

        if not subscribed:
            await message.answer(
                "Please join the required channel before requesting this file.",
                reply_markup=subscription_keyboard(public_id),
            )
            return

        # ---------------------------------------------------------
        # 2. CHECK EXISTING 24-HOUR SESSION
        # ---------------------------------------------------------

        try:
            access_session = await access_service.get_valid_session(
                user_telegram_id
            )
        except SQLAlchemyError:
            logger.exception("Database error while checking access session")
            await message.answer(
                "I could not check your access session. Please try again later."
            )
            return

        # ---------------------------------------------------------
        # 3. VALID SESSION EXISTS -> DIRECT FILE
        # ---------------------------------------------------------

        if access_session is not None:
            logger.info(
                "Using existing access session id=%s for user id=%s",
                access_session.id,
                user_telegram_id,
            )

        # ---------------------------------------------------------
        # 4. NO SESSION
        # ---------------------------------------------------------

        else:
            # User came through VPLINK unlock destination.
            if unlocked:
                try:
                    access_session = await access_service.create_session(
                        user_telegram_id
                    )
                except SQLAlchemyError:
                    logger.exception(
                        "Database error while creating unlocked access session"
                    )
                    await message.answer(
                        "I could not create your access session. "
                        "Please try again later."
                    )
                    return

                logger.info(
                    "Created new 24-hour access session id=%s for unlocked user id=%s",
                    access_session.id,
                    user_telegram_id,
                )

            # User has no session and has NOT completed VPLINK.
            else:
                try:
                    unlock_destination = (
                        link_service.build_file_link(stored_file)
                        .replace(
                            "?start=file_",
                            "?start=unlock_",
                            1,
                        )
                    )

                    short_url = await vplink_service.shorten(
                        unlock_destination
                    )

                except VplinkError:
                    logger.exception(
                        "VPLINK failed for user id=%s file id=%s",
                        user_telegram_id,
                        stored_file.id,
                    )

                    await message.answer(
                        "I could not create the unlock link right now. "
                        "Please try again later."
                    )
                    return

                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🔓 Unlock Access",
                                url=short_url,
                            )
                        ]
                    ]
                )

                await message.answer(
                    "You don't currently have a 24-hour access session.\n\n"
                    "Complete the unlock step first, then you'll receive "
                    "24-hour access.",
                    reply_markup=keyboard,
                )

                logger.info(
                    "Sent VPLINK unlock URL to user id=%s for file id=%s",
                    user_telegram_id,
                    stored_file.id,
                )

                return

        # ---------------------------------------------------------
        # 5. DELIVER FILE
        # ---------------------------------------------------------

        try:
            copied_message = await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=stored_file.telegram_chat_id,
                message_id=stored_file.telegram_message_id,
            )
        except TelegramAPIError:
            logger.exception(
                "Telegram failed to copy stored file id=%s",
                stored_file.id,
            )

            await message.answer(
                "Telegram could not deliver this file right now. "
                "Please try again later."
            )
            return

        # ---------------------------------------------------------
        # 6. SAVE DELETION SCHEDULE
        # ---------------------------------------------------------

        try:
            delivery = await delivery_service.record_delivery(
                user_telegram_id=user_telegram_id,
                stored_file_id=stored_file.id,
                sent_chat_id=message.chat.id,
                sent_message_id=copied_message.message_id,
            )
        except SQLAlchemyError:
            logger.exception(
                "File was copied but its deletion schedule could not be saved"
            )

            try:
                await bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=copied_message.message_id,
                )
            except TelegramAPIError:
                logger.exception(
                    "Could not clean up unscheduled copied message"
                )

            await message.answer(
                "The file was delivered, but its cleanup schedule "
                "could not be saved."
            )
            return

        await message.answer(
            "This file copy will be automatically deleted "
            "after the configured time."
        )

        logger.info(
            "Delivered stored file id=%s as delivery id=%s",
            stored_file.id,
            delivery.id,
        )

    # =============================================================
    # /start
    # =============================================================

    @router.message(CommandStart())
    async def command_start(
        message: Message,
        command: CommandObject,
    ) -> None:

        if message.from_user is not None:
            try:
                await user_service.record_seen(
                    message.from_user.id,
                    message.from_user.username,
                )
            except SQLAlchemyError:
                logger.exception(
                    "Could not update user activity"
                )

        if command.args is None:
            await message.answer(
                "Hello! This is a local-development file-sharing bot.\n\n"
                "Administrators can upload files and create share links.\n"
                "Use /help to see the commands available now."
            )
            return

        args = command.args.strip()

        # ---------------------------------------------------------
        # VPLINK UNLOCK DESTINATION
        # ---------------------------------------------------------

        if args.startswith(_UNLOCK_PREFIX):
            unlock_public_id = args.removeprefix(_UNLOCK_PREFIX)

            public_id = link_service.parse_file_id(
                f"file_{unlock_public_id}"
            )

            if public_id is None:
                await message.answer(
                    "This unlock link is invalid or expired."
                )
                return

            await deliver_file(
                message,
                public_id,
                message.from_user.id if message.from_user else 0,
                unlocked=True,
            )
            return

        # ---------------------------------------------------------
        # NORMAL FILE LINK
        # ---------------------------------------------------------

        public_id = link_service.parse_file_id(args)

        if public_id is None:
            await message.answer(
                "This share link is invalid. "
                "Please ask the sender for a new link."
            )
            return

        await deliver_file(
            message,
            public_id,
            message.from_user.id if message.from_user else 0,
        )

    # =============================================================
    # SUBSCRIPTION RECHECK
    # =============================================================

    @router.callback_query(F.data.startswith(_CHECK_PREFIX))
    async def check_subscription(
        callback: CallbackQuery,
    ) -> None:

        await callback.answer()

        if callback.message is None or callback.from_user is None:
            return

        try:
            await user_service.record_seen(
                callback.from_user.id,
                callback.from_user.username,
            )
        except SQLAlchemyError:
            logger.exception(
                "Could not update user activity"
            )

        public_id = link_service.parse_file_id(
            "file_" + callback.data.removeprefix(_CHECK_PREFIX)
        )

        if public_id is None:
            await callback.message.answer(
                "This share link is invalid. Please request a new link."
            )
            return

        await deliver_file(
            callback.message,
            public_id,
            callback.from_user.id,
        )

    # =============================================================
    # /help
    # =============================================================

    @router.message(Command("help"))
    async def command_help(message: Message) -> None:
        await message.answer(
            "Available commands:\n"
            "/start - show the welcome message\n"
            "/help - show this help message\n\n"
            "File links check subscription and 24-hour access. "
            "Users without an active access session must complete "
            "the unlock step before receiving the file."
        )

    return router