from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database import get_db, TrackedProduct, PriceSnapshot
from services import syphoon, intelligence
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/products", tags=["products"])


class AddProductRequest(BaseModel):
    product_id: str
    zipcode: str
    product_name: Optional[str] = None


class RemoveProductRequest(BaseModel):
    product_id: str


# ── Live fetch (no DB write) ────────────────────────────────────────────────────
@router.get("/fetch")
async def fetch_product_live(
    product_id: str = Query(...),
    zipcode:    str = Query(...)
):
    """Fetch live product data from Syphoon without saving to DB."""
    try:
        raw    = await syphoon.fetch_product(product_id, zipcode)
        parsed = syphoon.parse_product(raw)
        if not parsed:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"success": True, "data": parsed}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Track a product (save to DB + take first snapshot) ─────────────────────────
@router.post("/track")
async def track_product(req: AddProductRequest, db: AsyncSession = Depends(get_db)):
    """Add a product to tracking and take an immediate snapshot."""
    try:
        raw    = await syphoon.fetch_product(req.product_id, req.zipcode)
        parsed = syphoon.parse_product(raw)
        if not parsed:
            raise HTTPException(status_code=404, detail="Product not found via Syphoon")

        product_name = req.product_name or parsed["product_name"] or req.product_id

        await intelligence.upsert_product(
            db,
            product_id=req.product_id,
            product_name=product_name,
            brand=parsed.get("brand"),
            image_url=parsed.get("image_url"),
        )
        await intelligence.upsert_zipcode(db, req.zipcode)
        await intelligence.save_snapshot(
            db,
            product_id=req.product_id,
            zipcode=req.zipcode,
            selling_price=parsed["selling_price"],
            mrp=parsed["mrp"],
            discount_percent=parsed["discount_percent"],
            in_stock=parsed["in_stock"],
            raw_response=raw,
        )

        return {"success": True, "message": f"Now tracking {product_name}", "data": parsed}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Untrack ─────────────────────────────────────────────────────────────────────
@router.post("/untrack")
async def untrack_product(req: RemoveProductRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TrackedProduct).where(TrackedProduct.product_id == req.product_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Product not being tracked")
    obj.is_active = False
    await db.commit()
    return {"success": True, "message": "Product removed from tracking"}


# ── List all tracked products ───────────────────────────────────────────────────
@router.get("/tracked")
async def list_tracked(db: AsyncSession = Depends(get_db)):
    products = await intelligence.get_all_tracked_products(db)
    return {"success": True, "data": [
        {
            "product_id":   p.product_id,
            "product_name": p.product_name,
            "brand":        p.brand,
            "image_url":    p.image_url,
            "created_at":   p.created_at.isoformat(),
        }
        for p in products
    ]}


# ── Price history ────────────────────────────────────────────────────────────────
@router.get("/history")
async def price_history(
    product_id: str = Query(...),
    zipcode:    str = Query(...),
    limit:      int = Query(30, le=200),
    db: AsyncSession = Depends(get_db)
):
    snapshots = await intelligence.get_price_history(db, product_id, zipcode, limit)
    return {"success": True, "data": [
        {
            "selling_price":    float(s.selling_price) if s.selling_price else None,
            "mrp":              float(s.mrp) if s.mrp else None,
            "discount_percent": float(s.discount_percent) if s.discount_percent else None,
            "in_stock":         s.in_stock,
            "snapshotted_at":   s.snapshotted_at.isoformat(),
        }
        for s in snapshots
    ]}
