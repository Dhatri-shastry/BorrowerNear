from contextlib import contextmanager
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user
import app.main as main_module
import app.routes.read as read_module
import app.routes.messaging as messaging_module
import app.routes.auth as auth_module


class FakeCursor:
    def __init__(self, row=None, rows=None): self.row=row; self.rows=rows or []; self.lastrowid=42
    def execute(self, *_): pass
    def fetchone(self): return self.row
    def fetchall(self): return self.rows
    def close(self): pass


class FakeConnection:
    def __init__(self): self.committed=False; self.rolled_back=False; self.closed=False; self.in_transaction=True
    def commit(self): self.committed=True; self.in_transaction=False
    def rollback(self): self.rolled_back=True; self.in_transaction=False
    def close(self): self.closed=True


def install_cursor(monkeypatch, module, row=None, rows=None):
    @contextmanager
    def fake(): yield FakeConnection(), FakeCursor(row, rows)
    monkeypatch.setattr(module, "cursor", fake)
    if module is read_module:
        monkeypatch.setattr(module,"get_cached_items",lambda *_:None)
        monkeypatch.setattr(module,"set_cached_items",lambda *_:None)
        monkeypatch.setattr(module,"invalidate_item_caches_safely",lambda:None)


def test_health_queries_db_count(monkeypatch):
    install_cursor(monkeypatch, main_module, {"items_in_db":10})
    assert TestClient(app).get("/health").json()=={"status":"ok","items_in_db":10}


def test_items_list_and_filters(monkeypatch):
    install_cursor(monkeypatch, read_module, rows=[{"item_id":1}])
    client=TestClient(app)
    result=client.get("/api/v1/items?category_id=2&status=AVAILABLE&search=drill")
    assert result.status_code==200 and result.json()["items"]==[{"item_id":1}]
    assert client.get("/api/v1/items?status=LOST").status_code==422
    assert client.get("/api/v1/items?limit=101").status_code==422
    assert client.get("/api/v1/items?sort_by=anything").status_code==422


def test_item_detail_404(monkeypatch):
    install_cursor(monkeypatch, read_module)
    assert TestClient(app).get("/api/v1/items/9999").status_code==404


def test_protected_endpoint_and_admin_role():
    client=TestClient(app)
    assert client.get("/api/v1/requests").status_code==401
    app.dependency_overrides[get_current_user]=lambda:{"user_id":7,"role":"USER","name":"Test","email":"t@example.com"}
    try: assert client.get("/api/v1/admin/stats").status_code==403
    finally: app.dependency_overrides.clear()


def test_registration_never_accepts_role():
    response=TestClient(app).post("/api/v1/auth/register",json={"name":"Test","email":"t@example.com",
       "phone":"9876500001","password":"a-very-strong-password","location_id":1,"role":"ADMIN"})
    assert response.status_code==422


def test_password_hash_round_trip_and_plaintext_not_stored():
    from app.security import hash_password, verify_password
    raw="an-example-password-that-is-long-enough"
    hashed=hash_password(raw)
    assert hashed != raw
    assert verify_password(raw,hashed)
    assert not verify_password("wrong-password",hashed)


def test_registration_creates_user_role_and_never_returns_hash(monkeypatch):
    install_cursor(monkeypatch, auth_module, {"location_id":1})
    monkeypatch.setattr(auth_module, "hash_password", lambda _: "secure-hash")
    response=TestClient(app).post("/api/v1/auth/register",json={"name":"New Member","email":"new@example.com",
       "phone":"9876500123","password":"a-very-strong-password","location_id":1})
    assert response.status_code==201
    assert response.json()["role"]=="USER" and "password_hash" not in response.json()


def test_login_and_invalid_credentials(monkeypatch):
    from app.security import hash_password
    row={"user_id":3,"name":"Member","email":"member@example.com","role":"USER","password_hash":hash_password("a-very-strong-password")}
    install_cursor(monkeypatch,auth_module,row)
    monkeypatch.setattr(auth_module,"create_access_token",lambda *_:"test-token")
    client=TestClient(app)
    valid=client.post("/api/v1/auth/login",json={"email":"member@example.com","password":"a-very-strong-password"})
    invalid=client.post("/api/v1/auth/login",json={"email":"member@example.com","password":"incorrect"})
    assert valid.status_code==200 and valid.json()["access_token"]=="test-token"
    assert "password_hash" not in valid.json()["user"]
    assert invalid.status_code==401


def test_messaging_requires_authentication():
    assert TestClient(app).get("/api/v1/conversations").status_code==401


def test_nonparticipant_cannot_create_conversation(monkeypatch):
    from contextlib import contextmanager
    row={"request_id":5,"item_id":9,"borrower_id":4,"owner_id":2,"item_name":"Camera"}
    @contextmanager
    def fake_cursor(): yield object(),FakeCursor(row)
    monkeypatch.setattr(messaging_module,"cursor",fake_cursor)
    app.dependency_overrides[get_current_user]=lambda:{"user_id":99,"role":"USER","name":"Outsider","email":"x@example.com"}
    try:
        response=TestClient(app).post("/api/v1/conversations",json={"request_id":5})
        assert response.status_code==403
    finally: app.dependency_overrides.clear()


def test_message_api_rejects_blank_text():
    app.dependency_overrides[get_current_user]=lambda:{"user_id":4,"role":"USER","name":"Member","email":"x@example.com"}
    try:
        response=TestClient(app).post("/api/v1/conversations/0123456789abcdef01234567/messages",json={"text":"   "})
        assert response.status_code==422
    finally: app.dependency_overrides.clear()


def test_nonparticipant_cannot_read_conversation(monkeypatch):
    monkeypatch.setattr(messaging_module,"is_conversation_participant",lambda *_:False)
    app.dependency_overrides[get_current_user]=lambda:{"user_id":99,"role":"USER","name":"Outsider","email":"x@example.com"}
    try:
        response=TestClient(app).get("/api/v1/conversations/0123456789abcdef01234567/messages")
        assert response.status_code==404
    finally: app.dependency_overrides.clear()


def test_connection_rolls_back_on_exception(monkeypatch):
    import app.db as db_module
    connection=FakeConnection()
    class Pool:
        def get_connection(self): return connection
    monkeypatch.setattr(db_module,"get_pool",lambda:Pool())
    try:
        with db_module.connection(): raise RuntimeError("simulated operation failure")
    except RuntimeError: pass
    assert connection.rolled_back and connection.closed and not connection.committed
