"""
Agent memory management — PostgreSQL (structured) + Qdrant (embeddings).
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models import AgentMemory
from config import settings
from llm import EMBEDDING

MEMORY_COLLECTION = "punji_memories"


async def get_embedding(text: str) -> list[float]:
    """Get a semantic embedding via the registry's EMBEDDING provider."""
    try:
        return await EMBEDDING.embed(text)
    except Exception:
        return [0.0] * EMBEDDING.dimensions


async def search_memories(user_id: str, query: str, db: AsyncSession, limit: int = 5) -> list[dict]:
    """Fetch top-N relevant memories via semantic search in Qdrant, fall back to DB."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        vector = await get_embedding(query)

        results = client.search(
            collection_name=MEMORY_COLLECTION,
            query_vector=vector,
            query_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]),
            limit=limit,
        )
        memory_ids = [r.id for r in results]

        db_result = await db.execute(
            select(AgentMemory).where(
                AgentMemory.id.in_([uuid.UUID(mid) if isinstance(mid, str) else mid for mid in memory_ids])
            )
        )
        memories = db_result.scalars().all()
        return [{"id": str(m.id), "type": m.memory_type, "content": m.content, "confidence": float(m.confidence)} for m in memories]
    except Exception:
        # Fall back to recent memories from DB
        result = await db.execute(
            select(AgentMemory)
            .where(AgentMemory.user_id == uuid.UUID(user_id))
            .order_by(AgentMemory.created_at.desc())
            .limit(limit)
        )
        memories = result.scalars().all()
        return [{"id": str(m.id), "type": m.memory_type, "content": m.content, "confidence": float(m.confidence)} for m in memories]


async def save_memory(user_id: str, memory_type: str, content: str, db: AsyncSession, confidence: float = 1.0):
    """Save a new memory to PostgreSQL and Qdrant."""
    memory = AgentMemory(
        user_id=uuid.UUID(user_id),
        memory_type=memory_type,
        content=content,
        confidence=confidence,
    )
    db.add(memory)
    await db.flush()

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import PointStruct

        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        vector = await get_embedding(content)

        # Ensure collection exists
        try:
            client.get_collection(MEMORY_COLLECTION)
        except Exception:
            from qdrant_client.http.models import VectorParams, Distance
            client.create_collection(
                MEMORY_COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING.dimensions, distance=Distance.COSINE),
            )

        point_id = str(memory.id)
        client.upsert(
            collection_name=MEMORY_COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload={"user_id": user_id, "type": memory_type})],
        )
        memory.qdrant_point_id = point_id
    except Exception:
        pass

    await db.commit()


async def delete_memory(memory_id: str, user_id: str, db: AsyncSession):
    """Delete from PostgreSQL and Qdrant."""
    result = await db.execute(
        select(AgentMemory).where(
            AgentMemory.id == uuid.UUID(memory_id),
            AgentMemory.user_id == uuid.UUID(user_id),
        )
    )
    mem = result.scalar_one_or_none()
    if not mem:
        return False

    if mem.qdrant_point_id:
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
            client.delete(collection_name=MEMORY_COLLECTION, points_selector=[mem.qdrant_point_id])
        except Exception:
            pass

    await db.delete(mem)
    await db.commit()
    return True
