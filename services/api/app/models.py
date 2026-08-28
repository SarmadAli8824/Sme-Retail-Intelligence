import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Date, DateTime, ForeignKey, Text, UniqueConstraint, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
def uid(): return str(uuid.uuid4())
class Organization(Base):
    __tablename__="organizations"
    id: Mapped[str]=mapped_column(String, primary_key=True, default=uid); name: Mapped[str]=mapped_column(String(160), unique=True); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
class User(Base):
    __tablename__="users"
    id: Mapped[str]=mapped_column(String, primary_key=True, default=uid); organization_id: Mapped[str]=mapped_column(ForeignKey("organizations.id"), index=True); email: Mapped[str]=mapped_column(String(254), unique=True, index=True); password_hash: Mapped[str]=mapped_column(String); role: Mapped[str]=mapped_column(String(16), default="owner"); is_active: Mapped[bool]=mapped_column(Boolean, default=True); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
class Upload(Base):
    __tablename__="uploads"
    id: Mapped[str]=mapped_column(String, primary_key=True, default=uid); organization_id: Mapped[str]=mapped_column(ForeignKey("organizations.id"), index=True); filename: Mapped[str]=mapped_column(String); kind: Mapped[str]=mapped_column(String(16)); checksum: Mapped[str]=mapped_column(String(64)); status: Mapped[str]=mapped_column(String(16), default="queued"); rows_processed: Mapped[int]=mapped_column(Integer, default=0); errors: Mapped[list]=mapped_column(JSON, default=list); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow); __table_args__=(UniqueConstraint("organization_id","checksum",name="uq_upload_checksum"),)
class Sale(Base):
    __tablename__="sales"
    id: Mapped[str]=mapped_column(String, primary_key=True, default=uid); organization_id: Mapped[str]=mapped_column(ForeignKey("organizations.id"), index=True); date: Mapped[date]=mapped_column(Date, index=True); sku: Mapped[str]=mapped_column(String(128), index=True); quantity_sold: Mapped[float]=mapped_column(Float); upload_id: Mapped[str]=mapped_column(ForeignKey("uploads.id")); __table_args__=(UniqueConstraint("organization_id","date","sku","upload_id",name="uq_sales_source"),)
class Inventory(Base):
    __tablename__="inventory"
    id: Mapped[str]=mapped_column(String, primary_key=True, default=uid); organization_id: Mapped[str]=mapped_column(ForeignKey("organizations.id"), index=True); sku: Mapped[str]=mapped_column(String(128), index=True); stock_on_hand: Mapped[float]=mapped_column(Float); updated_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow); __table_args__=(UniqueConstraint("organization_id","sku",name="uq_inventory_sku"),)
class Forecast(Base):
    __tablename__="forecasts"
    id: Mapped[str]=mapped_column(String, primary_key=True, default=uid); organization_id: Mapped[str]=mapped_column(ForeignKey("organizations.id"), index=True); sku: Mapped[str]=mapped_column(String(128), index=True); horizon_days: Mapped[int]=mapped_column(Integer); model_name: Mapped[str]=mapped_column(String); mae: Mapped[float]=mapped_column(Float); rmse: Mapped[float]=mapped_column(Float); predictions: Mapped[list]=mapped_column(JSON); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
class ChatAudit(Base):
    __tablename__="chat_audits"
    id: Mapped[str]=mapped_column(String, primary_key=True, default=uid); organization_id: Mapped[str]=mapped_column(ForeignKey("organizations.id"), index=True); user_id: Mapped[str]=mapped_column(ForeignKey("users.id")); question: Mapped[str]=mapped_column(Text); generated_sql: Mapped[str|None]=mapped_column(Text, nullable=True); accepted: Mapped[bool]=mapped_column(Boolean); reason: Mapped[str|None]=mapped_column(Text, nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
class DigestRun(Base):
    __tablename__="digest_runs"
    id: Mapped[str]=mapped_column(String, primary_key=True, default=uid); organization_id: Mapped[str]=mapped_column(ForeignKey("organizations.id"), index=True); status: Mapped[str]=mapped_column(String); sent_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
