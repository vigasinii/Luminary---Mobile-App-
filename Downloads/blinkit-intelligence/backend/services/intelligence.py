from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database import TrackedProduct, TrackedZipcode, PriceSnapshot, PriceAlert, AvailabilitySnapshot
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


async def upsert_product(db: AsyncSession, product_id: str, product_name: str,
                          brand: Optional[str] = None, category: Optional[str] = None,
                          image_url: Optional[str] = None) -> TrackedProduct:
    result = await db.execute(select(TrackedProduct).where(TrackedProduct.product_id == product_id))
    obj = result.scalar_one_or_none()
    if obj:
        if product_name: obj.product_name = product_name
        if brand:        obj.brand = brand
        if category:     obj.category = category
        if image_url:    obj.image_url = image_url
    else:
        obj = TrackedProduct(
            product_id=product_id,
            product_name=product_name,
            brand=brand,
            category=category,
            image_url=image_url
        )
        db.add(obj)
    await db.commit()
    return obj


async def upsert_zipcode(db: AsyncSession, zipcode: str) -> TrackedZipcode:
    result = await db.execute(select(TrackedZipcode).where(TrackedZipcode.zipcode == zipcode))
    obj = result.scalar_one_or_none()
    if not obj:
        obj = TrackedZipcode(zipcode=zipcode)
        db.add(obj)
        await db.commit()
    return obj


async def save_snapshot(db: AsyncSession, product_id: str, zipcode: str,
                         selling_price: Optional[float], mrp: Optional[float],
                         discount_percent: Optional[float], in_stock: bool,
                         raw_response: Optional[dict] = None) -> PriceSnapshot:
    # Check for price change alert
    await _check_and_create_alert(db, product_id, zipcode, selling_price, in_stock)

    snap = PriceSnapshot(
        product_id=product_id,
        zipcode=zipcode,
        selling_price=selling_price,
        mrp=mrp,
        discount_percent=discount_percent,
        in_stock=in_stock,
        raw_response=raw_response,
    )
    db.add(snap)

    # Save availability snapshot
    avail = AvailabilitySnapshot(product_id=product_id, zipcode=zipcode, in_stock=in_stock)
    db.add(avail)

    await db.commit()
    return snap


async def _check_and_create_alert(db: AsyncSession, product_id: str, zipcode: str,
                                    new_price: Optional[float], new_in_stock: bool):
    """Compare with last snapshot and fire alerts on changes."""
    result = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.product_id == product_id, PriceSnapshot.zipcode == zipcode)
        .order_by(desc(PriceSnapshot.snapshotted_at))
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if not last:
        return

    alerts = []

    # Stock change
    if last.in_stock and not new_in_stock:
        alerts.append(PriceAlert(
            product_id=product_id, zipcode=zipcode,
            old_price=last.selling_price, new_price=new_price,
            alert_type="out_of_stock"
        ))
    elif not last.in_stock and new_in_stock:
        alerts.append(PriceAlert(
            product_id=product_id, zipcode=zipcode,
            old_price=last.selling_price, new_price=new_price,
            alert_type="back_in_stock"
        ))

    # Price change (>1% threshold)
    if last.selling_price and new_price:
        change_pct = ((new_price - float(last.selling_price)) / float(last.selling_price)) * 100
        if abs(change_pct) > 1:
            alerts.append(PriceAlert(
                product_id=product_id, zipcode=zipcode,
                old_price=last.selling_price, new_price=new_price,
                change_percent=round(change_pct, 2),
                alert_type="price_drop" if change_pct < 0 else "price_increase"
            ))

    for a in alerts:
        db.add(a)
        logger.info(f"Alert: {a.alert_type} for {product_id} @ {zipcode}")


async def get_price_history(db: AsyncSession, product_id: str, zipcode: str, limit: int = 30):
    result = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.product_id == product_id, PriceSnapshot.zipcode == zipcode)
        .order_by(desc(PriceSnapshot.snapshotted_at))
        .limit(limit)
    )
    return result.scalars().all()


async def get_all_tracked_products(db: AsyncSession):
    result = await db.execute(
        select(TrackedProduct).where(TrackedProduct.is_active == True)
    )
    return result.scalars().all()


async def get_all_tracked_zipcodes(db: AsyncSession):
    result = await db.execute(
        select(TrackedZipcode).where(TrackedZipcode.is_active == True)
    )
    return result.scalars().all()


async def get_recent_alerts(db: AsyncSession, limit: int = 50):
    result = await db.execute(
        select(PriceAlert).order_by(desc(PriceAlert.triggered_at)).limit(limit)
    )
    return result.scalars().all()
