from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.books.invoices import router as invoices_router
from app.books.invoices.schemas import InvoiceCreate, InvoiceLineCreate, InvoiceUpdate
from app.books.invoices.service import compute_invoice_totals, void_invoice


def _sample_invoice_payload(
    invoice_number: str = "INV-2026-001",
    customer_name: str = "Acme Trading Co",
    offset_days: int = 15,
) -> InvoiceCreate:
    issue = date(2026, 11, 1)
    return InvoiceCreate(
        invoice_number=invoice_number,
        customer_name=customer_name,
        issue_date=issue,
        due_date=issue + timedelta(days=offset_days),
        lines=[
            InvoiceLineCreate(
                description="Cloud Subscription",
                quantity=Decimal("2.00"),
                unit_price=Decimal("500.00"),
                tax_rate_pct=Decimal("18.00"),
            )
        ],
    )


def test_create_invoice_computes_totals_and_tenant_scope(db_session, admin_user, other_tenant_admin):
    created = invoices_router.create_invoice(
        payload=_sample_invoice_payload(),
        db=db_session,
        current_user=admin_user,
    )
    assert created.company_id == admin_user.company_id
    assert created.subtotal == Decimal("1000.00")
    assert created.tax_amount == Decimal("180.00")
    assert created.total_amount == Decimal("1180.00")
    assert created.balance_due == Decimal("1180.00")
    assert created.status == "ISSUED"

    # Cross-tenant isolation check
    with pytest.raises(HTTPException) as exc_info:
        invoices_router.get_invoice(
            invoice_id=created.id,
            db=db_session,
            current_user=other_tenant_admin,
        )
    assert exc_info.value.status_code == 404


def test_duplicate_invoice_number_rejected_within_same_tenant(db_session, admin_user, other_tenant_admin):
    invoices_router.create_invoice(
        payload=_sample_invoice_payload("INV-DUP-01"),
        db=db_session,
        current_user=admin_user,
    )
    with pytest.raises(HTTPException) as exc_info:
        invoices_router.create_invoice(
            payload=_sample_invoice_payload("INV-DUP-01"),
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 409

    # Different tenant can reuse same invoice number
    other = invoices_router.create_invoice(
        payload=_sample_invoice_payload("INV-DUP-01"),
        db=db_session,
        current_user=other_tenant_admin,
    )
    assert other.company_id == other_tenant_admin.company_id


def test_update_and_void_invoice_status_guards(db_session, admin_user):
    inv = invoices_router.create_invoice(
        payload=_sample_invoice_payload("INV-EDIT-01"),
        db=db_session,
        current_user=admin_user,
    )
    updated = invoices_router.update_invoice(
        invoice_id=inv.id,
        payload=InvoiceUpdate(
            lines=[
                InvoiceLineCreate(
                    description="Updated Tier",
                    quantity=Decimal("1.00"),
                    unit_price=Decimal("2000.00"),
                    tax_rate_pct=Decimal("10.00"),
                )
            ]
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert updated.total_amount == Decimal("2200.00")

    voided = void_invoice(db=db_session, company_id=admin_user.company_id, invoice_id=inv.id)
    assert voided.status == "VOID"
    assert voided.balance_due == Decimal("0.00")

    # Voided invoice cannot be edited
    with pytest.raises(HTTPException) as exc_info:
        invoices_router.update_invoice(
            invoice_id=inv.id,
            payload=InvoiceUpdate(customer_name="New Name"),
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 409


def test_compute_invoice_totals_pure_calculation():
    subtotal, tax, total, computed = compute_invoice_totals(
        [
            InvoiceLineCreate(
                description="Item A",
                quantity=Decimal("3.00"),
                unit_price=Decimal("100.00"),
                tax_rate_pct=Decimal("5.00"),
            ),
            InvoiceLineCreate(
                description="Item B",
                quantity=Decimal("1.00"),
                unit_price=Decimal("50.00"),
                tax_rate_pct=Decimal("10.00"),
            ),
        ]
    )
    assert subtotal == Decimal("350.00")
    assert tax == Decimal("20.00")
    assert total == Decimal("370.00")
    assert len(computed) == 2
