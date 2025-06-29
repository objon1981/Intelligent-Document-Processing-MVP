# --- utils.py ---
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor()

async def run_in_threadpool(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: func(*args))