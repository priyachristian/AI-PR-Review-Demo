from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crm.contacts.models import CrmContact
from app.crm.contacts.schemas import ContactCreate, ContactUpdate


def _demote_existing_primary_contacts(
    db: Session,
    company_id: int,
    account_name: str,
    exclude_contact_id: Optional[int] = None,
) -> None:
    """Ensure only one primary contact exists per tenant account."""
    stmt = (
        update(CrmContact)
        .where(
            CrmContact.company_id == company_id,
            func.lower(CrmContact.account_name) == account_name.strip().lower(),
            CrmContact.is_primary.is_(True),
        )
        .values(is_primary=False)
    )
    if exclude_contact_id is not None:
        stmt = stmt.where(CrmContact.id != exclude_contact_id)
    db.execute(stmt)


def create_contact(db: Session, company_id: int, payload: ContactCreate) -> CrmContact:
    """Create a tenant-scoped CRM contact enforcing email uniqueness and single primary contact per account."""
    norm_email = str(payload.email).strip().lower()
    existing = db.scalar(
        select(CrmContact).where(
            CrmContact.company_id == company_id,
            CrmContact.email == norm_email,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact with email '{norm_email}' already exists.",
        )

    if payload.is_primary:
        _demote_existing_primary_contacts(db, company_id, payload.account_name)

    contact = CrmContact(
        company_id=company_id,
        account_name=payload.account_name,
        full_name=payload.full_name,
        email=norm_email,
        phone=payload.phone.strip() if payload.phone else None,
        job_title=payload.job_title.strip() if payload.job_title else None,
        is_primary=payload.is_primary,
        is_active=True,
    )
    db.add(contact)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact with email '{norm_email}' already exists.",
        )
    db.refresh(contact)
    return contact


def list_contacts(
    db: Session,
    company_id: int,
    account_name: Optional[str] = None,
    active_only: bool = False,
) -> List[CrmContact]:
    """List tenant-scoped CRM contacts."""
    stmt = select(CrmContact).where(CrmContact.company_id == company_id)
    if account_name:
        stmt = stmt.where(CrmContact.account_name.ilike(f"%{account_name.strip()}%"))
    if active_only:
        stmt = stmt.where(CrmContact.is_active.is_(True))
    return list(db.scalars(stmt.order_by(CrmContact.id.asc())).all())


def get_contact(db: Session, company_id: int, contact_id: int) -> CrmContact:
    """Fetch a tenant-scoped CRM contact or raise 404."""
    contact = db.scalar(
        select(CrmContact).where(
            CrmContact.id == contact_id,
            CrmContact.company_id == company_id,
        )
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact {contact_id} not found.",
        )
    return contact


def update_contact(
    db: Session,
    company_id: int,
    contact_id: int,
    payload: ContactUpdate,
) -> CrmContact:
    """Update a CRM contact with email uniqueness and primary-contact invariants."""
    contact = get_contact(db, company_id, contact_id)

    if payload.email is not None:
        norm_email = str(payload.email).strip().lower()
        if norm_email != contact.email.lower():
            conflict = db.scalar(
                select(CrmContact).where(
                    CrmContact.company_id == company_id,
                    CrmContact.email == norm_email,
                    CrmContact.id != contact.id,
                )
            )
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{norm_email}' is already assigned to another contact.",
                )
            contact.email = norm_email

    if payload.account_name is not None:
        contact.account_name = payload.account_name.strip()
    if payload.full_name is not None:
        contact.full_name = payload.full_name.strip()
    if payload.phone is not None:
        contact.phone = payload.phone.strip()
    if payload.job_title is not None:
        contact.job_title = payload.job_title.strip()
    if payload.is_active is not None:
        contact.is_active = payload.is_active

    if payload.is_primary is True:
        _demote_existing_primary_contacts(
            db,
            company_id,
            contact.account_name,
            exclude_contact_id=contact.id,
        )
        contact.is_primary = True
    elif payload.is_primary is False:
        contact.is_primary = False

    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, company_id: int, contact_id: int) -> None:
    """Delete a non-primary CRM contact."""
    contact = get_contact(db, company_id, contact_id)
    if contact.is_primary:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete primary contact; assign another primary contact first.",
        )
    db.delete(contact)
    db.commit()
