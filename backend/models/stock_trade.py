import uuid
from sqlalchemy import String, Numeric, Boolean, Date, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class StockTrade(Base):
    __tablename__ = "stock_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    stock_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"))

    trade_date: Mapped[Date] = mapped_column(Date, nullable=False)
    trade_type: Mapped[str] = mapped_column(String(10), nullable=False)   # "buy" | "sell"
    quantity: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)  # signed: positive=buy, negative=sell

    exchange: Mapped[str] = mapped_column(String(10), nullable=False, default="NSE")
    segment: Mapped[str | None] = mapped_column(String(10), nullable=True)   # "EQ", "BE", etc.
    trade_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # broker's ID, used for dedup
    import_source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User")
    stock: Mapped["Stock"] = relationship("Stock", back_populates="trades")

    __table_args__ = (
        Index("idx_stock_trades_user_id", "user_id"),
        Index("idx_stock_trades_stock_id", "stock_id"),
        Index("idx_stock_trades_trade_date", "trade_date"),
        Index("idx_stock_trades_stock_date", "stock_id", "trade_date"),
    )
