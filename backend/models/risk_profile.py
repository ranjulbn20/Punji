import uuid
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, func, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    drawdown_response: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    risk_category: Mapped[str | None] = mapped_column(String(20))

    target_equity_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    target_debt_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    target_gold_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    target_cash_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))

    additional_context: Mapped[dict] = mapped_column(JSONB, default=dict)

    last_reviewed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="risk_profile")

    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 1 AND 10", name="ck_risk_score_range"),
    )
