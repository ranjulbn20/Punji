"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("profile_picture_url", sa.String(500)),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("google_user_id", sa.String(255), unique=True),
        sa.Column("auth_provider", sa.String(20), server_default="email"),
        sa.Column("onboarding_step", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "risk_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True),
        sa.Column("drawdown_response", sa.String(20), nullable=False),
        sa.Column("risk_score", sa.Integer, sa.CheckConstraint("risk_score BETWEEN 1 AND 10")),
        sa.Column("risk_category", sa.String(20)),
        sa.Column("target_equity_pct", sa.Numeric(5, 2)),
        sa.Column("target_debt_pct", sa.Numeric(5, 2)),
        sa.Column("target_gold_pct", sa.Numeric(5, 2)),
        sa.Column("target_cash_pct", sa.Numeric(5, 2)),
        sa.Column("additional_context", JSONB, server_default="{}"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "goals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("goal_type", sa.String(50)),
        sa.Column("target_amount", sa.BigInteger, nullable=False),
        sa.Column("target_date", sa.Date, nullable=False),
        sa.Column("monthly_sip_allocated", sa.Integer, server_default="0"),
        sa.Column("priority", sa.Integer, server_default="1"),
        sa.Column("success_probability", sa.Numeric(5, 2)),
        sa.Column("required_monthly_sip", sa.Integer),
        sa.Column("projected_corpus_p10", sa.BigInteger),
        sa.Column("projected_corpus_p50", sa.BigInteger),
        sa.Column("projected_corpus_p90", sa.BigInteger),
        sa.Column("last_simulation_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "holdings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("goal_id", UUID(as_uuid=True), sa.ForeignKey("goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("instrument_type", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.Column("invested_amount", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("current_value", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("xirr", sa.Numeric(6, 2)),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_holdings_user_id", "holdings", ["user_id"])
    op.create_index("idx_holdings_user_active", "holdings", ["user_id", "is_active"])
    op.create_index("idx_holdings_instrument_type", "holdings", ["instrument_type"])
    op.create_index("idx_holdings_asset_class", "holdings", ["asset_class"])

    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("holding_id", UUID(as_uuid=True), sa.ForeignKey("holdings.id", ondelete="CASCADE")),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("units", sa.Numeric(15, 4)),
        sa.Column("price", sa.Numeric(12, 4)),
        sa.Column("notes", sa.Text),
        sa.Column("import_source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_transactions_user_id", "transactions", ["user_id"])
    op.create_index("idx_transactions_holding_id", "transactions", ["holding_id"])
    op.create_index("idx_transactions_date", "transactions", ["transaction_date"])
    op.create_index("idx_transactions_user_date", "transactions", ["user_id", "transaction_date"])

    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("related_holding_id", UUID(as_uuid=True), sa.ForeignKey("holdings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_goal_id", UUID(as_uuid=True), sa.ForeignKey("goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("reasoning", sa.Text),
        sa.Column("signal_score", sa.Integer, sa.CheckConstraint("signal_score BETWEEN 1 AND 10")),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("is_acted_upon", sa.Boolean, server_default="false"),
        sa.Column("user_feedback", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_alerts_user_id", "alerts", ["user_id"])
    op.create_index("idx_alerts_user_unread", "alerts", ["user_id", "is_read", "created_at"])

    op.create_table(
        "agent_memory",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("memory_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("qdrant_point_id", sa.String(255)),
        sa.Column("confidence", sa.Numeric(3, 2), server_default="1.0"),
        sa.Column("times_referenced", sa.Integer, server_default="0"),
        sa.Column("last_referenced_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_agent_memory_user_id", "agent_memory", ["user_id"])
    op.create_index("idx_agent_memory_type", "agent_memory", ["user_id", "memory_type"])

    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("total_value", sa.BigInteger, nullable=False),
        sa.Column("equity_value", sa.BigInteger, server_default="0"),
        sa.Column("debt_value", sa.BigInteger, server_default="0"),
        sa.Column("gold_value", sa.BigInteger, server_default="0"),
        sa.Column("cash_value", sa.BigInteger, server_default="0"),
        sa.Column("other_value", sa.BigInteger, server_default="0"),
        sa.Column("equity_pct", sa.Numeric(5, 2)),
        sa.Column("debt_pct", sa.Numeric(5, 2)),
        sa.Column("gold_pct", sa.Numeric(5, 2)),
        sa.Column("portfolio_xirr", sa.Numeric(6, 2)),
        sa.Column("nifty50_return_1y", sa.Numeric(6, 2)),
        sa.Column("nifty500_return_1y", sa.Numeric(6, 2)),
        sa.UniqueConstraint("user_id", "snapshot_date", name="uq_snapshot_user_date"),
    )
    op.create_index("idx_snapshots_user_date", "portfolio_snapshots", ["user_id", "snapshot_date"])

    op.create_table(
        "fund_compositions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scheme_code", sa.Integer, nullable=False),
        sa.Column("company_isin", sa.String(20), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("weight_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column("disclosure_month", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("scheme_code", "company_isin", "disclosure_month", name="uq_fund_comp"),
    )
    op.create_index("idx_fund_comp_scheme", "fund_compositions", ["scheme_code", "disclosure_month"])
    op.create_index("idx_fund_comp_isin", "fund_compositions", ["company_isin"])

    op.create_table(
        "business_group_mapping",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_isin", sa.String(20), unique=True, nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("group_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_bgm_group", "business_group_mapping", ["group_name"])
    op.create_index("idx_bgm_isin", "business_group_mapping", ["company_isin"])

    op.create_table(
        "import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("source_platform", sa.String(50), nullable=False),
        sa.Column("file_name", sa.String(255)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("preview_data", JSONB),
        sa.Column("holdings_created", sa.Integer, server_default="0"),
        sa.Column("holdings_updated", sa.Integer, server_default="0"),
        sa.Column("transactions_created", sa.Integer, server_default="0"),
        sa.Column("warnings", JSONB, server_default="[]"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_conversations_user", "conversations", ["user_id", "created_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE")),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("reasoning_trace", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Seed business group mapping
    op.execute("""
    INSERT INTO business_group_mapping (company_isin, company_name, group_name) VALUES
    ('INE040A01034', 'HDFC Bank Ltd', 'HDFC Group'),
    ('INE795G01014', 'HDFC Life Insurance', 'HDFC Group'),
    ('INE127D01025', 'HDFC Asset Management', 'HDFC Group'),
    ('INE001A01036', 'TCS Ltd', 'Tata Group'),
    ('INE155A01022', 'Tata Motors Ltd', 'Tata Group'),
    ('INE081A01020', 'Tata Steel Ltd', 'Tata Group'),
    ('INE280A01028', 'Titan Company Ltd', 'Tata Group'),
    ('INE192A01025', 'Tata Consumer Products', 'Tata Group'),
    ('INE245A01021', 'Tata Power Company', 'Tata Group'),
    ('INE500L01023', 'Tata Communications', 'Tata Group'),
    ('INE203G01027', 'Indian Hotels Co', 'Tata Group'),
    ('INE100A01010', 'Voltas Ltd', 'Tata Group'),
    ('INE423A01024', 'Adani Enterprises', 'Adani Group'),
    ('INE742F01042', 'Adani Ports & SEZ', 'Adani Group'),
    ('INE814H01011', 'Adani Power Ltd', 'Adani Group'),
    ('INE364U01010', 'Adani Green Energy', 'Adani Group'),
    ('INE002A01018', 'Reliance Industries', 'Reliance Group'),
    ('INE545U01014', 'Jio Financial Services', 'Reliance Group'),
    ('INE294B01019', 'Network18 Media', 'Reliance Group'),
    ('INE296A01024', 'Bajaj Finance Ltd', 'Bajaj Group'),
    ('INE918I01018', 'Bajaj Finserv Ltd', 'Bajaj Group'),
    ('INE917I01010', 'Bajaj Auto Ltd', 'Bajaj Group'),
    ('INE101A01026', 'Mahindra & Mahindra', 'Mahindra Group'),
    ('INE669C01036', 'Tech Mahindra Ltd', 'Mahindra Group'),
    ('INE103A01014', 'Mahindra Lifespace', 'Mahindra Group')
    ON CONFLICT (company_isin) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_table("import_jobs")
    op.drop_table("business_group_mapping")
    op.drop_table("fund_compositions")
    op.drop_table("portfolio_snapshots")
    op.drop_table("agent_memory")
    op.drop_table("alerts")
    op.drop_table("transactions")
    op.drop_table("holdings")
    op.drop_table("goals")
    op.drop_table("risk_profiles")
    op.drop_table("users")
