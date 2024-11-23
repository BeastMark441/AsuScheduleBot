from collections.abc import Coroutine
from functools import wraps
from typing import Any, Callable
import typing

from telegram import Message, Update

from telegrambot.context import ApplicationContext

def message_update_handler(f: Callable[[Message, ApplicationContext], Coroutine[Any, Any, Any]]):
    @wraps(f)
    async def wrapper(update: Update, context: ApplicationContext):
        return await f(typing.cast(Message, update.message), context)

    return wrapper
    