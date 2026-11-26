from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, String, Text

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CrmLead(Base):
    """Tenant-scoped CRM Lead entity."""

    __tablename__ = "crm_leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    company_name = Column(String(150), nullable=False)
    contact_name = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=False)
    email = Column(String(120), nullable=True)
    source = Column(String(80), nullable=False, default="Inbound")
    status = Column(String(30), nullable=False, default="NEW")
    potential_value = Column(Numeric(12, 2, asdecimal=True), nullable=True)
    inquiry_date = Column(Date, nullable=False, default=date.today)
    lost_reason = Column(Text, nullable=True)
    is_qualified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)
