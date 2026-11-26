from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crm.opportunities_deals.models import CrmOpportunityDeal
from app.crm.opportunities_deals.schemas import (
    OpportunityDealCreate,
    OpportunityDealUpdate,
    OpportunityStageTransition,
    PipelineForecastSummary,
)

STAGE_PROBABILITY: Dict[str, int] = {
    "PROSPECTING": 10,
    "QUALIFICATION": 25,
    "PROPOSAL": 50,
    "NEGOTIATION": 75,
    "CLOSED_WON": 100,
    "CLOSED_LOST": 0,
}

CLOSED_STAGES = frozenset({"CLOSED_WON", "CLOSED_LOST"})


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_opportunity_deal(
    db: Session,
    company_id: int,
    payload: OpportunityDealCreate,
) -> CrmOpportunityDeal:
    """Create a tenant-scoped CRM Opportunity / Deal at PROSPECTING stage (10%)."""
    deal = CrmOpportunityDeal(
        company_id=company_id,
        deal_name=payload.deal_name,
        account_name=payload.account_name,
        stage="PROSPECTING",
        amount=_round_money(payload.amount),
        probability_pct=STAGE_PROBABILITY["PROSPECTING"],
        expected_close_date=payload.expected_close_date,
        owner_username=payload.owner_username,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def list_opportunity_deals(
    db: Session,
    company_id: int,
    stage: Optional[str] = None,
) -> List[CrmOpportunityDeal]:
    """List tenant-scoped CRM opportunities / deals."""
    stmt = select(CrmOpportunityDeal).where(CrmOpportunityDeal.company_id == company_id)
    if stage:
        stmt = stmt.where(CrmOpportunityDeal.stage == stage.strip().upper())
    return list(
        db.scalars(
            stmt.order_by(CrmOpportunityDeal.expected_close_date.asc(), CrmOpportunityDeal.id.asc())
        ).all()
    )


def get_opportunity_deal(
    db: Session,
    company_id: int,
    deal_id: int,
) -> CrmOpportunityDeal:
    """Fetch a tenant-scoped opportunity / deal or raise 404."""
    deal = db.scalar(
        select(CrmOpportunityDeal).where(
            CrmOpportunityDeal.id == deal_id,
            CrmOpportunityDeal.company_id == company_id,
        )
    )
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity/Deal {deal_id} not found.",
        )
    return deal


def update_opportunity_deal(
    db: Session,
    company_id: int,
    deal_id: int,
    payload: OpportunityDealUpdate,
) -> CrmOpportunityDeal:
    """Update open deal fields; closed deals cannot be modified."""
    deal = get_opportunity_deal(db, company_id, deal_id)
    if deal.stage in CLOSED_STAGES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot modify deal in closed stage '{deal.stage}'.",
        )

    if payload.deal_name is not None:
        deal.deal_name = payload.deal_name.strip()
    if payload.amount is not None:
        deal.amount = _round_money(payload.amount)
    if payload.expected_close_date is not None:
        deal.expected_close_date = payload.expected_close_date
    if payload.owner_username is not None:
        deal.owner_username = payload.owner_username.strip()

    db.commit()
    db.refresh(deal)
    return deal


def transition_opportunity_stage(
    db: Session,
    company_id: int,
    deal_id: int,
    payload: OpportunityStageTransition,
) -> CrmOpportunityDeal:
    """Advance/close opportunity stage; CLOSED_LOST requires a loss_reason."""
    deal = get_opportunity_deal(db, company_id, deal_id)
    if deal.stage in CLOSED_STAGES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Deal is already closed in stage '{deal.stage}'.",
        )

    next_stage = payload.stage.strip().upper()
    if next_stage not in STAGE_PROBABILITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline stage '{next_stage}'.",
        )
    if next_stage == "CLOSED_LOST" and not (payload.loss_reason and payload.loss_reason.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Closing a deal as CLOSED_LOST requires a loss_reason.",
        )

    deal.stage = next_stage
    deal.probability_pct = STAGE_PROBABILITY[next_stage]
    deal.loss_reason = payload.loss_reason.strip() if next_stage == "CLOSED_LOST" and payload.loss_reason else None

    db.commit()
    db.refresh(deal)
    return deal


def get_pipeline_forecast(db: Session, company_id: int) -> PipelineForecastSummary:
    """Compute unweighted and probability-weighted open pipeline forecast for a tenant."""
    open_deals = list(
        db.scalars(
            select(CrmOpportunityDeal).where(
                CrmOpportunityDeal.company_id == company_id,
                CrmOpportunityDeal.stage.notin_(list(CLOSED_STAGES)),
            )
        ).all()
    )
    total_pipeline = Decimal("0.00")
    weighted_total = Decimal("0.00")

    for deal in open_deals:
        amt = Decimal(str(deal.amount))
        prob = Decimal(deal.probability_pct) / Decimal("100")
        total_pipeline += amt
        weighted_total += amt * prob

    return PipelineForecastSummary(
        company_id=company_id,
        open_deals_count=len(open_deals),
        total_pipeline_amount=_round_money(total_pipeline),
        weighted_forecast_amount=_round_money(weighted_total),
    )
