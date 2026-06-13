import uuid
from sqlalchemy import Integer, String, Numeric, Date, DateTime, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class FundComposition(Base):
    __tablename__ = "fund_compositions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_code: Mapped[int] = mapped_column(Integer, nullable=False)
    company_isin: Mapped[str] = mapped_column(String(20), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    disclosure_month: Mapped[Date] = mapped_column(Date, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("scheme_code", "company_isin", "disclosure_month", name="uq_fund_comp"),
        Index("idx_fund_comp_scheme", "scheme_code", "disclosure_month"),
        Index("idx_fund_comp_isin", "company_isin"),
    )
