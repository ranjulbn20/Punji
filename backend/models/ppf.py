import uuid
from sqlalchemy import String, Numeric, Boolean, DateTime, Date, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class PPFAccount(Base):
    __tablename__ = "ppf_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)

    # Instrument-specific columns
    account_number: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    bank_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    opening_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    maturity_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    annual_contribution: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)

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
        return "ppf"

    @property
    def asset_class(self) -> str:
        return "debt"

    @property
    def unrealised_pnl(self) -> float:
        return float(self.current_value) - float(self.invested_amount)

    @property
    def metadata_(self) -> dict:
        return {
            "account_number": self.account_number,
            "bank_name": self.bank_name,
            "annual_contribution": float(self.annual_contribution) if self.annual_contribution else 0,
            "opening_date": str(self.opening_date) if self.opening_date else None,
            "maturity_date": str(self.maturity_date) if self.maturity_date else None,
        }

    __table_args__ = (
        Index("idx_ppf_accounts_user_id", "user_id"),
    )
