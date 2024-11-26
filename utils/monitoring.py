import time
from functools import wraps
from typing import TypeVar, Callable, Any, Awaitable
import logging

T = TypeVar('T')

def measure_time(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Декоратор для измерения времени выполнения асинхронных функций"""
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.time()
        result = await func(*args, **kwargs)
        execution_time = time.time() - start
        
        if execution_time > 1.0:
            logging.warning(
                f"Slow operation detected: {func.__name__} "
                f"took {execution_time:.2f} seconds"
            )
        
        return result
    return wrapper 