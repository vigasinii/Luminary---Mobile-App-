import httpx
from typing import Optional
from config import settings


BLINKIT_URL = "https://www.blinkit.com"


async def _post(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            settings.SYPHOON_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        r.raise_for_status()
        return r.json()


async def fetch_product(product_id: str, zipcode: str) -> dict:
    return await _post({
        "key":        settings.SYPHOON_PRODUCT_KEY,
        "url":        BLINKIT_URL,
        "method":     "GET",
        "zipcode":    zipcode,
        "product_id": product_id,
    })


async def fetch_category(cat_id: str, zipcode: str, next_page_url: Optional[str] = None) -> dict:
    body = {
        "key":     settings.SYPHOON_CATEGORY_KEY,
        "url":     BLINKIT_URL,
        "method":  "GET",
        "zipcode": zipcode,
        "cat_id":  cat_id,
    }
    if next_page_url:
        body["next_page_url"] = next_page_url
    return await _post(body)


async def fetch_keyword(keyword: str, zipcode: str,
                        next_page_url: Optional[str] = None,
                        next_page_payload: Optional[dict] = None) -> dict:
    body = {
        "key":     settings.SYPHOON_KEYWORD_KEY,
        "url":     BLINKIT_URL,
        "method":  "GET",
        "zipcode": zipcode,
        "keyword": keyword,
    }
    if next_page_url:
        body["next_page_url"] = next_page_url
    if next_page_payload:
        body["next_page_payload"] = next_page_payload
    return await _post(body)


def parse_product(raw: dict) -> Optional[dict]:
    """Extract normalized product dict from any Syphoon response shape."""
    p = (
        raw.get("data", {}).get("product") or
        raw.get("product") or
        raw.get("data", {}).get("response", {}).get("product") or
        raw.get("data")
    )
    if not p or not (p.get("name") or p.get("product_name")):
        return None

    price_obj = p.get("price") or {}
    mrp = _float(p.get("mrp") or price_obj.get("mrp"))
    sp  = _float(
        price_obj.get("sale_price") or
        price_obj.get("selling_price") or
        p.get("selling_price") or
        p.get("mrp")
    )
    disc = round(((mrp - sp) / mrp) * 100, 2) if mrp and sp and mrp > 0 else None

    return {
        "product_id":   str(p.get("product_id") or p.get("id") or ""),
        "product_name": p.get("name") or p.get("product_name"),
        "brand":        p.get("brand") or p.get("brand_name"),
        "category":     p.get("category"),
        "image_url":    (p.get("images") or [None])[0] or p.get("image_url") or p.get("thumbnail"),
        "mrp":          mrp,
        "selling_price": sp,
        "discount_percent": disc,
        "in_stock":     p.get("in_stock", True),
        "variants":     p.get("variants") or [],
        "raw":          raw,
    }


def extract_listing_products(raw: dict) -> list[dict]:
    """Extract list of products from category/search response."""
    products = []
    widgets = (
        raw.get("data", {}).get("response", {}).get("response", {}).get("objects") or
        raw.get("data", {}).get("response", {}).get("objects") or
        []
    )
    for w in widgets:
        items = w.get("data", {}).get("objects") or w.get("data", {}).get("items") or []
        for item in items:
            p = item.get("data", {}).get("product") or item.get("data") or item
            pid = p.get("product_id") or p.get("id")
            if not pid:
                continue
            price_obj = p.get("price") or {}
            mrp = _float(p.get("mrp") or price_obj.get("mrp"))
            sp  = _float(
                price_obj.get("sale_price") or
                price_obj.get("selling_price") or
                p.get("selling_price") or
                p.get("mrp")
            )
            disc = round(((mrp - sp) / mrp) * 100, 2) if mrp and sp and mrp > 0 else None
            products.append({
                "product_id":   str(pid),
                "product_name": p.get("name") or p.get("product_name"),
                "brand":        p.get("brand") or p.get("brand_name"),
                "image_url":    (p.get("images") or [None])[0] or p.get("image_url"),
                "mrp":          mrp,
                "selling_price": sp,
                "discount_percent": disc,
                "in_stock":     p.get("in_stock", True),
            })
    return products


def get_pagination(raw: dict) -> tuple[Optional[str], Optional[dict]]:
    """Returns (next_url, next_payload)."""
    pagination = (
        raw.get("data", {}).get("response", {}).get("response", {}).get("pagination") or {}
    )
    next_url     = pagination.get("next_url")
    next_payload = raw.get("data", {}).get("response", {}).get("postback_params")
    return next_url, next_payload


def _float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None
