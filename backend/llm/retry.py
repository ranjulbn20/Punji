"""
Shared retry policy for transient google-genai errors (used by
GeminiProvider and GeminiEmbeddingProvider, which hit the same backend family).
"""

import asyncio
from typing import Awaitable, Callable, TypeVar

from google.genai import errors as genai_errors

T = TypeVar("T")

# 503 = model temporarily overloaded, 429 = rate limited — both transient
# *unless* the 429 is a per-day quota exhaustion (see below), which no
# amount of backoff within one process lifetime can fix.
RETRYABLE_CODES = {429, 503}


async def with_retry(fn: Callable[[], Awaitable[T]], retries: int = 3, base_delay: float = 1.0) -> T:
    for attempt in range(retries + 1):
        try:
            return await fn()
        except genai_errors.APIError as e:
            # Free-tier daily quota (quotaId ".../PerDay.../FreeTier") resets tomorrow,
            # not in the next few seconds — retrying just wastes ~7s before the caller's
            # FallbackLLMProvider would switch to Groq anyway. Per-minute rate limits
            # (".../PerMinute.../FreeTier") and 503 overloads are still worth the backoff.
            if e.code == 429 and "PerDay" in str(e):
                raise
            if e.code not in RETRYABLE_CODES or attempt == retries:
                raise
            await asyncio.sleep(base_delay * (2 ** attempt))
