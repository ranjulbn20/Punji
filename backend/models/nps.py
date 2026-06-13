import uuid
from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class NPSAccount(Base):
    __tablename__ = "nps_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)

    # Instrument-specific columns
    pran: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    tier: Mapped[str] = mapped_column(String(5), nullable=False, default="I")   # "I" or "II"
    equity_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    corporate_bond_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    govt_bond_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)

    # Common columns
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    invested_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    current_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    xirr: Mapped[float | None] = mapped_column(Numeric(6, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_refreshed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User")
    goal: Mapped["Goal | None"] = relationship("Goal")

    @property
    def instrument_type(self) -> str:
        return "nps"

    @property
    def asset_class(self) -> str:
        return "equity"

    @property
    def unrealised_pnl(self) -> float:
        return float(self.current_value) - float(self.invested_amount)

    @property
    def metadata_(self) -> dict:
        return {
            "pran": self.pran,
            "tier": self.tier,
            "equity_value": float(self.equity_value) if self.equity_value else 0,
            "corporate_bond_value": float(self.corporate_bond_value) if self.corporate_bond_value else 0,
            "govt_bond_value": float(self.govt_bond_value) if self.govt_bond_value else 0,
        }

    __table_args__ = (
        Index("idx_nps_accounts_user_id", "user_id"),
    )
