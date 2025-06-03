import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from bot_instance import bot
from bot.handlers.user_handlers import user_router
from bot.config import BotConfig
from bot.logger import setup_logger
from bot.middlewares.logger_middleware import LoggerMiddleware

# Set up logger
logger = setup_logger(__name__)

def register_routers(dp: Dispatcher) -> None:
    """Register routers for the bot."""
    dp.include_router(user_router)
    logger.info("Routers registered successfully")

async def setup_bot_commands():
    bot_commands = [
        BotCommand(command="/start", description="Стартовать бота"),
        BotCommand(command="/new_form", description="Создать новую доверенность"),
        BotCommand(command="/done", description="Закончить загрузку документов")
    ]
    await bot.set_my_commands(bot_commands)
    logger.info("Bot commands set up successfully")

async def main(bot: Bot) -> None:
    """Entry point for the bot."""
    logger.info("Starting bot...")

    config = BotConfig(
        admin_ids=[1305675],  
        welcome_message="""👋  Здравствуйте!

🤖 Этот бот создаёт доверенности для водителей. 

1. Нажмите команду /new_form чтобы создать новую доверенность. Доверенность создаётся на одного водителя. 
2. Загрузите необходимые документы: паспорт водителя и свидетельства о регистрации автотранспортного средства. Бот принимает файлы формата PNG, JPG и PDF. 
3. После того как вы загрузили все файлы, нажмите команду /done.
4. Выберите фирму выдающую доверенность.
5. Введите наименование завода для доверенности.
6. Бот создаст доверенность в XLSX формате. Проверьте данные и сохраните этот файл в формате PDF. 
"""
    )

    dp = Dispatcher()
    dp['config'] = config

    # Register middleware
    dp.update.middleware(LoggerMiddleware())
    logger.info("Logger middleware registered")

    register_routers(dp)
    
    # Set up bot commands
    await setup_bot_commands()
    
    logger.info("Bot is ready to start polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main(bot))
    except Exception as e:
        logger.error(f"Bot crashed with error: {str(e)}", exc_info=True)
        raise

