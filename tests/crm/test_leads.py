from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.crm.leads import router as leads_router
from app.crm.leads.schemas import LeadCreate, LeadStatusUpdate, LeadUpdate


def test_create_lead_and_duplicate_company_phone_rejected(db_session, admin_user, other_tenant_admin):
    lead = leads_router.create_lead(
        payload=LeadCreate(
            company_name="Horizon Logistics",
            contact_name="Rohan Patel",
            phone="+91-9876543210",
            email="rohan@example.com",
            potential_value=Decimal("25000.00"),
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert lead.status == "NEW"
    assert lead.is_qualified is False

    # Same company + phone within same tenant -> 409
    with pytest.raises(HTTPException) as exc_info:
        leads_router.create_lead(
            payload=LeadCreate(
                company_name="horizon logistics",
                contact_name="Duplicate Person",
                phone="+91-9876543210",
            ),
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 409

    # Different tenant isolated -> succeeds
    other_lead = leads_router.create_lead(
        payload=LeadCreate(
            company_name="Horizon Logistics",
            contact_name="Rohan Patel",
            phone="+91-9876543210",
        ),
        db=db_session,
        current_user=other_tenant_admin,
    )
    assert other_lead.company_id == other_tenant_admin.company_id


def test_lead_status_transitions_and_lost_reason_requirement(db_session, admin_user):
    lead = leads_router.create_lead(
        payload=LeadCreate(
            company_name="Apex Retail",
            contact_name="Meera Shah",
            phone="+91-9000011111",
        ),
        db=db_session,
        current_user=admin_user,
    )

    # LOST without reason -> 400
    with pytest.raises(HTTPException) as exc_info:
        leads_router.move_lead_status(
            lead_id=lead.id,
            payload=LeadStatusUpdate(status="LOST", lost_reason="   "),
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 400

    qualified = leads_router.move_lead_status(
        lead_id=lead.id,
        payload=LeadStatusUpdate(status="QUALIFIED"),
        db=db_session,
        current_user=admin_user,
    )
    assert qualified.status == "QUALIFIED"
    assert qualified.is_qualified is True

    won = leads_router.move_lead_status(
        lead_id=lead.id,
        payload=LeadStatusUpdate(status="WON"),
        db=db_session,
        current_user=admin_user,
    )
    assert won.status == "WON"

    # WON lead cannot be deleted
    with pytest.raises(HTTPException) as del_exc:
        leads_router.delete_lead(lead_id=lead.id, db=db_session, current_user=admin_user)
    assert del_exc.value.status_code == 409


def test_update_lead_and_tenant_isolation(db_session, admin_user, other_tenant_admin):
    lead = leads_router.create_lead(
        payload=LeadCreate(
            company_name="BlueSky Tech",
            contact_name="Ananya Rao",
            phone="+91-9123456789",
        ),
        db=db_session,
        current_user=admin_user,
    )
    updated = leads_router.update_lead(
        lead_id=lead.id,
        payload=LeadUpdate(potential_value=Decimal("42000.00")),
        db=db_session,
        current_user=admin_user,
    )
    assert updated.potential_value == Decimal("42000.00")

    with pytest.raises(HTTPException) as exc_info:
        leads_router.get_lead(lead_id=lead.id, db=db_session, current_user=other_tenant_admin)
    assert exc_info.value.status_code == 404
