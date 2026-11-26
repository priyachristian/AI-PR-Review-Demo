from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.books.quotations import router as quotations_router
from app.books.quotations.schemas import BooksQuotationCreate, BooksQuotationUpdate, QuotationLineCreate
from app.books.quotations.service import transition_quotation_status


def _sample_quote(quote_number: str = "QT-2026-001", expiry_offset: int = 10) -> BooksQuotationCreate:
    qdate = date(2026, 11, 1)
    return BooksQuotationCreate(
        quote_number=quote_number,
        customer_name="Summit Manufacturing",
        quote_date=qdate,
        expiry_date=qdate + timedelta(days=expiry_offset),
        discount_amount=Decimal("50.00"),
        lines=[
            QuotationLineCreate(
                description="ERP Annual License",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                tax_rate_pct=Decimal("18.00"),
            )
        ],
    )


def test_create_and_update_books_quotation(db_session, admin_user, other_tenant_admin):
    quote = quotations_router.create_quotation(
        payload=_sample_quote(),
        db=db_session,
        current_user=admin_user,
    )
    assert quote.status == "DRAFT"
    assert quote.subtotal == Decimal("1000.00")
    assert quote.discount_amount == Decimal("50.00")
    assert quote.tax_amount == Decimal("180.00")
    assert quote.total_amount == Decimal("1130.00")

    updated = quotations_router.update_quotation(
        quotation_id=quote.id,
        payload=BooksQuotationUpdate(discount_amount=Decimal("100.00")),
        db=db_session,
        current_user=admin_user,
    )
    assert updated.total_amount == Decimal("1080.00")

    # Tenant isolation
    with pytest.raises(HTTPException) as exc_info:
        quotations_router.get_quotation(
            quotation_id=quote.id,
            db=db_session,
            current_user=other_tenant_admin,
        )
    assert exc_info.value.status_code == 404


def test_quotation_discount_exceeding_subtotal_rejected(db_session, admin_user):
    bad_quote = _sample_quote("QT-BAD-DISC")
    bad_quote.discount_amount = Decimal("1500.00")
    with pytest.raises(HTTPException) as exc_info:
        quotations_router.create_quotation(payload=bad_quote, db=db_session, current_user=admin_user)
    assert exc_info.value.status_code == 400


def test_quotation_status_transitions_and_expiry_guard(db_session, admin_user):
    quote = quotations_router.create_quotation(
        payload=_sample_quote("QT-FLOW-01", expiry_offset=5),
        db=db_session,
        current_user=admin_user,
    )

    # Cannot jump directly from DRAFT to ACCEPTED
    with pytest.raises(HTTPException) as invalid_jump:
        transition_quotation_status(
            db=db_session,
            company_id=admin_user.company_id,
            quotation_id=quote.id,
            target_status="ACCEPTED",
            as_of_date=date(2026, 11, 2),
        )
    assert invalid_jump.value.status_code == 409

    sent = transition_quotation_status(
        db=db_session,
        company_id=admin_user.company_id,
        quotation_id=quote.id,
        target_status="SENT",
    )
    assert sent.status == "SENT"

    # Cannot accept after expiry date
    with pytest.raises(HTTPException) as expired_exc:
        transition_quotation_status(
            db=db_session,
            company_id=admin_user.company_id,
            quotation_id=quote.id,
            target_status="ACCEPTED",
            as_of_date=date(2026, 11, 20),
        )
    assert expired_exc.value.status_code == 409

    accepted = transition_quotation_status(
        db=db_session,
        company_id=admin_user.company_id,
        quotation_id=quote.id,
        target_status="ACCEPTED",
        as_of_date=date(2026, 11, 4),
    )
    assert accepted.status == "ACCEPTED"
