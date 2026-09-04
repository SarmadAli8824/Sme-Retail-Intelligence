import csv
import hashlib
import io
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .auth import current_user, hash_password, require_owner, token_for, verify_password
from .chat import execute_safe, question_is_unsafe, rule_sql, validate_and_scope
from .config import settings
from .database import Base, engine, ensure_schema_compatibility, get_db
from .forecasting import build_forecast
from .llm import generate_sql
from .models import ChatAudit, Forecast, Inventory, Organization, Sale, Upload, User, utcnow
from .schemas import ChatIn, ChatOut, ForecastOut, LoginIn, RegisterIn, SettingsIn, TokenOut, UserCreate, UserUpdate


REQUESTS = Counter("retail_api_requests_total", "Completed API operations", ["route", "status"])


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    with Session(engine) as db:
        _seed_demo(db)
    yield


app = FastAPI(
    title="SME Retail Intelligence API",
    description="Tenant-safe CSV retail analytics, demand forecasting, and conversational insights.",
    version="1.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({settings.frontend_origin, "http://localhost:3000", "http://localhost:4200"}),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _seed_demo(db: Session) -> None:
    if not settings.seed_demo_data or db.scalar(select(User).where(User.email == settings.demo_owner_email)):
        return
    org = db.scalar(select(Organization).where(Organization.name == "Demo Corner Shop"))
    if not org:
        org = Organization(name="Demo Corner Shop")
        db.add(org)
        db.flush()
    owner = User(organization_id=org.id, email=settings.demo_owner_email, password_hash=hash_password(settings.demo_owner_password), role="owner")
    existing_upload = db.scalar(select(Upload).where(Upload.organization_id == org.id, Upload.checksum == "demo-seed-v1"))
    if existing_upload:
        db.add(owner)
        db.commit()
        return
    upload = Upload(organization_id=org.id, filename="demo-data.csv", kind="sales", checksum="demo-seed-v1", status="completed", total_rows=90, rows_processed=90, completed_at=utcnow())
    db.add_all([owner, upload])
    db.flush()
    skus = [("COFFEE-01", "Ground Coffee", 8, 5), ("TEA-02", "Breakfast Tea", 42, 3), ("SNACK-03", "Oat Biscuits", 120, 1)]
    for sku, name, stock, base in skus:
        db.add(Inventory(organization_id=org.id, sku=sku, product_name=name, stock_on_hand=stock, reorder_point=10))
        for offset in range(90):
            db.add(Sale(organization_id=org.id, upload_id=upload.id, date=date.today() - timedelta(days=89 - offset), sku=sku, product_name=name, quantity_sold=float(base + (offset % 3))))
    db.commit()


@app.get("/health")
@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": app.version}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/auth/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    if db.scalar(select(Organization).where(func.lower(Organization.name) == payload.organization_name.strip().lower())):
        raise HTTPException(409, "An organization with this name already exists")
    org = Organization(name=payload.organization_name.strip())
    db.add(org)
    db.flush()
    user = User(organization_id=org.id, email=email, password_hash=hash_password(payload.password), role="owner")
    db.add(user)
    db.commit()
    REQUESTS.labels("register", "success").inc()
    return TokenOut(access_token=token_for(user), role=user.role, organization_id=org.id)


@app.post("/api/v1/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        REQUESTS.labels("login", "rejected").inc()
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "This account is inactive")
    REQUESTS.labels("login", "success").inc()
    return TokenOut(access_token=token_for(user), role=user.role, organization_id=user.organization_id)


@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id)
    return {"id": user.id, "email": user.email, "role": user.role, "organization_id": user.organization_id, "organization_name": org.name}


@app.post("/api/v1/users", status_code=201)
def create_user(payload: UserCreate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    role = payload.role.lower()
    email = str(payload.email).lower()
    if role not in {"owner", "staff"}:
        raise HTTPException(422, "Role must be owner or staff")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(organization_id=owner.organization_id, email=email, password_hash=hash_password(payload.password), role=role)
    db.add(user)
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role, "is_active": user.is_active}


@app.get("/api/v1/users")
def list_users(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.organization_id == owner.organization_id).order_by(User.created_at)).all()
    return [{"id": item.id, "email": item.email, "role": item.role, "is_active": item.is_active, "created_at": item.created_at} for item in users]


@app.patch("/api/v1/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.id == user_id, User.organization_id == owner.organization_id))
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == owner.id and payload.is_active is False:
        raise HTTPException(422, "You cannot deactivate your own account")
    if payload.role is not None:
        if payload.role not in {"owner", "staff"}:
            raise HTTPException(422, "Role must be owner or staff")
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
    db.commit()
    return {"id": target.id, "email": target.email, "role": target.role, "is_active": target.is_active}


@app.get("/api/v1/settings")
def get_settings(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    org = db.get(Organization, owner.organization_id)
    return {"organization_name": org.name, "low_stock_threshold": org.low_stock_threshold, "overstock_days": org.overstock_days, "digest_enabled": org.digest_enabled}


@app.put("/api/v1/settings")
def update_settings(payload: SettingsIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    org = db.get(Organization, owner.organization_id)
    org.low_stock_threshold = payload.low_stock_threshold
    org.overstock_days = payload.overstock_days
    org.digest_enabled = payload.digest_enabled
    db.commit()
    return get_settings(owner, db)


def parse_upload(raw: bytes, kind: str) -> tuple[list[dict], list[dict]]:
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        rows = list(reader)
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "CSV must be UTF-8 encoded") from exc
    required = {"sales": {"date", "sku", "quantity_sold"}, "inventory": {"sku", "stock_on_hand"}}[kind]
    columns = set(reader.fieldnames or [])
    if not rows or not required <= columns:
        raise HTTPException(422, f"Required columns: {', '.join(sorted(required))}")
    good: list[dict] = []
    errors: list[dict] = []
    for index, row in enumerate(rows, start=2):
        try:
            sku = (row.get("sku") or "").strip().upper()
            if not sku:
                raise ValueError("SKU is empty")
            if kind == "sales":
                quantity = float(row["quantity_sold"])
                if quantity < 0:
                    raise ValueError("quantity_sold cannot be negative")
                item = {"date": date.fromisoformat(row["date"].strip()), "sku": sku, "quantity_sold": quantity}
                for key in ("unit_price",):
                    if row.get(key, "").strip():
                        item[key] = float(row[key])
                for key in ("product_name", "category"):
                    if row.get(key, "").strip():
                        item[key] = row[key].strip()[:240]
            else:
                stock = float(row["stock_on_hand"])
                if stock < 0:
                    raise ValueError("stock_on_hand cannot be negative")
                item = {"sku": sku, "stock_on_hand": stock}
                for key in ("reorder_point", "unit_cost"):
                    if row.get(key, "").strip():
                        item[key] = float(row[key])
                for key in ("product_name", "category"):
                    if row.get(key, "").strip():
                        item[key] = row[key].strip()[:240]
            good.append(item)
        except (KeyError, ValueError, TypeError) as exc:
            errors.append({"row": index, "error": str(exc) or "Invalid value"})
    return good, errors


def _process_upload(db: Session, record: Upload, rows: list[dict]) -> None:
    if record.kind == "sales":
        db.add_all([Sale(organization_id=record.organization_id, upload_id=record.id, **row) for row in rows])
    else:
        for row in rows:
            item = db.scalar(select(Inventory).where(Inventory.organization_id == record.organization_id, Inventory.sku == row["sku"]))
            if item:
                for key, value in row.items():
                    setattr(item, key, value)
            else:
                db.add(Inventory(organization_id=record.organization_id, **row))
    record.rows_processed = len(rows)
    record.status = "completed" if rows else "failed"
    record.completed_at = utcnow()
    record.payload = None


def _upload_out(item: Upload) -> dict:
    return {"id": item.id, "filename": item.filename, "kind": item.kind, "status": item.status, "total_rows": item.total_rows, "rows_processed": item.rows_processed, "errors": item.errors, "created_at": item.created_at, "completed_at": item.completed_at}


@app.post("/api/v1/uploads/{kind}")
async def upload(kind: str, file: UploadFile = File(...), background: bool = Query(False), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if kind not in {"sales", "inventory"}:
        raise HTTPException(404, "Unknown upload type")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "Only CSV files are accepted")
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, "CSV exceeds the 5 MB upload limit")
    checksum = hashlib.sha256(kind.encode() + raw).hexdigest()
    existing = db.scalar(select(Upload).where(Upload.organization_id == user.organization_id, Upload.checksum == checksum))
    if existing:
        duplicate = _upload_out(existing)
        duplicate["duplicate"] = True
        return duplicate
    good, errors = parse_upload(raw, kind)
    queued_payload = [{**row, **({"date": row["date"].isoformat()} if kind == "sales" else {})} for row in good] if background else None
    record = Upload(organization_id=user.organization_id, filename=file.filename or "upload.csv", kind=kind, checksum=checksum, status="queued" if background and good else "processing", total_rows=len(good) + len(errors), errors=errors, payload=queued_payload)
    db.add(record)
    db.flush()
    if not background:
        _process_upload(db, record, good)
    elif not good:
        record.status = "failed"
    db.commit()
    REQUESTS.labels("upload", record.status).inc()
    return _upload_out(record)


@app.get("/api/v1/uploads")
def uploads(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Upload).where(Upload.organization_id == user.organization_id).order_by(Upload.created_at.desc()).limit(100)).all()
    return [_upload_out(item) for item in items]


@app.get("/api/v1/uploads/{upload_id}")
def upload_status(upload_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(Upload).where(Upload.id == upload_id, Upload.organization_id == user.organization_id))
    if not item:
        raise HTTPException(404, "Upload not found")
    return _upload_out(item)


@app.get("/api/v1/inventory")
def inventory(search: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Inventory).where(Inventory.organization_id == user.organization_id)
    if search:
        query = query.where(Inventory.sku.ilike(f"%{search[:80]}%"))
    items = db.scalars(query.order_by(Inventory.sku).limit(500)).all()
    return [{"sku": item.sku, "product_name": item.product_name, "category": item.category, "stock_on_hand": item.stock_on_hand, "reorder_point": item.reorder_point, "unit_cost": item.unit_cost, "updated_at": item.updated_at} for item in items]


@app.get("/api/v1/sales")
def sales(sku: str | None = None, date_from: date | None = None, date_to: date | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Sale).where(Sale.organization_id == user.organization_id)
    if sku:
        query = query.where(Sale.sku == sku.upper())
    if date_from:
        query = query.where(Sale.date >= date_from)
    if date_to:
        query = query.where(Sale.date <= date_to)
    items = db.scalars(query.order_by(Sale.date.desc()).limit(500)).all()
    return [{"date": item.date, "sku": item.sku, "product_name": item.product_name, "quantity_sold": item.quantity_sold, "unit_price": item.unit_price} for item in items]


@app.post("/api/v1/forecasts/{sku}", response_model=ForecastOut)
def forecast(sku: str, horizon: int = 14, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not 7 <= horizon <= 30:
        raise HTTPException(422, "horizon must be between 7 and 30")
    try:
        output = build_forecast(db, user.organization_id, sku.upper(), horizon)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.add(Forecast(organization_id=user.organization_id, **output))
    db.commit()
    REQUESTS.labels("forecast", "success").inc()
    return output


@app.get("/api/v1/forecasts")
def forecasts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Forecast).where(Forecast.organization_id == user.organization_id).order_by(Forecast.created_at.desc()).limit(100)).all()
    return [{"id": item.id, "sku": item.sku, "horizon_days": item.horizon_days, "model_name": item.model_name, "mae": item.mae, "rmse": item.rmse, "confidence": item.confidence, "status": item.status, "predictions": item.predictions, "created_at": item.created_at} for item in items]


@app.get("/api/v1/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id)
    cutoff = date.today() - timedelta(days=29)
    sales_rows = db.execute(select(Sale.sku, func.sum(Sale.quantity_sold).label("units")).where(Sale.organization_id == user.organization_id).group_by(Sale.sku).order_by(func.sum(Sale.quantity_sold).desc())).all()
    recent_rows = db.execute(select(Sale.sku, func.sum(Sale.quantity_sold).label("units")).where(Sale.organization_id == user.organization_id, Sale.date >= cutoff).group_by(Sale.sku)).all()
    trend_rows = db.execute(select(Sale.date, func.sum(Sale.quantity_sold).label("units")).where(Sale.organization_id == user.organization_id, Sale.date >= cutoff).group_by(Sale.date).order_by(Sale.date)).all()
    inventory_items = list(db.scalars(select(Inventory).where(Inventory.organization_id == user.organization_id)))
    velocities = {row.sku: float(row.units or 0) / 30 for row in recent_rows}
    low_stock, overstock, reorder = [], [], []
    for item in inventory_items:
        threshold = item.reorder_point if item.reorder_point is not None else org.low_stock_threshold
        velocity = velocities.get(item.sku, 0)
        cover = item.stock_on_hand / velocity if velocity > 0 else None
        row = {"sku": item.sku, "product_name": item.product_name, "stock_on_hand": item.stock_on_hand, "days_of_cover": round(cover, 1) if cover is not None else None}
        if item.stock_on_hand < threshold:
            low_stock.append(row)
        if (cover is not None and cover > org.overstock_days) or (cover is None and item.stock_on_hand > max(100, threshold * 5)):
            overstock.append(row)
        suggested = max(0, round(velocity * 14 - item.stock_on_hand))
        if suggested > 0:
            reorder.append({**row, "suggested_quantity": suggested})
    return {
        "summary": {"total_skus": len(inventory_items), "units_sold": round(sum(float(row.units or 0) for row in sales_rows), 2), "low_stock_count": len(low_stock), "reorder_count": len(reorder)},
        "top_movers": [{"sku": row.sku, "units": row.units} for row in sales_rows[:5]],
        "bottom_movers": [{"sku": row.sku, "units": row.units} for row in list(reversed(sales_rows[-5:]))],
        "low_stock": low_stock,
        "overstock": overstock,
        "reorder_suggestions": reorder,
        "sales_trend": [{"date": str(row.date), "units": row.units} for row in trend_rows],
    }


@app.post("/api/v1/chat", response_model=ChatOut)
async def chat(payload: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    fallback, summary = rule_sql(payload.question)
    generated = None
    try:
        if question_is_unsafe(payload.question):
            raise ValueError("The request asks for a prohibited operation or sensitive data")
        generated = await generate_sql(payload.question)
        approved = validate_and_scope(generated or fallback, user.organization_id)
        rows = execute_safe(db, approved, settings.query_timeout_ms)
        db.add(ChatAudit(organization_id=user.organization_id, user_id=user.id, question=payload.question, generated_sql=approved, accepted=True))
        db.commit()
        REQUESTS.labels("chat", "accepted").inc()
        return ChatOut(answer=f"{summary}. I found {len(rows)} result{'s' if len(rows) != 1 else ''}.", rows=rows, query_summary=summary, source_context=["Tenant-scoped retail data", "Maximum 100 rows", "Read-only query"])
    except Exception as exc:
        db.rollback()
        db.add(ChatAudit(organization_id=user.organization_id, user_id=user.id, question=payload.question, generated_sql=generated or fallback, accepted=False, reason=str(exc)[:500]))
        db.commit()
        REQUESTS.labels("chat", "rejected").inc()
        return ChatOut(answer="I could not safely answer that request. Try asking about stock, sales, movers, or forecasts.", rows=[], query_summary="Request rejected", source_context=["No query was executed"], rejected=True)
