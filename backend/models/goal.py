import uuid
from sqlalchemy import String, Integer, BigInteger, Date, Boolean, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_type: Mapped[str | None] = mapped_column(String(50))
    target_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_date: Mapped[Date] = mapped_column(Date, nullable=False)
    monthly_sip_allocated: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, default=1)

    success_probability: Mapped[float | None] = mapped_column(Numeric(5, 2))
    required_monthly_sip: Mapped[int | None] = mapped_column(Integer)
    projected_corpus_p10: Mapped[int | None] = mapped_column(BigInteger)
    projected_corpus_p50: Mapped[int | None] = mapped_column(BigInteger)
    projected_corpus_p90: Mapped[int | None] = mapped_column(BigInteger)
    last_simulation_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="goals")
    holdings: Mapped[list["Holding"]] = relationship("Holding", back_populates="goal")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="related_goal")
