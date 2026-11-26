from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app import security
from app.crm.leads import service
from app.crm.leads.schemas import LeadCreate, LeadResponse, LeadStatusUpdate, LeadUpdate
from app.database import get_db

router = APIRouter(
    prefix="/crm/leads",
    tags=["CRM - Leads"],
)


@router.post(
    "/",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a CRM lead",
)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.create_lead(db=db, company_id=current_user.company_id, payload=payload)


@router.get(
    "/",
    response_model=List[LeadResponse],
    summary="List CRM leads",
)
def list_leads(
    status_filter: Annotated[Optional[str], Query(description="Filter by lead status")] = None,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.list_leads(
        db=db,
        company_id=current_user.company_id,
        status_filter=status_filter,
    )


@router.get(
    "/{lead_id}",
    response_model=LeadResponse,
    summary="Get a CRM lead by ID",
)
def get_lead(
    lead_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.get_lead(db=db, company_id=current_user.company_id, lead_id=lead_id)


@router.put(
    "/{lead_id}",
    response_model=LeadResponse,
    summary="Update a CRM lead",
)
def update_lead(
    lead_id: Annotated[int, Path(ge=1)],
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.update_lead(
        db=db,
        company_id=current_user.company_id,
        lead_id=lead_id,
        payload=payload,
    )


@router.patch(
    "/{lead_id}/status",
    response_model=LeadResponse,
    summary="Transition CRM lead status",
)
def move_lead_status(
    lead_id: Annotated[int, Path(ge=1)],
    payload: LeadStatusUpdate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.move_lead_status(
        db=db,
        company_id=current_user.company_id,
        lead_id=lead_id,
        payload=payload,
    )


@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a CRM lead",
)
def delete_lead(
    lead_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    service.delete_lead(db=db, company_id=current_user.company_id, lead_id=lead_id)
    return None
