from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crm.leads.models import CrmLead
from app.crm.leads.schemas import LeadCreate, LeadStatusUpdate, LeadUpdate

LEAD_STATUS_ORDER: Tuple[str, ...] = (
    "NEW",
    "CONTACTED",
    "QUALIFIED",
    "PROPOSAL_SENT",
    "NEGOTIATION",
    "WON",
    "LOST",
    "JUNK",
)


def _ensure_unique_company_phone(
    db: Session,
    company_id: int,
    company_name: str,
    phone: str,
    exclude_lead_id: Optional[int] = None,
) -> None:
    """Reject duplicate (company_name, phone) within the same tenant."""
    stmt = select(CrmLead).where(
        CrmLead.company_id == company_id,
        func.lower(CrmLead.company_name) == company_name.strip().lower(),
        CrmLead.phone == phone.strip(),
    )
    if exclude_lead_id is not None:
        stmt = stmt.where(CrmLead.id != exclude_lead_id)
    if db.scalar(stmt):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A lead with this company name and phone already exists in the organization.",
        )


def create_lead(db: Session, company_id: int, payload: LeadCreate) -> CrmLead:
    """Create a tenant-scoped CRM lead enforcing unique company_name + phone."""
    _ensure_unique_company_phone(db, company_id, payload.company_name, payload.phone)
    lead = CrmLead(
        company_id=company_id,
        company_name=payload.company_name,
        contact_name=payload.contact_name,
        phone=payload.phone,
        email=str(payload.email).strip().lower() if payload.email else None,
        source=payload.source,
        status="NEW",
        potential_value=payload.potential_value,
        inquiry_date=payload.inquiry_date,
        is_qualified=False,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def list_leads(
    db: Session,
    company_id: int,
    status_filter: Optional[str] = None,
) -> List[CrmLead]:
    """List tenant-scoped CRM leads."""
    stmt = select(CrmLead).where(CrmLead.company_id == company_id)
    if status_filter:
        stmt = stmt.where(CrmLead.status == status_filter.strip().upper())
    return list(db.scalars(stmt.order_by(CrmLead.id.desc())).all())


def get_lead(db: Session, company_id: int, lead_id: int) -> CrmLead:
    """Fetch a single tenant-scoped lead or raise 404."""
    lead = db.scalar(
        select(CrmLead).where(
            CrmLead.id == lead_id,
            CrmLead.company_id == company_id,
        )
    )
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found.",
        )
    return lead


def update_lead(db: Session, company_id: int, lead_id: int, payload: LeadUpdate) -> CrmLead:
    """Update lead fields while enforcing tenant-scoped company_name + phone uniqueness."""
    lead = get_lead(db, company_id, lead_id)
    target_company = payload.company_name if payload.company_name is not None else lead.company_name
    target_phone = payload.phone if payload.phone is not None else lead.phone
    _ensure_unique_company_phone(db, company_id, target_company, target_phone, exclude_lead_id=lead.id)

    if payload.company_name is not None:
        lead.company_name = payload.company_name.strip()
    if payload.contact_name is not None:
        lead.contact_name = payload.contact_name.strip()
    if payload.phone is not None:
        lead.phone = payload.phone.strip()
    if payload.email is not None:
        lead.email = str(payload.email).strip().lower()
    if payload.potential_value is not None:
        lead.potential_value = payload.potential_value

    db.commit()
    db.refresh(lead)
    return lead


def move_lead_status(
    db: Session,
    company_id: int,
    lead_id: int,
    payload: LeadStatusUpdate,
) -> CrmLead:
    """Transition lead across canonical statuses; LOST requires a non-empty lost_reason."""
    lead = get_lead(db, company_id, lead_id)
    next_status = payload.status.strip().upper()
    if next_status not in LEAD_STATUS_ORDER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lead status '{next_status}'.",
        )
    if next_status == "LOST" and not (payload.lost_reason and payload.lost_reason.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marking a lead LOST requires a lost_reason.",
        )

    lead.status = next_status
    lead.lost_reason = payload.lost_reason.strip() if next_status == "LOST" and payload.lost_reason else None
    if next_status in ("QUALIFIED", "PROPOSAL_SENT", "NEGOTIATION", "WON"):
        lead.is_qualified = True

    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, company_id: int, lead_id: int) -> None:
    """Delete a lead unless it is already WON."""
    lead = get_lead(db, company_id, lead_id)
    if lead.status == "WON":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a WON lead.",
        )
    db.delete(lead)
    db.commit()
