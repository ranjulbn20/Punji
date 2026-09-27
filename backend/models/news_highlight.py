import uuid
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class NewsHighlight(Base):
    __tablename__ = "news_highlights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    # Polymorphic instrument reference — no FK constraint since instruments span multiple tables
    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False)
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    holding_name: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)

    category: Mapped[str] = mapped_column(String(20), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="news_highlights")

    __table_args__ = (
        Index("idx_news_highlights_user_id", "user_id", "created_at"),
    )
