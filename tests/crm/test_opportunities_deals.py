from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.crm.opportunities_deals import router as deals_router
from app.crm.opportunities_deals.schemas import (
    OpportunityDealCreate,
    OpportunityDealUpdate,
    OpportunityStageTransition,
)


def test_opportunity_pipeline_and_weighted_forecast(db_session, admin_user, other_tenant_admin):
    d1 = deals_router.create_opportunity_deal(
        payload=OpportunityDealCreate(
            deal_name="Enterprise Rollout",
            account_name="Orion Systems",
            amount=Decimal("10000.00"),
            expected_close_date=date(2026, 12, 15),
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert d1.stage == "PROSPECTING"
    assert d1.probability_pct == 10

    d2 = deals_router.create_opportunity_deal(
        payload=OpportunityDealCreate(
            deal_name="Annual Support Renewal",
            account_name="Orion Systems",
            amount=Decimal("4000.00"),
            expected_close_date=date(2026, 12, 20),
        ),
        db=db_session,
        current_user=admin_user,
    )
    d2 = deals_router.transition_opportunity_stage(
        deal_id=d2.id,
        payload=OpportunityStageTransition(stage="NEGOTIATION"),
        db=db_session,
        current_user=admin_user,
    )
    assert d2.probability_pct == 75

    forecast = deals_router.get_pipeline_forecast(db=db_session, current_user=admin_user)
    assert forecast.open_deals_count == 2
    assert forecast.total_pipeline_amount == Decimal("14000.00")
    # 10000 * 10% + 4000 * 75% = 1000 + 3000 = 4000.00
    assert forecast.weighted_forecast_amount == Decimal("4000.00")

    # Tenant isolation
    with pytest.raises(HTTPException) as exc_info:
        deals_router.get_opportunity_deal(
            deal_id=d1.id,
            db=db_session,
            current_user=other_tenant_admin,
        )
    assert exc_info.value.status_code == 404


def test_closed_deal_immutability_and_loss_reason_validation(db_session, admin_user):
    deal = deals_router.create_opportunity_deal(
        payload=OpportunityDealCreate(
            deal_name="Mid-Market Deal",
            account_name="Zenith Retail",
            amount=Decimal("5000.00"),
            expected_close_date=date(2026, 12, 30),
        ),
        db=db_session,
        current_user=admin_user,
    )

    # CLOSED_LOST requires loss_reason
    with pytest.raises(HTTPException) as bad_loss:
        deals_router.transition_opportunity_stage(
            deal_id=deal.id,
            payload=OpportunityStageTransition(stage="CLOSED_LOST"),
            db=db_session,
            current_user=admin_user,
        )
    assert bad_loss.value.status_code == 400

    closed = deals_router.transition_opportunity_stage(
        deal_id=deal.id,
        payload=OpportunityStageTransition(stage="CLOSED_WON"),
        db=db_session,
        current_user=admin_user,
    )
    assert closed.stage == "CLOSED_WON"
    assert closed.probability_pct == 100

    # Closed deal cannot be edited or re-transitioned
    with pytest.raises(HTTPException) as edit_exc:
        deals_router.update_opportunity_deal(
            deal_id=deal.id,
            payload=OpportunityDealUpdate(amount=Decimal("6000.00")),
            db=db_session,
            current_user=admin_user,
        )
    assert edit_exc.value.status_code == 409

    with pytest.raises(HTTPException) as trans_exc:
        deals_router.transition_opportunity_stage(
            deal_id=deal.id,
            payload=OpportunityStageTransition(stage="PROPOSAL"),
            db=db_session,
            current_user=admin_user,
        )
    assert trans_exc.value.status_code == 409
