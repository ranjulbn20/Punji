import uuid
from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)

    # Instrument-specific columns
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)     # e.g. "AIRTEL.NS"
    isin: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    exchange: Mapped[str] = mapped_column(String(10), nullable=False, default="NSE")
    quantity: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False, default=0)
    avg_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    current_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)

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

    # --- Common interface (duck-typed by HoldingOut) ---
    @property
    def instrument_type(self) -> str:
        return "stock"

    @property
    def asset_class(self) -> str:
        return "equity"

    @property
    def unrealised_pnl(self) -> float:
        return float(self.current_value) - float(self.invested_amount)

    @property
    def metadata_(self) -> dict:
        return {
            "symbol": self.symbol,
            "isin": self.isin,
            "exchange": self.exchange,
            "quantity": float(self.quantity) if self.quantity else 0,
            "average_price": float(self.avg_price) if self.avg_price else 0,
            "current_price": float(self.current_price) if self.current_price else 0,
        }

    __table_args__ = (
        Index("idx_stocks_user_id", "user_id"),
        Index("idx_stocks_user_active", "user_id", "is_active"),
        Index("idx_stocks_symbol", "symbol"),
    )
