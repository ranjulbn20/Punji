import uuid
from sqlalchemy import String, Integer, Boolean, Text, DateTime, ForeignKey, Index, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    related_holding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("holdings.id", ondelete="SET NULL"), nullable=True)
    related_goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)

    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    signal_score: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_acted_upon: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="alerts")
    related_holding: Mapped["Holding | None"] = relationship("Holding", back_populates="alerts")
    related_goal: Mapped["Goal | None"] = relationship("Goal", back_populates="alerts")

    __table_args__ = (
        CheckConstraint("signal_score BETWEEN 1 AND 10", name="ck_signal_score_range"),
        Index("idx_alerts_user_id", "user_id"),
        Index("idx_alerts_user_unread", "user_id", "is_read", "created_at"),
    )
