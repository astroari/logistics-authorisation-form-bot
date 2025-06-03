from aiogram import Bot, types
from aiogram.client.bot import DefaultBotProperties
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN_API = os.getenv('TOKEN_API')

bot = Bot(
    token=TOKEN_API,
    default=DefaultBotProperties(parse_mode='HTML')
    )