import asyncio

from aiogram import Bot, Dispatcher

from bot_instance import bot
from bot.handlers.user_handlers import user_router

from bot.config import BotConfig


def register_routers(dp: Dispatcher) -> None:
    """Register routers for the bot."""

    dp.include_router(user_router)


async def main(bot: Bot) -> None:
    """Entry point for the bot."""

    config = BotConfig(
        admin_ids=[123456789, 1305675],  
        welcome_message="Welcome to the bot!"
    )

    dp = Dispatcher()
    dp['config'] = config

    register_routers(dp)
    await dp.start_polling(bot)

    

if __name__ == "__main__":
    asyncio.run(main(bot))

