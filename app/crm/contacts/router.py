from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app import security
from app.crm.contacts import service
from app.crm.contacts.schemas import ContactCreate, ContactResponse, ContactUpdate
from app.database import get_db

router = APIRouter(
    prefix="/crm/contacts",
    tags=["CRM - Contacts"],
)


@router.post(
    "/",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a CRM contact",
)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.create_contact(db=db, company_id=current_user.company_id, payload=payload)


@router.get(
    "/",
    response_model=List[ContactResponse],
    summary="List CRM contacts",
)
def list_contacts(
    account_name: Annotated[Optional[str], Query(description="Filter by account name")] = None,
    active_only: Annotated[bool, Query(description="Return only active contacts")] = False,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.list_contacts(
        db=db,
        company_id=current_user.company_id,
        account_name=account_name,
        active_only=active_only,
    )


@router.get(
    "/{contact_id}",
    response_model=ContactResponse,
    summary="Get a CRM contact by ID",
)
def get_contact(
    contact_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.get_contact(db=db, company_id=current_user.company_id, contact_id=contact_id)


@router.put(
    "/{contact_id}",
    response_model=ContactResponse,
    summary="Update a CRM contact",
)
def update_contact(
    contact_id: Annotated[int, Path(ge=1)],
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.update_contact(
        db=db,
        company_id=current_user.company_id,
        contact_id=contact_id,
        payload=payload,
    )


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a CRM contact",
)
def delete_contact(
    contact_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    service.delete_contact(db=db, company_id=current_user.company_id, contact_id=contact_id)
    return None
