from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from bot.logger import setup_logger

logger = setup_logger(__name__)

class LoggerMiddleware(BaseMiddleware):
    """Middleware for logging all bot interactions."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Log the incoming update
        if isinstance(event, Message):
            user_id = event.from_user.id
            username = event.from_user.username
            chat_id = event.chat.id
            
            if event.text:
                logger.info(f"Message from user {user_id} (@{username}) in chat {chat_id}: {event.text}")
            elif event.document:
                logger.info(f"Document from user {user_id} (@{username}) in chat {chat_id}: {event.document.file_name}")
            elif event.photo:
                logger.info(f"Photo from user {user_id} (@{username}) in chat {chat_id}")
            else:
                logger.info(f"Other update from user {user_id} (@{username}) in chat {chat_id}: {event.content_type}")
                
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            username = event.from_user.username
            logger.info(f"Callback query from user {user_id} (@{username}): {event.data}")
        
        try:
            # Process the update
            result = await handler(event, data)
            return result
            
        except Exception as e:
            # Log any errors that occur during processing
            logger.error(f"Error processing update: {str(e)}", exc_info=True)
            raise 