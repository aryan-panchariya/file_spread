"""Handlers for basic public bot commands."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name=__name__)


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    """Welcome a user. Deep-link file delivery is added in Phase 3/4."""
    await message.answer(
        "Hello! This is a local-development file-sharing bot.\n\n"
        "File uploads and sharing links will be added in the next phases.\n"
        "Use /help to see the commands available now."
    )


@router.message(Command("help"))
async def command_help(message: Message) -> None:
    """Explain currently available commands without promising unfinished behavior."""
    await message.answer(
        "Available commands:\n"
        "/start — show the welcome message\n"
        "/help — show this help message\n\n"
        "Current phase: basic startup and commands."
    )
