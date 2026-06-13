"""instrument_tables — separate table per instrument type

Revision ID: e3a1f9c2d4b5
Revises: d88d6f33b7eb
Create Date: 2026-05-24

Replaces the single `holdings` table with five typed tables:
  stocks, mutual_funds, fixed_deposits, ppf_accounts, nps_accounts

Transactions now reference instruments via (instrument_type, instrument_id)
instead of a FK to holdings.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e3a1f9c2d4b5'
down_revision: Union[str, None] = 'd88d6f33b7eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create typed instrument tables ────────────────────────────────────

    op.create_table(
        'stocks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('isin', sa.String(20), nullable=False, server_default=''),
        sa.Column('exchange', sa.String(10), nullable=False, server_default='NSE'),
        sa.Column('quantity', sa.Numeric(15, 4), nullable=False, server_default='0'),
        sa.Column('avg_price', sa.Numeric(12, 4), nullable=False, server_default='0'),
        sa.Column('current_price', sa.Numeric(12, 4), nullable=False, server_default='0'),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('invested_amount', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('current_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('xirr', sa.Numeric(6, 2), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_stocks_user_id', 'stocks', ['user_id'])
    op.create_index('idx_stocks_user_active', 'stocks', ['user_id', 'is_active'])
    op.create_index('idx_stocks_symbol', 'stocks', ['symbol'])

    op.create_table(
        'mutual_funds',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('scheme_name', sa.String(500), nullable=False),
        sa.Column('folio_number', sa.String(50), nullable=False, server_default=''),
        sa.Column('isin', sa.String(20), nullable=False, server_default=''),
        sa.Column('units', sa.Numeric(15, 4), nullable=False, server_default='0'),
        sa.Column('avg_nav', sa.Numeric(12, 4), nullable=False, server_default='0'),
        sa.Column('current_nav', sa.Numeric(12, 4), nullable=False, server_default='0'),
        sa.Column('asset_class', sa.String(20), nullable=False, server_default='equity'),
        sa.Column('display_name', sa.String(500), nullable=False),
        sa.Column('invested_amount', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('current_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('xirr', sa.Numeric(6, 2), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_mutual_funds_user_id', 'mutual_funds', ['user_id'])
    op.create_index('idx_mutual_funds_user_active', 'mutual_funds', ['user_id', 'is_active'])
    op.create_index('idx_mutual_funds_isin', 'mutual_funds', ['isin'])

    op.create_table(
        'fixed_deposits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('bank_name', sa.String(200), nullable=False, server_default=''),
        sa.Column('principal', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('interest_rate', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('start_date', sa.Date, nullable=True),
        sa.Column('maturity_date', sa.Date, nullable=True),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('invested_amount', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('current_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('xirr', sa.Numeric(6, 2), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_fixed_deposits_user_id', 'fixed_deposits', ['user_id'])
    op.create_index('idx_fixed_deposits_user_active', 'fixed_deposits', ['user_id', 'is_active'])

    op.create_table(
        'ppf_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('account_number', sa.String(30), nullable=False, server_default=''),
        sa.Column('bank_name', sa.String(200), nullable=False, server_default=''),
        sa.Column('opening_date', sa.Date, nullable=True),
        sa.Column('maturity_date', sa.Date, nullable=True),
        sa.Column('annual_contribution', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('invested_amount', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('current_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('xirr', sa.Numeric(6, 2), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_ppf_accounts_user_id', 'ppf_accounts', ['user_id'])

    op.create_table(
        'nps_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('pran', sa.String(20), nullable=False, server_default=''),
        sa.Column('tier', sa.String(5), nullable=False, server_default='I'),
        sa.Column('equity_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('corporate_bond_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('govt_bond_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('invested_amount', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('current_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('xirr', sa.Numeric(6, 2), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_nps_accounts_user_id', 'nps_accounts', ['user_id'])

    # ── 2. Migrate data from holdings into typed tables ───────────────────────

    op.execute("""
        INSERT INTO stocks (id, user_id, goal_id, symbol, isin, exchange,
                            quantity, avg_price, current_price,
                            display_name, invested_amount, current_value,
                            xirr, is_active, last_refreshed_at, created_at)
        SELECT
            id, user_id, goal_id,
            COALESCE(metadata->>'symbol', display_name || '.NS'),
            COALESCE(metadata->>'isin', ''),
            COALESCE(metadata->>'exchange', 'NSE'),
            COALESCE((metadata->>'quantity')::NUMERIC, 0),
            COALESCE((metadata->>'average_price')::NUMERIC, 0),
            COALESCE((metadata->>'current_price')::NUMERIC, 0),
            display_name, invested_amount, current_value,
            xirr, is_active, last_refreshed_at, created_at
        FROM holdings WHERE instrument_type = 'stock'
    """)

    op.execute("""
        INSERT INTO mutual_funds (id, user_id, goal_id, scheme_name, folio_number, isin,
                                  units, avg_nav, current_nav, asset_class,
                                  display_name, invested_amount, current_value,
                                  xirr, is_active, last_refreshed_at, created_at)
        SELECT
            id, user_id, goal_id,
            display_name,
            COALESCE(metadata->>'folio_number', ''),
            COALESCE(metadata->>'isin', ''),
            COALESCE((metadata->>'units')::NUMERIC, 0),
            COALESCE((metadata->>'avg_nav')::NUMERIC, 0),
            COALESCE((metadata->>'current_nav')::NUMERIC, 0),
            asset_class,
            display_name, invested_amount, current_value,
            xirr, is_active, last_refreshed_at, created_at
        FROM holdings WHERE instrument_type = 'mutual_fund'
    """)

    op.execute("""
        INSERT INTO fixed_deposits (id, user_id, goal_id, bank_name, principal,
                                    interest_rate, start_date, maturity_date,
                                    display_name, invested_amount, current_value,
                                    xirr, is_active, last_refreshed_at, created_at)
        SELECT
            id, user_id, goal_id,
            COALESCE(metadata->>'bank_name', display_name),
            invested_amount,
            COALESCE((metadata->>'interest_rate')::NUMERIC, 0),
            CASE WHEN metadata->>'start_date' IS NOT NULL
                 THEN (metadata->>'start_date')::DATE ELSE NULL END,
            CASE WHEN metadata->>'maturity_date' IS NOT NULL
                 THEN (metadata->>'maturity_date')::DATE ELSE NULL END,
            display_name, invested_amount, current_value,
            xirr, is_active, last_refreshed_at, created_at
        FROM holdings WHERE instrument_type = 'fixed_deposit'
    """)

    op.execute("""
        INSERT INTO ppf_accounts (id, user_id, goal_id, account_number, bank_name,
                                  opening_date, maturity_date, annual_contribution,
                                  display_name, invested_amount, current_value,
                                  xirr, is_active, last_refreshed_at, created_at)
        SELECT
            id, user_id, goal_id,
            COALESCE(metadata->>'account_number', ''),
            COALESCE(metadata->>'bank_name', ''),
            CASE WHEN metadata->>'opening_date' IS NOT NULL
                 THEN (metadata->>'opening_date')::DATE ELSE NULL END,
            CASE WHEN metadata->>'maturity_date' IS NOT NULL
                 THEN (metadata->>'maturity_date')::DATE ELSE NULL END,
            COALESCE((metadata->>'annual_contribution')::NUMERIC, 0),
            display_name, invested_amount, current_value,
            xirr, is_active, last_refreshed_at, created_at
        FROM holdings WHERE instrument_type = 'ppf'
    """)

    op.execute("""
        INSERT INTO nps_accounts (id, user_id, goal_id, pran, tier,
                                  equity_value, corporate_bond_value, govt_bond_value,
                                  display_name, invested_amount, current_value,
                                  xirr, is_active, last_refreshed_at, created_at)
        SELECT
            id, user_id, goal_id,
            COALESCE(metadata->>'pran', ''),
            COALESCE(metadata->>'tier', 'I'),
            COALESCE((metadata->>'equity_value')::NUMERIC, 0),
            COALESCE((metadata->>'corporate_bond_value')::NUMERIC, 0),
            COALESCE((metadata->>'govt_bond_value')::NUMERIC, 0),
            display_name, invested_amount, current_value,
            xirr, is_active, last_refreshed_at, created_at
        FROM holdings WHERE instrument_type = 'nps'
    """)

    # ── 3. Update transactions ─────────────────────────────────────────────────

    op.add_column('transactions', sa.Column('instrument_type', sa.String(50), nullable=True))
    op.add_column('transactions', sa.Column('instrument_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Populate from holdings type (same UUIDs, so holding_id = instrument_id)
    op.execute("""
        UPDATE transactions t
        SET instrument_type = h.instrument_type,
            instrument_id   = t.holding_id
        FROM holdings h
        WHERE h.id = t.holding_id
    """)

    # Make non-nullable now that data is populated
    op.alter_column('transactions', 'instrument_type', nullable=False, server_default='stock')
    op.alter_column('transactions', 'instrument_id', nullable=False)

    op.create_index('idx_transactions_instrument', 'transactions', ['instrument_type', 'instrument_id'])

    # Drop old holding_id column (drop FK first)
    op.drop_index('idx_transactions_holding_id', table_name='transactions')
    op.drop_constraint('transactions_holding_id_fkey', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'holding_id')

    # ── 4. Update alerts ───────────────────────────────────────────────────────

    op.add_column('alerts', sa.Column('related_instrument_type', sa.String(50), nullable=True))
    op.add_column('alerts', sa.Column('related_instrument_id', postgresql.UUID(as_uuid=True), nullable=True))

    op.execute("""
        UPDATE alerts a
        SET related_instrument_type = h.instrument_type,
            related_instrument_id   = a.related_holding_id
        FROM holdings h
        WHERE h.id = a.related_holding_id
    """)

    op.drop_constraint('alerts_related_holding_id_fkey', 'alerts', type_='foreignkey')
    op.drop_column('alerts', 'related_holding_id')

    # ── 5. Drop the holdings table ─────────────────────────────────────────────
    op.drop_table('holdings')


def downgrade() -> None:
    # Recreate holdings table
    op.create_table(
        'holdings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('instrument_type', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(500), nullable=False),
        sa.Column('asset_class', sa.String(20), nullable=False),
        sa.Column('invested_amount', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('current_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('xirr', sa.Numeric(6, 2), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Restore transactions.holding_id
    op.add_column('transactions', sa.Column('holding_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE transactions SET holding_id = instrument_id")
    op.drop_index('idx_transactions_instrument', table_name='transactions')
    op.drop_column('transactions', 'instrument_type')
    op.drop_column('transactions', 'instrument_id')
    # Restore alerts
    op.add_column('alerts', sa.Column('related_holding_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE alerts SET related_holding_id = related_instrument_id")
    op.drop_column('alerts', 'related_instrument_type')
    op.drop_column('alerts', 'related_instrument_id')
    # Drop new tables
    op.drop_table('nps_accounts')
    op.drop_table('ppf_accounts')
    op.drop_table('fixed_deposits')
    op.drop_table('mutual_funds')
    op.drop_table('stocks')
