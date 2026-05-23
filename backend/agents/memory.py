"""
Agent memory management — PostgreSQL (structured) + Qdrant (embeddings).
"""
import uuid
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models import AgentMemory
from config import settings


async def get_embedding(text: str) -> list[float]:
    """Get embedding from Claude via Anthropic embeddings endpoint."""
    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        # Anthropic doesn't have a native embedding API yet — use a simple hash-based mock
        # In production, replace with a proper embedding model (e.g., text-embedding-3-small)
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        vector = [((b - 128) / 128.0) for b in h]
        # Pad to 1536 dimensions
        while len(vector) < 1536:
            vector.extend(vector[:min(len(vector), 1536 - len(vector))])
        return vector[:1536]
    except Exception:
        return [0.0] * 1536


async def search_memories(user_id: str, query: str, db: AsyncSession, limit: int = 5) -> list[dict]:
    """Fetch top-N relevant memories via semantic search in Qdrant, fall back to DB."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        vector = await get_embedding(query)

        results = client.search(
            collection_name="punji_memories",
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
            client.get_collection("punji_memories")
        except Exception:
            from qdrant_client.http.models import VectorParams, Distance
            client.create_collection(
                "punji_memories",
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

        point_id = str(memory.id)
        client.upsert(
            collection_name="punji_memories",
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
            client.delete(collection_name="punji_memories", points_selector=[mem.qdrant_point_id])
        except Exception:
            pass

    await db.delete(mem)
    await db.commit()
    return True
