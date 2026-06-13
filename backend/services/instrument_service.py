"""
Helpers for querying instruments across the five typed tables.
All code that previously queried the `holdings` table should use these.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Stock, MutualFund, FixedDeposit, PPFAccount, NPSAccount, INSTRUMENT_MODEL_MAP


ALL_INSTRUMENT_MODELS = [Stock, MutualFund, FixedDeposit, PPFAccount, NPSAccount]


async def get_all_instruments(db: AsyncSession, user_id, active_only: bool = True) -> list:
    """Return every instrument for a user across all five tables."""
    results = []
    for model in ALL_INSTRUMENT_MODELS:
        q = select(model).where(model.user_id == user_id)
        if active_only:
            q = q.where(model.is_active == True)
        rows = await db.execute(q)
        results.extend(rows.scalars().all())
    return results


async def get_instruments_by_type(
    db: AsyncSession, user_id, instrument_type: str, active_only: bool = True
) -> list:
    model = INSTRUMENT_MODEL_MAP.get(instrument_type)
    if not model:
        return []
    q = select(model).where(model.user_id == user_id)
    if active_only:
        q = q.where(model.is_active == True)
    rows = await db.execute(q)
    return rows.scalars().all()


async def get_instrument_by_id(db: AsyncSession, user_id, instrument_type: str, instrument_id):
    model = INSTRUMENT_MODEL_MAP.get(instrument_type)
    if not model:
        return None
    result = await db.execute(
        select(model).where(model.id == instrument_id, model.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def find_existing_instrument(db: AsyncSession, user_id, dto: dict):
    """
    Dedup lookup before creating an instrument on import.
    Stocks match by symbol. MFs match by scheme_name + folio_number.
    Others match by display_name.
    """
    instrument_type = dto["instrument_type"]
    meta = dto.get("metadata", {})

    if instrument_type == "stock":
        symbol = meta.get("symbol") or dto.get("display_name", "") + ".NS"
        result = await db.execute(
            select(Stock).where(
                Stock.user_id == user_id,
                Stock.is_active == True,
                Stock.symbol == symbol,
            )
        )
        return result.scalar_one_or_none()

    if instrument_type == "mutual_fund":
        folio = meta.get("folio_number", "")
        scheme = dto.get("display_name", "")
        q = select(MutualFund).where(
            MutualFund.user_id == user_id,
            MutualFund.is_active == True,
            MutualFund.scheme_name == scheme,
        )
        if folio:
            q = q.where(MutualFund.folio_number == folio)
        result = await db.execute(q)
        return result.scalar_one_or_none()

    # Generic fallback: match by display_name
    model = INSTRUMENT_MODEL_MAP.get(instrument_type)
    if not model:
        return None
    result = await db.execute(
        select(model).where(
            model.user_id == user_id,
            model.is_active == True,
            model.display_name == dto.get("display_name", ""),
        )
    )
    return result.scalar_one_or_none()


def build_instrument_from_dto(user_id, dto: dict):
    """Create (but don't add to session) the right instrument model from an import DTO."""
    instrument_type = dto["instrument_type"]
    meta = dto.get("metadata", {})

    common = dict(
        user_id=user_id,
        display_name=dto["display_name"],
        invested_amount=dto["invested_amount"],
        current_value=dto["current_value"],
    )

    if instrument_type == "stock":
        return Stock(
            **common,
            symbol=meta.get("symbol", dto["display_name"] + ".NS"),
            isin=meta.get("isin", ""),
            exchange=meta.get("exchange", "NSE"),
            quantity=meta.get("quantity", 0),
            avg_price=meta.get("average_price", 0),
            current_price=meta.get("current_price", 0),
        )

    if instrument_type == "mutual_fund":
        return MutualFund(
            **common,
            scheme_name=dto["display_name"],
            folio_number=meta.get("folio_number", ""),
            isin=meta.get("isin", ""),
            units=meta.get("units", 0),
            avg_nav=meta.get("avg_nav", 0),
            current_nav=meta.get("current_nav", 0),
            asset_class_stored=dto.get("asset_class", "equity"),
        )

    if instrument_type == "fixed_deposit":
        from datetime import date
        def _parse_date(s):
            try:
                return date.fromisoformat(s) if s else None
            except ValueError:
                return None
        return FixedDeposit(
            **common,
            bank_name=meta.get("bank_name", dto["display_name"]),
            principal=dto["invested_amount"],
            interest_rate=meta.get("interest_rate", 0),
            start_date=_parse_date(meta.get("start_date")),
            maturity_date=_parse_date(meta.get("maturity_date")),
        )

    if instrument_type == "ppf":
        from datetime import date
        def _parse_date(s):
            try:
                return date.fromisoformat(s) if s else None
            except ValueError:
                return None
        return PPFAccount(
            **common,
            account_number=meta.get("account_number", ""),
            bank_name=meta.get("bank_name", ""),
            opening_date=_parse_date(meta.get("opening_date")),
            maturity_date=_parse_date(meta.get("maturity_date")),
            annual_contribution=meta.get("annual_contribution", 0),
        )

    if instrument_type == "nps":
        return NPSAccount(
            **common,
            pran=meta.get("pran", ""),
            tier=meta.get("tier", "I"),
            equity_value=meta.get("equity_value", 0),
            corporate_bond_value=meta.get("corporate_bond_value", 0),
            govt_bond_value=meta.get("govt_bond_value", 0),
        )

    raise ValueError(f"Unknown instrument_type: {instrument_type}")
