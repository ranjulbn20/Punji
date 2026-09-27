"""
Shared retry policy for transient google-genai errors (used by
GeminiProvider and GeminiEmbeddingProvider, which hit the same backend family).
"""

import asyncio
from typing import Awaitable, Callable, TypeVar

from google.genai import errors as genai_errors

T = TypeVar("T")

# 503 = model temporarily overloaded, 429 = rate limited — both transient.
RETRYABLE_CODES = {429, 503}


async def with_retry(fn: Callable[[], Awaitable[T]], retries: int = 3, base_delay: float = 1.0) -> T:
    for attempt in range(retries + 1):
        try:
            return await fn()
        except genai_errors.APIError as e:
            if e.code not in RETRYABLE_CODES or attempt == retries:
                raise
            await asyncio.sleep(base_delay * (2 ** attempt))
