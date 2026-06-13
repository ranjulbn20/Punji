import uuid
from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    # Polymorphic instrument reference — no FK constraint since it spans multiple tables
    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False)   # stock | mutual_fund | fixed_deposit | ppf | nps
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    transaction_date: Mapped[Date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)  # buy | sell | sip | dividend_reinvest
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    units: Mapped[float | None] = mapped_column(Numeric(15, 4))
    price: Mapped[float | None] = mapped_column(Numeric(12, 4))

    notes: Mapped[str | None] = mapped_column(Text)
    import_source: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="transactions")

    __table_args__ = (
        Index("idx_transactions_user_id", "user_id"),
        Index("idx_transactions_instrument", "instrument_type", "instrument_id"),
        Index("idx_transactions_date", "transaction_date"),
        Index("idx_transactions_user_date", "user_id", "transaction_date"),
    )
