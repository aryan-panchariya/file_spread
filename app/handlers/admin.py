"""Admin-only upload handler for Phase 2."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.exc import SQLAlchemyError

from app.services.file_service import FileService, IncomingFile
from app.services.link_service import LinkService

logger = logging.getLogger(__name__)


def build_admin_router(file_service: FileService, link_service: LinkService, admin_ids: set[int]) -> Router:
    router = Router(name=__name__)

    @router.message(Command("link"))
    async def command_link(message: Message, command: CommandObject) -> None:
        """Let an admin recover the deep link for an earlier stored file record."""
        sender = message.from_user
        if sender is None or sender.id not in admin_ids:
            await message.answer("This command is available to bot administrators only.")
            logger.warning("Rejected /link from non-admin user id=%s", getattr(sender, "id", None))
            return
        if command.args is None or not command.args.strip().isdigit():
            await message.answer("Usage: <code>/link LOCAL_RECORD_ID</code>\nExample: <code>/link 1</code>")
            return
        try:
            stored_file = await file_service.get_by_id(int(command.args.strip()))
        except SQLAlchemyError:
            logger.exception("Database error while retrieving an admin share link")
            await message.answer("I could not retrieve that link due to a database error. Please try again.")
            return
        if stored_file is None:
            await message.answer("No stored file exists with that local record ID.")
            return
        await message.answer(f"Share link: {link_service.build_file_link(stored_file)}")

    @router.message(F.document | F.video | F.audio | F.animation)
    async def receive_admin_upload(message: Message) -> None:
        sender = message.from_user
        if sender is None or sender.id not in admin_ids:
            await message.answer("File uploads are available to bot administrators only.")
            logger.warning("Rejected file upload from non-admin user id=%s", getattr(sender, "id", None))
            return
        incoming_file = _extract_incoming_file(message)
        if incoming_file is None:
            logger.error("Upload filter matched but no supported file was found in message %s", message.message_id)
            await message.answer("I could not read that file. Please send it again as a document, video, audio, or animation.")
            return
        try:
            stored_file, was_created = await file_service.store_upload(incoming_file)
        except SQLAlchemyError:
            logger.exception("Database error while storing source message %s", message.message_id)
            await message.answer("I could not save that file reference due to a database error. Please try again.")
            return
        if was_created:
            await message.answer(
                "File reference stored successfully.\n"
                f"Share link: {link_service.build_file_link(stored_file)}\n\n"
                "The link is valid now. File delivery will be enabled in Phase 4."
            )
            logger.info("Stored admin upload record id=%s from chat=%s", stored_file.id, message.chat.id)
        else:
            await message.answer(
                "This exact Telegram message was already stored.\n"
                f"Share link: {link_service.build_file_link(stored_file)}"
            )

    return router


def _extract_incoming_file(message: Message) -> IncomingFile | None:
    attachment = message.document or message.video or message.audio or message.animation
    if attachment is None:
        return None
    if message.document is not None:
        file_type = "document"
    elif message.video is not None:
        file_type = "video"
    elif message.audio is not None:
        file_type = "audio"
    else:
        file_type = "animation"
    return IncomingFile(
        telegram_chat_id=message.chat.id,
        telegram_message_id=message.message_id,
        telegram_file_id=attachment.file_id,
        telegram_file_unique_id=attachment.file_unique_id,
        file_name=getattr(attachment, "file_name", None),
        file_type=file_type,
        mime_type=getattr(attachment, "mime_type", None),
        file_size=attachment.file_size,
    )
