import uuid
from sqlalchemy import String, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class BusinessGroupMapping(Base):
    __tablename__ = "business_group_mapping"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_isin: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_name: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_bgm_group", "group_name"),
        Index("idx_bgm_isin", "company_isin"),
    )
