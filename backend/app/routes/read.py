import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from redis.exceptions import RedisError

from app.db import cursor
from app.config import get_settings
from app.dependencies import get_current_user, require_lender, require_admin
from app.schemas.models import ItemCreate, ItemUpdate
from app.redis_store import get_cached_items, set_cached_items, item_cache_key, invalidate_item_caches_safely

router = APIRouter()
logger=logging.getLogger("borrownear.items")
MAX_ITEM_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": (".jpg", b"\xff\xd8\xff"), "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
               "image/webp": (".webp", b"RIFF")}
DEFAULT_IMAGE_DIR = Path(__file__).resolve().parent.parent / "item_defaults"


def _default_image_name(item_name: str, category_name: str) -> str:
    name=item_name.lower()
    if "tent" in name: return "tent.svg"
    if "camera" in name: return "camera.svg"
    if "drill" in name: return "drill.svg"
    if "ladder" in name: return "ladder.svg"
    if "projector" in name: return "projector.svg"
    if "racket" in name or "badminton" in name: return "racket.svg"
    if "air fryer" in name: return "air-fryer.svg"
    if "raspberry" in name or "pi kit" in name: return "electronics.svg"
    if "book" in name or "clrs" in name or "database system concepts" in name: return "book.svg"
    category=category_name.lower()
    if "tool" in category: return "drill.svg"
    if "sport" in category or "outdoor" in category: return "tent.svg"
    if "book" in category: return "book.svg"
    if "kitchen" in category: return "air-fryer.svg"
    return "electronics.svg"

ITEM_SELECT = """SELECT i.item_id, i.owner_id, o.name AS owner_name,
 c.category_id, c.category_name, i.item_name, i.description,
 i.`condition` AS item_condition, i.estimated_value, i.deposit_amount,
 i.status, i.created_at, l.location_id, l.locality, l.city, l.pincode
 FROM items i JOIN users o ON o.user_id=i.owner_id
 JOIN categories c ON c.category_id=i.category_id
 JOIN locations l ON l.location_id=o.location_id"""


@router.get("/items")
def list_items(category_id: int | None = Query(None, gt=0), location_id: int | None = Query(None, gt=0),
               status: str | None = None, search: str | None = Query(None, max_length=100),
               sort_by: str = Query("created_at"), sort_order: str = Query("desc"),
               limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    clauses, params = [], []
    if category_id is not None:
        clauses.append("i.category_id=%s"); params.append(category_id)
    if location_id is not None:
        clauses.append("l.location_id=%s"); params.append(location_id)
    if status is not None:
        allowed = {"AVAILABLE", "RESERVED", "BORROWED", "UNAVAILABLE"}
        if status not in allowed:
            raise HTTPException(422, "Invalid item status")
        clauses.append("i.status=%s"); params.append(status)
    if search:
        clauses.append("(i.item_name LIKE %s OR i.description LIKE %s)")
        term = f"%{search}%"; params += [term, term]
    sort_columns={"created_at":"i.created_at","item_name":"i.item_name","estimated_value":"i.estimated_value"}
    if sort_by not in sort_columns: raise HTTPException(422,"Invalid sort_by field")
    if sort_order.lower() not in {"asc","desc"}: raise HTTPException(422,"sort_order must be asc or desc")
    direction=sort_order.upper()
    sql = ITEM_SELECT + (" WHERE " + " AND ".join(clauses) if clauses else "") + f" ORDER BY {sort_columns[sort_by]} {direction}, i.item_id LIMIT %s OFFSET %s"
    params += [limit, offset]
    cache_parts={"category_id":category_id,"location_id":location_id,"status":status,
                 "search":search,"sort_by":sort_by,"sort_order":direction,"limit":limit,"offset":offset}
    cache_key=item_cache_key(cache_parts)
    try:
        cached=get_cached_items(cache_key)
        if cached is not None:
            return cached
    except RedisError as exc:
        logger.info("Redis item cache read skipped (%s)",type(exc).__name__)
    with cursor() as (_, cur):
        cur.execute(sql, tuple(params)); rows = cur.fetchall()
    result={"items":jsonable_encoder(rows),"limit":limit,"offset":offset}
    try:
        set_cached_items(cache_key,result)
    except RedisError as exc:
        logger.info("Redis item cache write skipped (%s)",type(exc).__name__)
    return result


@router.get("/items/{item_id}")
def get_item(item_id: int):
    with cursor() as (_, cur):
        cur.execute(ITEM_SELECT + " WHERE i.item_id=%s", (item_id,)); row = cur.fetchone()
    if not row: raise HTTPException(404, "Item not found")
    return row


@router.get("/items/{item_id}/image")
def get_item_image(item_id: int):
    with cursor() as (_, cur):
        cur.execute("SELECT i.item_name,c.category_name FROM items i JOIN categories c ON c.category_id=i.category_id WHERE i.item_id=%s", (item_id,))
        item=cur.fetchone()
    if not item: raise HTTPException(404, "Item not found")
    image_dir=Path(get_settings().item_image_dir)
    for suffix, content_type in ((".jpg","image/jpeg"),(".png","image/png"),(".webp","image/webp")):
        uploaded=image_dir / f"{item_id}{suffix}"
        if uploaded.is_file():
            return FileResponse(uploaded, media_type=content_type, headers={"Cache-Control":"no-store"})
    fallback=DEFAULT_IMAGE_DIR / _default_image_name(item["item_name"],item["category_name"])
    return FileResponse(fallback, media_type="image/svg+xml", headers={"Cache-Control":"no-store"})


@router.post("/items/{item_id}/image", status_code=201)
async def upload_item_image(item_id: int, image: UploadFile = File(...), user=Depends(require_lender)):
    content_type=(image.content_type or "").lower()
    if content_type not in IMAGE_TYPES:
        raise HTTPException(415,"Use a JPEG, PNG, or WebP image")
    data=await image.read(MAX_ITEM_IMAGE_BYTES+1)
    if len(data)>MAX_ITEM_IMAGE_BYTES:
        raise HTTPException(413,"Image must be 5 MB or smaller")
    suffix,signature=IMAGE_TYPES[content_type]
    if not data.startswith(signature) or (content_type=="image/webp" and data[8:12]!=b"WEBP"):
        raise HTTPException(415,"The uploaded file does not match its image type")
    with cursor() as (conn,cur):
        cur.execute("SELECT owner_id FROM items WHERE item_id=%s",(item_id,)); item=cur.fetchone()
        if not item: raise HTTPException(404,"Item not found")
        if item["owner_id"]!=user["user_id"]: raise HTTPException(403,"Only the item owner can upload its image")
    image_dir=Path(get_settings().item_image_dir)
    image_dir.mkdir(parents=True,exist_ok=True)
    target=image_dir / f"{item_id}{suffix}"
    for old_suffix in (".jpg",".png",".webp"):
        old_image=image_dir / f"{item_id}{old_suffix}"
        if old_image!=target and old_image.exists(): old_image.unlink()
    target.write_bytes(data)
    return {"image_url":f"/api/v1/items/{item_id}/image"}


@router.get("/categories")
def categories():
    with cursor() as (_, cur):
        cur.execute("SELECT category_id, category_name, description FROM categories ORDER BY category_name")
        return cur.fetchall()


@router.get("/locations")
def locations():
    with cursor() as (_, cur):
        cur.execute("SELECT location_id, locality, city, pincode FROM locations ORDER BY city, locality")
        return cur.fetchall()


def public_user(user_id: int):
    with cursor() as (_, cur):
        cur.execute("""SELECT u.user_id,u.name,u.location_id,l.locality,l.city,u.trust_score,u.created_at
          FROM users u JOIN locations l ON l.location_id=u.location_id WHERE u.user_id=%s""", (user_id,))
        row = cur.fetchone()
    if not row: raise HTTPException(404, "User not found")
    return row


@router.get("/users/{user_id}")
def get_user(user_id: int):
    return public_user(user_id)


@router.get("/users/{user_id}/items")
def user_items(user_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    public_user(user_id)
    with cursor() as (_, cur):
        cur.execute(ITEM_SELECT + " WHERE i.owner_id=%s ORDER BY i.created_at DESC, i.item_id LIMIT %s OFFSET %s",
                    (user_id, limit, offset))
        return {"items": cur.fetchall(), "limit": limit, "offset": offset}


@router.get("/auth/me")
def my_profile(user=Depends(get_current_user)):
    return {**public_user(user["user_id"]), "role": user["role"]}


@router.post("/items", status_code=201)
def create_item(data: ItemCreate, user=Depends(require_lender)):
    if data.deposit_amount > data.estimated_value:
        raise HTTPException(422, "deposit_amount cannot exceed estimated_value")
    with cursor() as (conn, cur):
        cur.execute("SELECT category_id FROM categories WHERE category_id=%s", (data.category_id,))
        if not cur.fetchone(): raise HTTPException(422, "Unknown category")
        cur.execute("""INSERT INTO items(owner_id,category_id,item_name,description,`condition`,estimated_value,deposit_amount)
          VALUES(%s,%s,%s,%s,%s,%s,%s)""",
          (user["user_id"],data.category_id,data.item_name.strip(),data.description,data.condition,
           data.estimated_value,data.deposit_amount))
        item_id=cur.lastrowid
        conn.commit()
    invalidate_item_caches_safely()
    return get_item(item_id)


@router.patch("/items/{item_id}")
def update_item(item_id: int, data: ItemUpdate, user=Depends(require_lender)):
    changes=data.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422,"Provide at least one field to update")
    if any(value is None for key,value in changes.items() if key not in {"description","condition"}):
        raise HTTPException(422,"Required item fields cannot be null")
    allowed={"category_id","item_name","description","condition","estimated_value","deposit_amount","status"}
    if set(changes)-allowed: raise HTTPException(422,"Invalid item fields")
    columns={"category_id":"category_id","item_name":"item_name","description":"description",
             "condition":"`condition`","estimated_value":"estimated_value","deposit_amount":"deposit_amount","status":"status"}
    with cursor() as (conn,cur):
        cur.execute("SELECT owner_id,status,estimated_value,deposit_amount FROM items WHERE item_id=%s FOR UPDATE",(item_id,))
        item=cur.fetchone()
        if not item: raise HTTPException(404,"Item not found")
        if item["owner_id"]!=user["user_id"]: raise HTTPException(403,"Only the item owner can edit it")
        if item["status"] in ("RESERVED","BORROWED"):
            raise HTTPException(409,"Reserved or borrowed items cannot be edited")
        value=changes.get("estimated_value",item["estimated_value"])
        deposit=changes.get("deposit_amount",item["deposit_amount"])
        if deposit>value: raise HTTPException(422,"deposit_amount cannot exceed estimated_value")
        if "category_id" in changes:
            cur.execute("SELECT category_id FROM categories WHERE category_id=%s",(changes["category_id"],))
            if not cur.fetchone(): raise HTTPException(422,"Unknown category")
        assignments=", ".join(f"{columns[key]}=%s" for key in changes)
        cur.execute(f"UPDATE items SET {assignments} WHERE item_id=%s",(*changes.values(),item_id))
        conn.commit()
    invalidate_item_caches_safely()
    return get_item(item_id)


@router.delete("/items/{item_id}", status_code=200)
def deactivate_item(item_id:int,user=Depends(require_lender)):
    with cursor() as (conn,cur):
        cur.execute("SELECT owner_id,status FROM items WHERE item_id=%s FOR UPDATE",(item_id,)); item=cur.fetchone()
        if not item: raise HTTPException(404,"Item not found")
        if item["owner_id"]!=user["user_id"]: raise HTTPException(403,"Only the item owner can deactivate it")
        if item["status"] in ("RESERVED","BORROWED"):
            raise HTTPException(409,"Reserved or borrowed items cannot be deactivated")
        cur.execute("UPDATE items SET status='UNAVAILABLE' WHERE item_id=%s",(item_id,))
        conn.commit()
    invalidate_item_caches_safely()
    return {"item_id":item_id,"status":"UNAVAILABLE"}


@router.get("/analytics/categories")
def category_stats(user=Depends(require_admin)):
    with cursor() as (_, cur):
        cur.execute("""SELECT c.category_id,c.category_name,COUNT(DISTINCT i.item_id) AS item_count,
          COUNT(DISTINCT r.request_id) AS request_count,
          COUNT(DISTINCT CASE WHEN t.status IN ('ACTIVE','OVERDUE','RETURNED') THEN t.transaction_id END) AS borrow_count
          FROM categories c LEFT JOIN items i ON i.category_id=c.category_id
          LEFT JOIN borrow_requests r ON r.item_id=i.item_id
          LEFT JOIN borrow_transactions t ON t.request_id=r.request_id
          GROUP BY c.category_id,c.category_name
          HAVING COUNT(DISTINCT i.item_id) >= 0 ORDER BY borrow_count DESC, request_count DESC""")
        return cur.fetchall()


@router.get("/analytics/overdue")
def overdue_items(user=Depends(require_admin)):
    with cursor() as (_, cur):
        cur.execute("""SELECT t.transaction_id,i.item_name,o.name AS owner_name,b.name AS borrower_name,
          t.due_date,DATEDIFF(CURRENT_DATE,t.due_date) AS days_overdue
          FROM borrow_transactions t JOIN borrow_requests r ON r.request_id=t.request_id
          JOIN items i ON i.item_id=r.item_id JOIN users o ON o.user_id=i.owner_id
          JOIN users b ON b.user_id=r.borrower_id
          WHERE t.status IN ('ACTIVE','OVERDUE') AND t.due_date<CURRENT_DATE
          ORDER BY t.due_date""")
        return cur.fetchall()


@router.get("/items/{item_id}/reviews")
def item_reviews(item_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    with cursor() as (_, cur):
        cur.execute("SELECT item_id FROM items WHERE item_id=%s", (item_id,))
        if not cur.fetchone(): raise HTTPException(404, "Item not found")
        cur.execute("""SELECT rv.review_id,rv.transaction_id,rv.reviewer_id,u.name AS reviewer_name,
          rv.rating,rv.comment,rv.review_date FROM reviews rv JOIN borrow_transactions t ON t.transaction_id=rv.transaction_id
          JOIN borrow_requests r ON r.request_id=t.request_id JOIN users u ON u.user_id=rv.reviewer_id
          WHERE r.item_id=%s ORDER BY rv.review_date DESC LIMIT %s OFFSET %s""", (item_id,limit,offset))
        return {"reviews":cur.fetchall(),"limit":limit,"offset":offset}
