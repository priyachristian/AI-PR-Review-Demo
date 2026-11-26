from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CrmContact(Base):
    """Tenant-scoped CRM Contact linked to an account/organization."""

    __tablename__ = "crm_contacts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    account_name = Column(String(150), nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=True)
    job_title = Column(String(100), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_crm_company_contact_email"),
    )
