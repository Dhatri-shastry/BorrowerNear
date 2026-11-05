from fastapi import APIRouter, HTTPException, status
from mysql.connector import IntegrityError

from app.db import cursor
from app.schemas.models import RegisterIn, LoginIn, RoleIn
from app.security import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user
from fastapi import Depends

router = APIRouter()


@router.post("/auth/register", status_code=201)
def register(data: RegisterIn):
    try:
        with cursor() as (conn, cur):
            cur.execute("SELECT location_id FROM locations WHERE location_id=%s", (data.location_id,))
            if not cur.fetchone(): raise HTTPException(422, "Unknown location")
            cur.execute("INSERT INTO users(name,email,phone,password_hash,location_id,role) VALUES(%s,%s,%s,%s,%s,%s)",
                        (data.name, data.email.lower(), data.phone, hash_password(data.password), data.location_id, data.role))
            user_id = cur.lastrowid
            conn.commit()
            return {"user_id": user_id, "name": data.name, "email": data.email.lower(), "role": data.role}
    except IntegrityError as exc:
        if exc.errno == 1062: raise HTTPException(409, "Email or phone is already registered") from None
        raise


def _login(data: LoginIn, admin: bool):
    with cursor() as (_, cur):
        cur.execute("SELECT user_id,name,email,role,password_hash FROM users WHERE email=%s", (data.email.lower(),))
        user = cur.fetchone()
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if (user["role"] == "ADMIN") != admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_access_token(user["user_id"], user["role"])
    return {"access_token": token, "token_type": "bearer", "user": {k:user[k] for k in ("user_id","name","email","role")}}


@router.post("/auth/login")
def login(data: LoginIn):
    return _login(data, admin=False)


@router.post("/auth/admin/login")
def admin_login(data: LoginIn):
    return _login(data, admin=True)


@router.post("/auth/role")
def choose_role(data: RoleIn, user=Depends(get_current_user)):
    if user["role"] != "USER":
        raise HTTPException(status.HTTP_409_CONFLICT, "This account already has a role")
    with cursor() as (conn, cur):
        cur.execute("UPDATE users SET role=%s WHERE user_id=%s AND role='USER'", (data.role,user["user_id"]))
        if cur.rowcount != 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "This account already has a role")
        conn.commit()
    return {**user,"role":data.role}
