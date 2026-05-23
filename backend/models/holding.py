import uuid
from sqlalchemy import String, BigInteger, Boolean, Numeric, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)

    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)

    invested_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    current_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    xirr: Mapped[float | None] = mapped_column(Numeric(6, 2))

    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_refreshed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="holdings")
    goal: Mapped["Goal | None"] = relationship("Goal", back_populates="holdings")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="holding")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="related_holding")

    @property
    def unrealised_pnl(self) -> int:
        return self.current_value - self.invested_amount

    __table_args__ = (
        Index("idx_holdings_user_id", "user_id"),
        Index("idx_holdings_user_active", "user_id", "is_active"),
        Index("idx_holdings_instrument_type", "instrument_type"),
        Index("idx_holdings_asset_class", "asset_class"),
    )
