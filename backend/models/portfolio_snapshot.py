import uuid
from sqlalchemy import BigInteger, Numeric, Date, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    snapshot_date: Mapped[Date] = mapped_column(Date, nullable=False)
    total_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    equity_value: Mapped[int] = mapped_column(BigInteger, default=0)
    debt_value: Mapped[int] = mapped_column(BigInteger, default=0)
    gold_value: Mapped[int] = mapped_column(BigInteger, default=0)
    cash_value: Mapped[int] = mapped_column(BigInteger, default=0)
    other_value: Mapped[int] = mapped_column(BigInteger, default=0)

    equity_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    debt_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    gold_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))

    portfolio_xirr: Mapped[float | None] = mapped_column(Numeric(6, 2))
    nifty50_return_1y: Mapped[float | None] = mapped_column(Numeric(6, 2))
    nifty500_return_1y: Mapped[float | None] = mapped_column(Numeric(6, 2))

    user: Mapped["User"] = relationship("User", back_populates="portfolio_snapshots")

    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_snapshot_user_date"),
        Index("idx_snapshots_user_date", "user_id", "snapshot_date"),
    )
