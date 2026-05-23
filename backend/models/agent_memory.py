import uuid
from sqlalchemy import String, Integer, Numeric, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255))

    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)
    times_referenced: Mapped[int] = mapped_column(Integer, default=0)
    last_referenced_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="agent_memories")

    __table_args__ = (
        Index("idx_agent_memory_user_id", "user_id"),
        Index("idx_agent_memory_type", "user_id", "memory_type"),
    )
