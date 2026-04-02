from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import AsyncSessionLocal
from services import syphoon, intelligence
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def run_scheduled_tracking():
    """Called by scheduler every N minutes. Tracks all active products × zipcodes."""
    logger.info("Scheduled tracking run started")
    async with AsyncSessionLocal() as db:
        products = await intelligence.get_all_tracked_products(db)
        zipcodes = await intelligence.get_all_tracked_zipcodes(db)

        if not products or not zipcodes:
            logger.info("No tracked products or zipcodes, skipping.")
            return

        for product in products:
            for zipcode in zipcodes:
                try:
                    raw = await syphoon.fetch_product(product.product_id, zipcode.zipcode)
                    parsed = syphoon.parse_product(raw)
                    if not parsed:
                        continue
                    await intelligence.save_snapshot(
                        db,
                        product_id=product.product_id,
                        zipcode=zipcode.zipcode,
                        selling_price=parsed["selling_price"],
                        mrp=parsed["mrp"],
                        discount_percent=parsed["discount_percent"],
                        in_stock=parsed["in_stock"],
                        raw_response=None,  # skip storing raw for scheduled runs
                    )
                    logger.info(f"Tracked {product.product_id} @ {zipcode.zipcode}: ₹{parsed['selling_price']}")
                except Exception as e:
                    logger.error(f"Failed tracking {product.product_id} @ {zipcode.zipcode}: {e}")

    logger.info("Scheduled tracking run complete")


def start_scheduler(interval_minutes: int = 60):
    scheduler.add_job(
        run_scheduled_tracking,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="price_tracker",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started — tracking every {interval_minutes} minutes")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
