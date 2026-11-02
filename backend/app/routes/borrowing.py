from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from mysql.connector import IntegrityError

from app.db import cursor
from app.dependencies import get_current_user, require_admin
from app.schemas.models import RequestIn, DecisionIn, HandoverIn, ReturnIn, ReviewIn
from app.redis_store import invalidate_item_caches_safely

router = APIRouter()


@router.post("/requests", status_code=201)
def create_request(data: RequestIn, user=Depends(get_current_user)):
    if data.end_date <= data.start_date: raise HTTPException(422, "end_date must be after start_date")
    if data.start_date < date.today(): raise HTTPException(422, "start_date cannot be in the past")
    try:
        with cursor() as (conn, cur):
            cur.execute("SELECT owner_id,status FROM items WHERE item_id=%s FOR UPDATE", (data.item_id,)); item=cur.fetchone()
            if not item: raise HTTPException(404, "Item not found")
            if item["owner_id"] == user["user_id"]: raise HTTPException(409, "You cannot request your own item")
            if item["status"] != "AVAILABLE": raise HTTPException(409, "Item is not available")
            cur.execute("INSERT INTO borrow_requests(item_id,borrower_id,start_date,end_date) VALUES(%s,%s,%s,%s)",
                        (data.item_id,user["user_id"],data.start_date,data.end_date))
            request_id=cur.lastrowid; conn.commit()
            return {"request_id":request_id,"status":"PENDING"}
    except IntegrityError as exc:
        if exc.errno == 1062: raise HTTPException(409,"A pending request for this item already exists") from None
        raise


@router.get("/requests")
def my_requests(user=Depends(get_current_user), limit:int=Query(50,ge=1,le=100), offset:int=Query(0,ge=0)):
    with cursor() as (_,cur):
        cur.execute("""SELECT r.request_id,r.item_id,i.item_name,i.owner_id,o.name AS owner_name,
          r.start_date,r.end_date,r.request_date,r.status FROM borrow_requests r JOIN items i ON i.item_id=r.item_id
          JOIN users o ON o.user_id=i.owner_id WHERE r.borrower_id=%s ORDER BY r.request_date DESC LIMIT %s OFFSET %s""",
                    (user["user_id"],limit,offset)); return cur.fetchall()


@router.get("/owner/requests")
def incoming_requests(user=Depends(get_current_user), limit:int=Query(50,ge=1,le=100), offset:int=Query(0,ge=0)):
    with cursor() as (_,cur):
        cur.execute("""SELECT r.request_id,r.item_id,i.item_name,r.borrower_id,b.name AS borrower_name,
          r.start_date,r.end_date,r.request_date,r.status FROM borrow_requests r JOIN items i ON i.item_id=r.item_id
          JOIN users b ON b.user_id=r.borrower_id WHERE i.owner_id=%s ORDER BY r.request_date DESC LIMIT %s OFFSET %s""",
                    (user["user_id"],limit,offset)); return cur.fetchall()


@router.patch("/requests/{request_id}")
def decide_request(request_id:int, data:DecisionIn, user=Depends(get_current_user)):
    with cursor() as (conn,cur):
        cur.execute("SELECT r.*,i.owner_id,i.status AS item_status FROM borrow_requests r JOIN items i ON i.item_id=r.item_id WHERE r.request_id=%s FOR UPDATE",(request_id,)); r=cur.fetchone()
        if not r: raise HTTPException(404,"Request not found")
        if r["owner_id"] != user["user_id"]: raise HTTPException(403,"Only the item owner can decide")
        if r["status"] != "PENDING": raise HTTPException(409,"Only pending requests can be decided")
        if data.decision == "APPROVED":
            cur.execute("SELECT request_id FROM borrow_requests WHERE item_id=%s AND status='APPROVED' AND start_date<=%s AND end_date>=%s AND request_id<>%s FOR UPDATE",
                        (r["item_id"],r["end_date"],r["start_date"],request_id))
            if cur.fetchone(): raise HTTPException(409,"Dates overlap another approved request")
            if r["item_status"] != "AVAILABLE": raise HTTPException(409,"Item is not available")
            cur.execute("UPDATE items SET status='RESERVED' WHERE item_id=%s",(r["item_id"],))
        cur.execute("UPDATE borrow_requests SET status=%s WHERE request_id=%s",(data.decision,request_id))
        conn.commit()
    invalidate_item_caches_safely()
    return {"request_id":request_id,"status":data.decision}


@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id:int,user=Depends(get_current_user)):
    with cursor() as (conn,cur):
        cur.execute("SELECT r.item_id,r.borrower_id,r.status,i.status AS item_status FROM borrow_requests r JOIN items i ON i.item_id=r.item_id WHERE r.request_id=%s FOR UPDATE",(request_id,)); r=cur.fetchone()
        if not r: raise HTTPException(404,"Request not found")
        if r["borrower_id"]!=user["user_id"]: raise HTTPException(403,"Only the requesting borrower can cancel")
        if r["status"] not in ("PENDING","APPROVED"): raise HTTPException(409,"Request cannot be cancelled in its current state")
        cur.execute("SELECT transaction_id FROM borrow_transactions WHERE request_id=%s",(request_id,))
        if cur.fetchone(): raise HTTPException(409,"A handed-over transaction cannot be cancelled")
        cur.execute("UPDATE borrow_requests SET status='CANCELLED' WHERE request_id=%s",(request_id,))
        if r["status"]=="APPROVED":
            cur.execute("UPDATE items SET status='AVAILABLE' WHERE item_id=%s AND status='RESERVED'",(r["item_id"],))
        conn.commit()
    invalidate_item_caches_safely()
    return {"request_id":request_id,"status":"CANCELLED"}


@router.post("/requests/{request_id}/handover",status_code=201)
def handover(request_id:int,data:HandoverIn,user=Depends(get_current_user)):
    if data.due_date < data.borrow_date: raise HTTPException(422,"due_date cannot be before borrow_date")
    with cursor() as (conn,cur):
        cur.execute("SELECT r.*,i.owner_id FROM borrow_requests r JOIN items i ON i.item_id=r.item_id WHERE r.request_id=%s FOR UPDATE",(request_id,)); r=cur.fetchone()
        if not r: raise HTTPException(404,"Request not found")
        if user["user_id"] != r["owner_id"]: raise HTTPException(403,"Only the owner can record handover")
        if r["status"] != "APPROVED": raise HTTPException(409,"Request must be approved")
        if data.borrow_date != r["start_date"] or data.due_date != r["end_date"]: raise HTTPException(422,"Handover dates must match the approved request")
        cur.execute("INSERT INTO borrow_transactions(request_id,borrow_date,due_date,condition_before) VALUES(%s,%s,%s,%s)",
                    (request_id,data.borrow_date,data.due_date,data.condition_before))
        tid=cur.lastrowid; cur.execute("UPDATE items SET status='BORROWED' WHERE item_id=%s",(r["item_id"],)); conn.commit()
    invalidate_item_caches_safely()
    return {"transaction_id":tid,"status":"ACTIVE"}


@router.post("/transactions/{transaction_id}/return")
def return_item(transaction_id:int,data:ReturnIn,user=Depends(get_current_user)):
    with cursor() as (conn,cur):
        cur.execute("""SELECT t.*,r.borrower_id,i.owner_id,i.item_id FROM borrow_transactions t JOIN borrow_requests r ON r.request_id=t.request_id
          JOIN items i ON i.item_id=r.item_id WHERE t.transaction_id=%s FOR UPDATE""",(transaction_id,)); t=cur.fetchone()
        if not t: raise HTTPException(404,"Transaction not found")
        if user["user_id"] not in (t["owner_id"],t["borrower_id"]): raise HTTPException(403,"Only transaction participants can record return")
        if t["status"] not in ("ACTIVE","OVERDUE"): raise HTTPException(409,"Transaction is not active")
        if data.return_date < t["borrow_date"]: raise HTTPException(422,"Return date cannot precede borrow date")
        cur.execute("UPDATE borrow_transactions SET status='RETURNED',return_date=%s,condition_after=%s WHERE transaction_id=%s",
                    (data.return_date,data.condition_after,transaction_id))
        cur.execute("UPDATE items SET status='AVAILABLE' WHERE item_id=%s",(t["item_id"],)); conn.commit()
    invalidate_item_caches_safely()
    return {"transaction_id":transaction_id,"status":"RETURNED","return_date":data.return_date}


@router.post("/transactions/{transaction_id}/reviews",status_code=201)
def create_review(transaction_id:int,data:ReviewIn,user=Depends(get_current_user)):
    try:
        with cursor() as (conn,cur):
            cur.execute("""SELECT t.status,r.borrower_id,i.owner_id FROM borrow_transactions t
              JOIN borrow_requests r ON r.request_id=t.request_id JOIN items i ON i.item_id=r.item_id
              WHERE t.transaction_id=%s FOR UPDATE""",(transaction_id,)); t=cur.fetchone()
            if not t: raise HTTPException(404,"Transaction not found")
            if t["status"]!="RETURNED": raise HTTPException(409,"Reviews require a returned transaction")
            if user["user_id"] not in (t["borrower_id"],t["owner_id"]): raise HTTPException(403,"Only transaction participants can review")
            cur.execute("INSERT INTO reviews(transaction_id,reviewer_id,rating,comment) VALUES(%s,%s,%s,%s)",
                        (transaction_id,user["user_id"],data.rating,data.comment))
            cur.execute("""UPDATE users SET trust_score=COALESCE((SELECT ROUND(AVG(x.rating),2) FROM
              (SELECT rv.rating,IF(rv.reviewer_id=br.borrower_id,it.owner_id,br.borrower_id) AS reviewee_id
               FROM reviews rv JOIN borrow_transactions bt ON bt.transaction_id=rv.transaction_id
               JOIN borrow_requests br ON br.request_id=bt.request_id JOIN items it ON it.item_id=br.item_id) x
              WHERE x.reviewee_id=users.user_id),0) WHERE user_id=%s""",
                        (t["owner_id"] if user["user_id"]==t["borrower_id"] else t["borrower_id"],))
            review_id=cur.lastrowid; conn.commit()
            return {"review_id":review_id,"transaction_id":transaction_id,"rating":data.rating}
    except IntegrityError as exc:
        if exc.errno==1062: raise HTTPException(409,"You have already reviewed this transaction") from None
        raise


@router.get("/transactions")
def history(user=Depends(get_current_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    with cursor() as (_,cur):
        cur.execute("""SELECT t.transaction_id,t.status,t.borrow_date,t.due_date,t.return_date,i.item_name,
          o.name AS owner_name,b.name AS borrower_name FROM borrow_transactions t
          JOIN borrow_requests r ON r.request_id=t.request_id JOIN items i ON i.item_id=r.item_id
          JOIN users o ON o.user_id=i.owner_id JOIN users b ON b.user_id=r.borrower_id
          WHERE i.owner_id=%s OR r.borrower_id=%s ORDER BY t.borrow_date DESC LIMIT %s OFFSET %s""",
                    (user["user_id"],user["user_id"],limit,offset)); return cur.fetchall()


@router.get("/admin/stats")
def admin_stats(user=Depends(require_admin)):
    with cursor() as (_,cur):
        cur.execute("""SELECT (SELECT COUNT(*) FROM users) AS users,
          (SELECT COUNT(*) FROM items) AS items,
          (SELECT COUNT(*) FROM borrow_requests) AS requests,
          (SELECT COUNT(*) FROM borrow_transactions WHERE status IN ('ACTIVE','OVERDUE')) AS active_borrows,
          (SELECT COUNT(*) FROM borrow_transactions WHERE status='OVERDUE' OR (status='ACTIVE' AND due_date<CURRENT_DATE)) AS overdue""")
        return cur.fetchone()
