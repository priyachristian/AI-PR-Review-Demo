from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app import security
from app.crm.opportunities_deals import service
from app.crm.opportunities_deals.schemas import (
    OpportunityDealCreate,
    OpportunityDealResponse,
    OpportunityDealUpdate,
    OpportunityStageTransition,
    PipelineForecastSummary,
)
from app.database import get_db

router = APIRouter(
    prefix="/crm/opportunities-deals",
    tags=["CRM - Opportunities / Deals"],
)


@router.post(
    "/",
    response_model=OpportunityDealResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a CRM opportunity / deal",
)
def create_opportunity_deal(
    payload: OpportunityDealCreate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.create_opportunity_deal(db=db, company_id=current_user.company_id, payload=payload)


@router.get(
    "/",
    response_model=List[OpportunityDealResponse],
    summary="List CRM opportunities / deals",
)
def list_opportunity_deals(
    stage: Annotated[Optional[str], Query(description="Filter by pipeline stage")] = None,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.list_opportunity_deals(
        db=db,
        company_id=current_user.company_id,
        stage=stage,
    )


@router.get(
    "/forecast",
    response_model=PipelineForecastSummary,
    summary="Get probability-weighted CRM pipeline forecast",
)
def get_pipeline_forecast(
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.get_pipeline_forecast(db=db, company_id=current_user.company_id)


@router.get(
    "/{deal_id}",
    response_model=OpportunityDealResponse,
    summary="Get a CRM opportunity / deal by ID",
)
def get_opportunity_deal(
    deal_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.get_opportunity_deal(db=db, company_id=current_user.company_id, deal_id=deal_id)


@router.put(
    "/{deal_id}",
    response_model=OpportunityDealResponse,
    summary="Update a CRM opportunity / deal",
)
def update_opportunity_deal(
    deal_id: Annotated[int, Path(ge=1)],
    payload: OpportunityDealUpdate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.update_opportunity_deal(
        db=db,
        company_id=current_user.company_id,
        deal_id=deal_id,
        payload=payload,
    )


@router.patch(
    "/{deal_id}/stage",
    response_model=OpportunityDealResponse,
    summary="Transition CRM opportunity / deal stage",
)
def transition_opportunity_stage(
    deal_id: Annotated[int, Path(ge=1)],
    payload: OpportunityStageTransition,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.transition_opportunity_stage(
        db=db,
        company_id=current_user.company_id,
        deal_id=deal_id,
        payload=payload,
    )
