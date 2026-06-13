import uuid
from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class MutualFund(Base):
    __tablename__ = "mutual_funds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)

    # Instrument-specific columns
    scheme_name: Mapped[str] = mapped_column(String(500), nullable=False)
    folio_number: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    isin: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    scheme_code: Mapped[int | None] = mapped_column(nullable=True)
    units: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False, default=0)
    avg_nav: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    current_nav: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    asset_class_stored: Mapped[str] = mapped_column("asset_class", String(20), nullable=False, default="equity")

    # Common columns
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    invested_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    current_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    xirr: Mapped[float | None] = mapped_column(Numeric(6, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_refreshed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User")
    goal: Mapped["Goal | None"] = relationship("Goal")

    # --- Common interface (duck-typed by HoldingOut) ---
    @property
    def instrument_type(self) -> str:
        return "mutual_fund"

    @property
    def asset_class(self) -> str:
        return self.asset_class_stored

    @property
    def unrealised_pnl(self) -> float:
        return float(self.current_value) - float(self.invested_amount)

    @property
    def metadata_(self) -> dict:
        return {
            "isin": self.isin,
            "scheme_code": self.scheme_code,
            "folio_number": self.folio_number,
            "units": float(self.units) if self.units else 0,
            "current_nav": float(self.current_nav) if self.current_nav else 0,
            "avg_nav": float(self.avg_nav) if self.avg_nav else 0,
        }

    __table_args__ = (
        Index("idx_mutual_funds_user_id", "user_id"),
        Index("idx_mutual_funds_user_active", "user_id", "is_active"),
        Index("idx_mutual_funds_isin", "isin"),
    )
