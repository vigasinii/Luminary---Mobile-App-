from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db, TrackedZipcode
from services.intelligence import get_recent_alerts, upsert_zipcode, get_all_tracked_zipcodes
from pydantic import BaseModel

router = APIRouter(tags=["alerts & zipcodes"])


@router.get("/alerts")
async def list_alerts(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db)
):
    alerts = await get_recent_alerts(db, limit)
    return {"success": True, "data": [
        {
            "id":             a.id,
            "product_id":     a.product_id,
            "zipcode":        a.zipcode,
            "old_price":      float(a.old_price) if a.old_price else None,
            "new_price":      float(a.new_price) if a.new_price else None,
            "change_percent": float(a.change_percent) if a.change_percent else None,
            "alert_type":     a.alert_type,
            "triggered_at":   a.triggered_at.isoformat(),
            "notified":       a.notified,
        }
        for a in alerts
    ]}


class AddZipcodeRequest(BaseModel):
    zipcode: str
    city:    str | None = None
    state:   str | None = None


@router.post("/zipcodes")
async def add_zipcode(req: AddZipcodeRequest, db: AsyncSession = Depends(get_db)):
    obj = await upsert_zipcode(db, req.zipcode)
    if req.city:  obj.city  = req.city
    if req.state: obj.state = req.state
    await db.commit()
    return {"success": True, "zipcode": req.zipcode}


@router.get("/zipcodes")
async def list_zipcodes(db: AsyncSession = Depends(get_db)):
    zipcodes = await get_all_tracked_zipcodes(db)
    return {"success": True, "data": [
        {"zipcode": z.zipcode, "city": z.city, "state": z.state}
        for z in zipcodes
    ]}


@router.delete("/zipcodes/{zipcode}")
async def remove_zipcode(zipcode: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TrackedZipcode).where(TrackedZipcode.zipcode == zipcode))
    obj = result.scalar_one_or_none()
    if obj:
        obj.is_active = False
        await db.commit()
    return {"success": True}
