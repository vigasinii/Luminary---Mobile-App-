from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, Boolean, DateTime, Text, ForeignKey, JSON, text
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
from config import settings

# Convert postgres:// or postgresql:// to postgresql+asyncpg://
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Strip channel_binding param (not supported by asyncpg)
if "channel_binding=require" in db_url:
    db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "")

engine = create_async_engine(db_url, echo=False, pool_size=5, max_overflow=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class TrackedProduct(Base):
    __tablename__ = "tracked_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    product_name: Mapped[Optional[str]] = mapped_column(Text)
    brand: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(255))
    cat_id: Mapped[Optional[str]] = mapped_column(String(100))
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    snapshots: Mapped[List["PriceSnapshot"]] = relationship(back_populates="product", lazy="selectin")


class TrackedZipcode(Base):
    __tablename__ = "tracked_zipcodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    zipcode: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(String, ForeignKey("tracked_products.product_id"), nullable=False)
    zipcode: Mapped[str] = mapped_column(String(20), nullable=False)
    selling_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    mrp: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    discount_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    unit_type: Mapped[Optional[str]] = mapped_column(String(50))
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    variant_id: Mapped[Optional[str]] = mapped_column(String(100))
    variant_name: Mapped[Optional[str]] = mapped_column(String(255))
    snapshotted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON)

    product: Mapped["TrackedProduct"] = relationship(back_populates="snapshots")


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    zipcode: Mapped[str] = mapped_column(String(20), nullable=False)
    old_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    new_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    change_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    alert_type: Mapped[str] = mapped_column(String(50))  # price_drop, price_increase, back_in_stock, out_of_stock
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notified: Mapped[bool] = mapped_column(Boolean, default=False)


class AvailabilitySnapshot(Base):
    __tablename__ = "availability_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    zipcode: Mapped[str] = mapped_column(String(20), nullable=False)
    in_stock: Mapped[bool] = mapped_column(Boolean)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create indexes
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_price_snapshots_product_zip "
            "ON price_snapshots(product_id, zipcode)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_price_snapshots_time "
            "ON price_snapshots(snapshotted_at DESC)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_avail_product_zip "
            "ON availability_snapshots(product_id, zipcode)"
        ))
