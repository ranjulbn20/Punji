"""
Helpers for querying instruments across the five typed tables.
All code that previously queried the `holdings` table should use these.
"""
import base64
import uuid as uuid_lib
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, union_all, literal, tuple_, func, case

from models import Stock, MutualFund, FixedDeposit, PPFAccount, NPSAccount, INSTRUMENT_MODEL_MAP


ALL_INSTRUMENT_MODELS = [Stock, MutualFund, FixedDeposit, PPFAccount, NPSAccount]

# asset_class is a hardcoded property (not a column) on every model except MutualFund.
CONSTANT_ASSET_CLASS = {"stock": "equity", "fixed_deposit": "debt", "ppf": "debt", "nps": "equity"}


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
    Stocks match by symbol first, then fall back to ISIN (handles renamed tickers like ZOMATO→ETERNAL).
    MFs match by scheme_name + folio_number. Others match by display_name.
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
        match = result.scalar_one_or_none()
        if match:
            return match
        # Fallback: match by ISIN for renamed stocks (e.g. ZOMATO → ETERNAL, SHRIRAMTRANS → SHRIRAMFIN)
        isin = meta.get("isin", "")
        if isin:
            result = await db.execute(
                select(Stock).where(
                    Stock.user_id == user_id,
                    Stock.is_active == True,
                    Stock.isin == isin,
                )
            )
            return result.scalar_one_or_none()
        return None

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
            scheme_code=meta.get("scheme_code"),
            units=meta.get("units", 0),
            avg_nav=meta.get("average_nav") or meta.get("avg_nav", 0),
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


# ── Keyset pagination across the five typed tables ─────────────────────────────
# Ordered by (created_at desc, id desc); the cursor opaquely encodes the last
# row's (created_at, id) so the next page asks for rows strictly before it.

def encode_cursor(created_at: datetime, id_: uuid_lib.UUID) -> str:
    raw = f"{created_at.isoformat()}|{id_}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid_lib.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    created_at_str, id_str = raw.rsplit("|", 1)
    return datetime.fromisoformat(created_at_str), uuid_lib.UUID(id_str)


async def get_instruments_page(
    db: AsyncSession,
    user_id,
    instrument_type: str | None = None,
    asset_class: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    active_only: bool = True,
) -> tuple[list, str | None]:
    """Return one keyset-paginated page of instruments plus the next cursor (None if last page)."""
    cursor_key = decode_cursor(cursor) if cursor else None

    types = [instrument_type] if instrument_type else list(INSTRUMENT_MODEL_MAP.keys())
    if asset_class:
        types = [t for t in types if t == "mutual_fund" or CONSTANT_ASSET_CLASS.get(t) == asset_class]
    if not types:
        return [], None

    if len(types) == 1:
        model = INSTRUMENT_MODEL_MAP[types[0]]
        q = select(model).where(model.user_id == user_id)
        if active_only:
            q = q.where(model.is_active == True)
        if asset_class and hasattr(model, "asset_class_stored"):
            q = q.where(model.asset_class_stored == asset_class)
        if cursor_key:
            q = q.where(tuple_(model.created_at, model.id) < tuple_(*cursor_key))
        q = q.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)
        rows = (await db.execute(q)).scalars().all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
        return rows, next_cursor

    # Multiple types (e.g. the "All" tab): find the page across all tables first via a
    # UNION ALL of (id, created_at, instrument_type), then batch-fetch full rows per type.
    branches = []
    for t in types:
        model = INSTRUMENT_MODEL_MAP[t]
        b = select(
            model.id.label("id"),
            model.created_at.label("created_at"),
            literal(t).label("instrument_type"),
        ).where(model.user_id == user_id)
        if active_only:
            b = b.where(model.is_active == True)
        if asset_class and t == "mutual_fund":
            b = b.where(model.asset_class_stored == asset_class)
        branches.append(b)

    union_sq = union_all(*branches).subquery()
    q = select(union_sq.c.id, union_sq.c.created_at, union_sq.c.instrument_type)
    if cursor_key:
        q = q.where(tuple_(union_sq.c.created_at, union_sq.c.id) < tuple_(*cursor_key))
    q = q.order_by(union_sq.c.created_at.desc(), union_sq.c.id.desc()).limit(limit + 1)
    page_rows = (await db.execute(q)).all()

    has_more = len(page_rows) > limit
    page_rows = page_rows[:limit]
    if not page_rows:
        return [], None

    ids_by_type: dict[str, list] = {}
    for row in page_rows:
        ids_by_type.setdefault(row.instrument_type, []).append(row.id)

    fetched = {}
    for t, ids in ids_by_type.items():
        model = INSTRUMENT_MODEL_MAP[t]
        result = await db.execute(select(model).where(model.id.in_(ids)))
        for obj in result.scalars().all():
            fetched[obj.id] = obj

    ordered = [fetched[row.id] for row in page_rows if row.id in fetched]
    next_cursor = encode_cursor(page_rows[-1].created_at, page_rows[-1].id) if has_more else None
    return ordered, next_cursor


async def get_holdings_summary(db: AsyncSession, user_id, active_only: bool = True) -> list[dict]:
    """Per-instrument-type aggregate: count, invested/current amounts, P&L, and value-weighted XIRR."""
    results = []
    for t, model in INSTRUMENT_MODEL_MAP.items():
        xirr_weight = func.coalesce(
            func.sum(case((model.xirr.isnot(None), model.current_value), else_=0)), 0
        )
        xirr_weighted_sum = func.coalesce(
            func.sum(case((model.xirr.isnot(None), model.xirr * model.current_value), else_=0)), 0
        )
        q = select(
            func.count(model.id),
            func.coalesce(func.sum(model.invested_amount), 0),
            func.coalesce(func.sum(model.current_value), 0),
            xirr_weighted_sum,
            xirr_weight,
        ).where(model.user_id == user_id)
        if active_only:
            q = q.where(model.is_active == True)
        count, invested, current, w_sum, w_weight = (await db.execute(q)).one()
        results.append({
            "instrument_type": t,
            "count": count,
            "invested_amount": float(invested),
            "current_value": float(current),
            "unrealised_pnl": float(current) - float(invested),
            "xirr": (float(w_sum) / float(w_weight)) if w_weight else None,
        })
    return results
