from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from services import syphoon, intelligence
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["browse"])


# ── Category ──────────────────────────────────────────────────────────────────
@router.get("/category")
async def browse_category(
    cat_id:        str = Query(...),
    zipcode:       str = Query(...),
    next_page_url: Optional[str] = Query(None),
):
    try:
        raw      = await syphoon.fetch_category(cat_id, zipcode, next_page_url)
        products = syphoon.extract_listing_products(raw)
        next_url, _ = syphoon.get_pagination(raw)
        return {
            "success":  True,
            "data":     products,
            "next_url": next_url,
            "count":    len(products),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Keyword Search ─────────────────────────────────────────────────────────────
class SearchNextPageRequest(BaseModel):
    keyword:           str
    zipcode:           str
    next_page_url:     Optional[str] = None
    next_page_payload: Optional[dict] = None


@router.get("/search")
async def keyword_search(
    keyword: str = Query(...),
    zipcode: str = Query(...),
):
    """First page search."""
    try:
        raw      = await syphoon.fetch_keyword(keyword, zipcode)
        products = syphoon.extract_listing_products(raw)
        next_url, next_payload = syphoon.get_pagination(raw)
        return {
            "success":          True,
            "data":             products,
            "next_url":         next_url,
            "next_payload":     next_payload,
            "count":            len(products),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/search/next")
async def keyword_search_next(req: SearchNextPageRequest):
    """Subsequent pages — POST because next_page_payload can be large."""
    try:
        raw      = await syphoon.fetch_keyword(req.keyword, req.zipcode, req.next_page_url, req.next_page_payload)
        products = syphoon.extract_listing_products(raw)
        next_url, next_payload = syphoon.get_pagination(raw)
        return {
            "success":      True,
            "data":         products,
            "next_url":     next_url,
            "next_payload": next_payload,
            "count":        len(products),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Bulk track from search/category results ────────────────────────────────────
class BulkTrackRequest(BaseModel):
    product_ids: list[str]
    zipcode:     str


@router.post("/track-bulk")
async def bulk_track(req: BulkTrackRequest, db: AsyncSession = Depends(get_db)):
    """Track multiple products at once (from category/search results)."""
    await intelligence.upsert_zipcode(db, req.zipcode)
    results = []
    for pid in req.product_ids:
        try:
            raw    = await syphoon.fetch_product(pid, req.zipcode)
            parsed = syphoon.parse_product(raw)
            if not parsed:
                results.append({"product_id": pid, "status": "not_found"})
                continue
            await intelligence.upsert_product(
                db, pid,
                product_name=parsed["product_name"],
                brand=parsed.get("brand"),
                image_url=parsed.get("image_url"),
            )
            await intelligence.save_snapshot(
                db, pid, req.zipcode,
                selling_price=parsed["selling_price"],
                mrp=parsed["mrp"],
                discount_percent=parsed["discount_percent"],
                in_stock=parsed["in_stock"],
            )
            results.append({"product_id": pid, "status": "tracked", "price": parsed["selling_price"]})
        except Exception as e:
            results.append({"product_id": pid, "status": "error", "error": str(e)})

    return {"success": True, "results": results}
