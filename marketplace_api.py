from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import database as db

router = APIRouter(tags=["marketplace"])
BASE = Path(__file__).parent


class ListingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    price: float | None = Field(default=None, ge=0)
    category_id: int | None = None
    category: str = Field(default="", max_length=100)
    seller_name: str = Field(min_length=1, max_length=120)
    seller_contact: str = Field(min_length=1, max_length=200)
    city: str = Field(default="", max_length=100)
    image_url: str = Field(default="", max_length=1000)


def _category_id(c: ListingCreate):
    if c.category_id is not None:
        return c.category_id
    if not c.category.strip():
        return None
    with db.get_connection() as conn:
        row = db._fetchone(conn, "SELECT id FROM marketplace_categories WHERE name=? OR slug=?", (c.category.strip(), c.category.strip().lower()))
        return row["id"] if row else None


def _listing(row):
    item = dict(row)
    if item.get("price") is not None:
        item["price"] = float(item["price"])
    return item


@router.get("/marketplace")
def marketplace_page():
    return FileResponse(BASE / "web" / "marketplace" / "index.html")


@router.get("/marketplace/style.css")
def marketplace_css():
    return FileResponse(BASE / "web" / "marketplace" / "style.css", media_type="text/css")


@router.get("/marketplace/app.js")
def marketplace_js():
    return FileResponse(BASE / "web" / "marketplace" / "app.js", media_type="application/javascript")


@router.get("/api/marketplace/categories")
def categories():
    with db.get_connection() as conn:
        rows = db._fetchall(conn, "SELECT id,name,slug FROM marketplace_categories ORDER BY id")
        return [dict(r) for r in rows]


@router.get("/api/marketplace/listings")
def listings(
    q: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=100),
    city: str = Query(default="", max_length=100),
    sort: str = Query(default="new", pattern="^(new|cheap|expensive)$"),
    limit: int = Query(default=50, ge=1, le=100),
):
    conditions = ["l.status='active'"]
    params = []
    if q.strip():
        conditions.append("(l.title ILIKE ? OR COALESCE(l.description,'') ILIKE ? OR COALESCE(l.city,'') ILIKE ?)")
        needle = f"%{q.strip()}%"
        params.extend([needle, needle, needle])
    if category.strip() and category.strip() != "Все":
        conditions.append("c.name=?")
        params.append(category.strip())
    if city.strip():
        conditions.append("l.city ILIKE ?")
        params.append(f"%{city.strip()}%")
    order = "l.created_at DESC"
    if sort == "cheap":
        order = "l.price ASC NULLS LAST, l.created_at DESC"
    elif sort == "expensive":
        order = "l.price DESC NULLS LAST, l.created_at DESC"
    sql = f"""
        SELECT l.id,l.title,l.description,l.price,l.category_id,c.name AS category,
               l.seller_name,l.seller_contact,l.city,l.image_url,l.views,l.created_at
        FROM marketplace_listings l
        LEFT JOIN marketplace_categories c ON c.id=l.category_id
        WHERE {' AND '.join(conditions)}
        ORDER BY {order}
        LIMIT ?
    """
    params.append(limit)
    with db.get_connection() as conn:
        rows = db._fetchall(conn, sql, tuple(params))
        return [_listing(r) for r in rows]


@router.get("/api/marketplace/listings/{listing_id}")
def listing_detail(listing_id: int):
    with db.get_connection() as conn:
        row = db._fetchone(conn, """
            SELECT l.id,l.title,l.description,l.price,l.category_id,c.name AS category,
                   l.seller_name,l.seller_contact,l.city,l.image_url,l.views,l.created_at
            FROM marketplace_listings l
            LEFT JOIN marketplace_categories c ON c.id=l.category_id
            WHERE l.id=? AND l.status='active'
        """, (listing_id,))
        if not row:
            raise HTTPException(404, "Объявление не найдено")
        db._execute(conn, "UPDATE marketplace_listings SET views=views+1,updated_at=NOW() WHERE id=?", (listing_id,))
        return _listing(row)


@router.post("/api/marketplace/listings")
def create_listing(item: ListingCreate):
    title = item.title.strip()
    seller = item.seller_name.strip()
    contact = item.seller_contact.strip()
    if not title or not seller or not contact:
        raise HTTPException(400, "Заполните обязательные поля")
    category_id = _category_id(item)
    with db.get_connection() as conn:
        listing_id = db._insert_id(conn, """
            INSERT INTO marketplace_listings
                (title,description,price,category_id,seller_name,seller_contact,city,image_url,status)
            VALUES (?,?,?,?,?,?,?,?, 'active')
        """, (
            title, item.description.strip(), item.price, category_id, seller,
            contact, item.city.strip(), item.image_url.strip()
        ))
        return {"ok": True, "id": listing_id}
