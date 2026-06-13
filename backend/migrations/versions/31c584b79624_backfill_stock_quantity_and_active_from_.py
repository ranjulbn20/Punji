"""backfill_stock_quantity_and_active_from_trades

Revision ID: 31c584b79624
Revises: 120cf98b353b
Create Date: 2026-06-13 23:31:11.912476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '31c584b79624'
down_revision: Union[str, None] = '120cf98b353b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recompute net quantity from all StockTrade records and deactivate fully-sold stocks.
    # Only affects stocks that have at least one StockTrade row; snapshot-only imports are untouched.
    op.execute("""
        UPDATE stocks s
        SET
            quantity = GREATEST(net.qty, 0),
            is_active = CASE WHEN net.qty <= 0 THEN false ELSE s.is_active END
        FROM (
            SELECT stock_id,
                   SUM(CASE WHEN trade_type = 'buy' THEN quantity ELSE -quantity END) AS qty
            FROM stock_trades
            GROUP BY stock_id
        ) net
        WHERE s.id = net.stock_id
    """)


def downgrade() -> None:
    # Not reversible — we don't know the original quantity/is_active values.
    pass
