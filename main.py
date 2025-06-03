import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from bot_instance import bot
from bot.handlers.user_handlers import user_router

from bot.config import BotConfig


def register_routers(dp: Dispatcher) -> None:
    """Register routers for the bot."""

    dp.include_router(user_router)


async def setup_bot_commands():
    bot_commands = [
        BotCommand(command="/start", description="Стартовать бота"),
        BotCommand(command="/new_form", description="Создать новую доверенность"),
        BotCommand(command="/done", description="Закончить загрузку документов")
    ]
    await bot.set_my_commands(bot_commands)   


async def main(bot: Bot) -> None:
    """Entry point for the bot."""

    config = BotConfig(
        admin_ids=[1305675],  
        welcome_message="Здравст"
    )

    dp = Dispatcher()
    dp['config'] = config

    register_routers(dp)
    
    # Set up bot commands
    await setup_bot_commands()
    
    await dp.start_polling(bot)

    

if __name__ == "__main__":
    asyncio.run(main(bot))

