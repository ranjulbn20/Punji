from fastapi import APIRouter, Depends, HTTPException, Query
from models import User
from dependencies import get_current_user
from services.market_service import get_mf_nav, get_stock_price, get_macro_data, search_mf

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/mf/{scheme_code}")
async def mf_data(scheme_code: int, user: User = Depends(get_current_user)):
    data = await get_mf_nav(scheme_code)
    if not data:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return data


@router.get("/mf/search")
async def mf_search(q: str = Query(..., min_length=2), user: User = Depends(get_current_user)):
    return await search_mf(q)


@router.get("/stock/{symbol}")
async def stock_data(symbol: str, user: User = Depends(get_current_user)):
    data = await get_stock_price(symbol)
    if not data:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return data


@router.get("/macro")
async def macro_data(user: User = Depends(get_current_user)):
    return await get_macro_data()
