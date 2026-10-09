"""aiogram wiring. All decisions live in OpsBot.handle; this module only moves text in and out."""

from __future__ import annotations

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message

from .core import OpsBot


def build_router(core: OpsBot) -> Router:
    router = Router(name="opsbot")

    @router.message(F.text)
    async def on_text(message: Message) -> None:
        if message.from_user is None or message.text is None:
            return
        private = message.chat.type == "private"
        if not private and message.chat.id not in core.cfg.allowed_chats:
            return  # groups are ignored unless explicitly allowed
        reply = core.handle(message.from_user.id, message.text, private=private)
        if reply:
            # Plain text on purpose: user-supplied strings (alert reasons) must never be parsed as markup.
            await message.answer(reply, parse_mode=None)

    return router


def build_dispatcher(core: OpsBot) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(build_router(core))
    return dp


def build_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=None))


async def run_polling(token: str, core: OpsBot) -> None:
    bot = build_bot(token)
    try:
        await build_dispatcher(core).start_polling(bot, allowed_updates=["message"])
    finally:
        await bot.session.close()
