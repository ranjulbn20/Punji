import uuid
from sqlalchemy import String, Boolean, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    profile_picture_url: Mapped[str | None] = mapped_column(String(500))

    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_user_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    auth_provider: Mapped[str] = mapped_column(String(20), default="email")

    onboarding_step: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    risk_profile: Mapped["RiskProfile"] = relationship("RiskProfile", back_populates="user", uselist=False)
    holdings: Mapped[list["Holding"]] = relationship("Holding", back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    goals: Mapped[list["Goal"]] = relationship("Goal", back_populates="user")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="user")
    agent_memories: Mapped[list["AgentMemory"]] = relationship("AgentMemory", back_populates="user")
    portfolio_snapshots: Mapped[list["PortfolioSnapshot"]] = relationship("PortfolioSnapshot", back_populates="user")
    import_jobs: Mapped[list["ImportJob"]] = relationship("ImportJob", back_populates="user")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="user")
