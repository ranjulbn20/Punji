"""monetary_values_to_rupees

Revision ID: d88d6f33b7eb
Revises: 001
Create Date: 2026-05-23 18:56:01.332157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd88d6f33b7eb'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert paise → rupees by dividing all monetary columns by 100
    op.execute("ALTER TABLE holdings ALTER COLUMN invested_amount TYPE NUMERIC(15,2) USING invested_amount / 100.0")
    op.execute("ALTER TABLE holdings ALTER COLUMN current_value TYPE NUMERIC(15,2) USING current_value / 100.0")

    op.execute("ALTER TABLE transactions ALTER COLUMN amount TYPE NUMERIC(15,2) USING amount / 100.0")

    op.execute("ALTER TABLE goals ALTER COLUMN target_amount TYPE NUMERIC(15,2) USING target_amount / 100.0")
    op.execute("ALTER TABLE goals ALTER COLUMN monthly_sip_allocated TYPE NUMERIC(15,2) USING monthly_sip_allocated / 100.0")
    op.execute("ALTER TABLE goals ALTER COLUMN required_monthly_sip TYPE NUMERIC(15,2) USING CASE WHEN required_monthly_sip IS NULL THEN NULL ELSE required_monthly_sip / 100.0 END")
    op.execute("ALTER TABLE goals ALTER COLUMN projected_corpus_p10 TYPE NUMERIC(15,2) USING CASE WHEN projected_corpus_p10 IS NULL THEN NULL ELSE projected_corpus_p10 / 100.0 END")
    op.execute("ALTER TABLE goals ALTER COLUMN projected_corpus_p50 TYPE NUMERIC(15,2) USING CASE WHEN projected_corpus_p50 IS NULL THEN NULL ELSE projected_corpus_p50 / 100.0 END")
    op.execute("ALTER TABLE goals ALTER COLUMN projected_corpus_p90 TYPE NUMERIC(15,2) USING CASE WHEN projected_corpus_p90 IS NULL THEN NULL ELSE projected_corpus_p90 / 100.0 END")


def downgrade() -> None:
    op.execute("ALTER TABLE holdings ALTER COLUMN invested_amount TYPE BIGINT USING (invested_amount * 100)::BIGINT")
    op.execute("ALTER TABLE holdings ALTER COLUMN current_value TYPE BIGINT USING (current_value * 100)::BIGINT")
    op.execute("ALTER TABLE transactions ALTER COLUMN amount TYPE BIGINT USING (amount * 100)::BIGINT")
    op.execute("ALTER TABLE goals ALTER COLUMN target_amount TYPE BIGINT USING (target_amount * 100)::BIGINT")
    op.execute("ALTER TABLE goals ALTER COLUMN monthly_sip_allocated TYPE INTEGER USING (monthly_sip_allocated * 100)::INTEGER")
    op.execute("ALTER TABLE goals ALTER COLUMN required_monthly_sip TYPE INTEGER USING CASE WHEN required_monthly_sip IS NULL THEN NULL ELSE (required_monthly_sip * 100)::INTEGER END")
    op.execute("ALTER TABLE goals ALTER COLUMN projected_corpus_p10 TYPE BIGINT USING CASE WHEN projected_corpus_p10 IS NULL THEN NULL ELSE (projected_corpus_p10 * 100)::BIGINT END")
    op.execute("ALTER TABLE goals ALTER COLUMN projected_corpus_p50 TYPE BIGINT USING CASE WHEN projected_corpus_p50 IS NULL THEN NULL ELSE (projected_corpus_p50 * 100)::BIGINT END")
    op.execute("ALTER TABLE goals ALTER COLUMN projected_corpus_p90 TYPE BIGINT USING CASE WHEN projected_corpus_p90 IS NULL THEN NULL ELSE (projected_corpus_p90 * 100)::BIGINT END")
