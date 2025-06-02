from aiogram import Bot, types
from token_api import TOKEN_API
from aiogram.client.bot import DefaultBotProperties


bot = Bot(
    token=TOKEN_API,
    default=DefaultBotProperties(parse_mode='HTML')
    )