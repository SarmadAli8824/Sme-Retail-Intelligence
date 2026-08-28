import csv, hashlib, io
from datetime import datetime
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .auth import current_user, hash_password, require_owner, token_for, verify_password
from .config import settings
from .database import Base, engine, get_db
from .forecasting import build_forecast
from .models import ChatAudit, Forecast, Inventory, Organization, Sale, Upload, User
from .schemas import ChatIn, ChatOut, ForecastOut, LoginIn, RegisterIn, TokenOut, UserCreate
from .chat import rule_sql, validate_and_scope
from .llm import generate_sql
REQUESTS=Counter("retail_api_requests_total","API requests",["route"])
app=FastAPI(title="SME Retail Intelligence API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin,"http://localhost:4200"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.on_event("startup")
def startup(): Base.metadata.create_all(bind=engine)
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/metrics")
def metrics(): return PlainTextResponse(generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.post("/api/v1/auth/register",response_model=TokenOut)
def register(payload:RegisterIn,db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==payload.email)): raise HTTPException(409,"Email already registered")
    org=Organization(name=payload.organization_name); db.add(org); db.flush()
    user=User(organization_id=org.id,email=str(payload.email).lower(),password_hash=hash_password(payload.password),role="owner"); db.add(user); db.commit()
    return TokenOut(access_token=token_for(user),role=user.role,organization_id=org.id)
@app.post("/api/v1/auth/login",response_model=TokenOut)
def login(payload:LoginIn,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==payload.email.lower()))
    if not user or not verify_password(payload.password,user.password_hash): raise HTTPException(401,"Invalid credentials")
    return TokenOut(access_token=token_for(user),role=user.role,organization_id=user.organization_id)
@app.get("/api/v1/auth/me")
def me(user:User=Depends(current_user)): return {"id":user.id,"email":user.email,"role":user.role,"organization_id":user.organization_id}
@app.post("/api/v1/users")
def create_user(payload:UserCreate,owner:User=Depends(require_owner),db:Session=Depends(get_db)):
    if payload.role not in {"owner","staff"}: raise HTTPException(422,"Invalid role")
    if db.scalar(select(User).where(User.email==payload.email)): raise HTTPException(409,"Email already registered")
    user=User(organization_id=owner.organization_id,email=str(payload.email),password_hash=hash_password(payload.password),role=payload.role); db.add(user); db.commit(); return {"id":user.id,"email":user.email,"role":user.role}
@app.get("/api/v1/users")
def list_users(owner:User=Depends(require_owner),db:Session=Depends(get_db)):
    return [{"id":u.id,"email":u.email,"role":u.role} for u in db.scalars(select(User).where(User.organization_id==owner.organization_id))]
def parse_upload(raw:bytes,kind:str):
    try: rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except UnicodeDecodeError: raise HTTPException(422,"CSV must be UTF-8 encoded")
    required={"sales":{"date","sku","quantity_sold"},"inventory":{"sku","stock_on_hand"}}[kind]
    if not rows or not required <= set(rows[0]): raise HTTPException(422,f"Required columns: {', '.join(sorted(required))}")
    good=[]; errors=[]
    for index,row in enumerate(rows,start=2):
        try:
            sku=row["sku"].strip().upper()
            if not sku: raise ValueError("SKU is empty")
            if kind=="sales": good.append((datetime.fromisoformat(row["date"].strip()).date(),sku,float(row["quantity_sold"])))
            else: good.append((sku,float(row["stock_on_hand"])))
        except (KeyError,ValueError,TypeError) as exc: errors.append({"row":index,"error":str(exc)})
    return good,errors
@app.post("/api/v1/uploads/{kind}")
async def upload(kind:str,file:UploadFile=File(...),user:User=Depends(current_user),db:Session=Depends(get_db)):
    if kind not in {"sales","inventory"}: raise HTTPException(404,"Unknown upload type")
    raw=await file.read(); checksum=hashlib.sha256(raw).hexdigest()
    existing=db.scalar(select(Upload).where(Upload.organization_id==user.organization_id,Upload.checksum==checksum))
    if existing: return {"id":existing.id,"status":"duplicate","rows_processed":existing.rows_processed,"errors":existing.errors}
    good,errors=parse_upload(raw,kind); record=Upload(organization_id=user.organization_id,filename=file.filename or "upload.csv",kind=kind,checksum=checksum,status="processing",errors=errors); db.add(record);db.flush()
    if kind=="sales": db.add_all([Sale(organization_id=user.organization_id,date=d,sku=s,quantity_sold=q,upload_id=record.id) for d,s,q in good])
    else:
        for sku,stock in good:
            inv=db.scalar(select(Inventory).where(Inventory.organization_id==user.organization_id,Inventory.sku==sku))
            if inv: inv.stock_on_hand=stock
            else: db.add(Inventory(organization_id=user.organization_id,sku=sku,stock_on_hand=stock))
    record.rows_processed=len(good); record.status="completed" if good else "failed"; db.commit(); REQUESTS.labels("upload").inc()
    return {"id":record.id,"status":record.status,"rows_processed":record.rows_processed,"errors":errors}
@app.get("/api/v1/uploads")
def uploads(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [{"id":u.id,"filename":u.filename,"kind":u.kind,"status":u.status,"rows_processed":u.rows_processed,"errors":u.errors,"created_at":u.created_at} for u in db.scalars(select(Upload).where(Upload.organization_id==user.organization_id).order_by(Upload.created_at.desc()))]
@app.get("/api/v1/inventory")
def inventory(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [{"sku":x.sku,"stock_on_hand":x.stock_on_hand,"updated_at":x.updated_at} for x in db.scalars(select(Inventory).where(Inventory.organization_id==user.organization_id).order_by(Inventory.sku))]
@app.post("/api/v1/forecasts/{sku}",response_model=ForecastOut)
def forecast(sku:str,horizon:int=14,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not 7<=horizon<=30: raise HTTPException(422,"horizon must be between 7 and 30")
    try: out=build_forecast(db,user.organization_id,sku.upper(),horizon)
    except ValueError as exc: raise HTTPException(422,str(exc))
    db.add(Forecast(organization_id=user.organization_id,**out));db.commit();REQUESTS.labels("forecast").inc();return out
@app.get("/api/v1/dashboard")
def dashboard(user:User=Depends(current_user),db:Session=Depends(get_db)):
    sales=db.execute(select(Sale.sku,func.sum(Sale.quantity_sold).label("units")).where(Sale.organization_id==user.organization_id).group_by(Sale.sku).order_by(func.sum(Sale.quantity_sold).desc())).all()
    inv=list(db.scalars(select(Inventory).where(Inventory.organization_id==user.organization_id)))
    return {"top_movers":[{"sku":r.sku,"units":r.units} for r in sales[:5]],"bottom_movers":[{"sku":r.sku,"units":r.units} for r in sales[-5:]],"low_stock":[{"sku":x.sku,"stock_on_hand":x.stock_on_hand} for x in inv if x.stock_on_hand<10],"overstock":[{"sku":x.sku,"stock_on_hand":x.stock_on_hand} for x in inv if x.stock_on_hand>100]}
@app.post("/api/v1/chat",response_model=ChatOut)
async def chat(payload:ChatIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    fallback,summary=rule_sql(payload.question)
    sql=await generate_sql(payload.question) or fallback
    try:
        approved=validate_and_scope(sql,user.organization_id)
        # Execute constrained query via application query builders; SQL text is audit-only in this deterministic MVP.
        if "inventory" in sql:
            inventory_query=select(Inventory).where(Inventory.organization_id==user.organization_id)
            if "stock_on_hand < 10" in sql: inventory_query=inventory_query.where(Inventory.stock_on_hand<10)
            rows=[{"sku":x.sku,"stock_on_hand":x.stock_on_hand} for x in db.scalars(inventory_query.order_by(Inventory.stock_on_hand).limit(100))]
        elif "forecasts" in sql: rows=[{"sku":f.sku,"model_name":f.model_name,"mae":f.mae,"rmse":f.rmse,"predictions":f.predictions} for f in db.scalars(select(Forecast).where(Forecast.organization_id==user.organization_id).order_by(Forecast.created_at.desc()).limit(100))]
        else: rows=[{"sku":r.sku,"units_sold":r.units_sold} for r in db.execute(select(Sale.sku,func.sum(Sale.quantity_sold).label("units_sold")).where(Sale.organization_id==user.organization_id).group_by(Sale.sku).order_by(func.sum(Sale.quantity_sold).desc()).limit(100))]
        db.add(ChatAudit(organization_id=user.organization_id,user_id=user.id,question=payload.question,generated_sql=approved,accepted=True));db.commit(); return ChatOut(answer=f"{summary}. I found {len(rows)} result(s).",rows=rows,query_summary=summary)
    except Exception as exc:
        db.add(ChatAudit(organization_id=user.organization_id,user_id=user.id,question=payload.question,generated_sql=sql,accepted=False,reason=str(exc)));db.commit(); return ChatOut(answer="I could not safely answer that request.",rows=[],query_summary="Request rejected",rejected=True)
