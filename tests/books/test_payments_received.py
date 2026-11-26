from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.books.invoices import router as invoices_router
from app.books.invoices.schemas import InvoiceCreate, InvoiceLineCreate
from app.books.payments_received import router as payments_router
from app.books.payments_received.schemas import PaymentReceivedCreate, PaymentReceivedUpdate


def _create_open_invoice(db_session, admin_user, inv_no: str, due: date, amount: Decimal):
    return invoices_router.create_invoice(
        payload=InvoiceCreate(
            invoice_number=inv_no,
            customer_name="Global Retailers",
            issue_date=date(2026, 11, 1),
            due_date=due,
            lines=[
                InvoiceLineCreate(
                    description="Services",
                    quantity=Decimal("1.00"),
                    unit_price=amount,
                    tax_rate_pct=Decimal("0.00"),
                )
            ],
        ),
        db=db_session,
        current_user=admin_user,
    )


def test_cheque_payment_transition_sequence(db_session, admin_user):
    cheque = payments_router.create_payment(
        payload=PaymentReceivedCreate(
            payment_number="PAY-CHQ-001",
            customer_name="Global Retailers",
            payment_mode="CHEQUE",
            amount=Decimal("500.00"),
            payment_date=date(2026, 11, 5),
            reference_number="CHQ-9911",
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert cheque.status == "RECEIVED"

    # Cannot edit non-PENDING payment
    with pytest.raises(HTTPException) as exc_info:
        payments_router.update_pending_payment(
            payment_id=cheque.id,
            payload=PaymentReceivedUpdate(amount=Decimal("600.00")),
            db=db_session,
            current_user=admin_user,
        )
    assert exc_info.value.status_code == 409

    for expected_status in ("DEPOSITED", "CLEARED", "APPROVED"):
        cheque = payments_router.advance_payment_status(
            payment_id=cheque.id,
            db=db_session,
            current_user=admin_user,
        )
        assert cheque.status == expected_status


def test_auto_pay_allocates_to_oldest_due_invoice_first(db_session, admin_user, other_tenant_admin):
    newer_inv = _create_open_invoice(db_session, admin_user, "INV-NEW", date(2026, 11, 25), Decimal("400.00"))
    older_inv = _create_open_invoice(db_session, admin_user, "INV-OLD", date(2026, 11, 10), Decimal("300.00"))

    payment = payments_router.create_payment(
        payload=PaymentReceivedCreate(
            payment_number="PAY-UPI-001",
            customer_name="Global Retailers",
            payment_mode="UPI",
            amount=Decimal("450.00"),
            payment_date=date(2026, 11, 12),
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert payment.status == "PENDING"

    # Must be APPROVED before auto-pay
    with pytest.raises(HTTPException) as exc_info:
        payments_router.auto_pay_invoices(payment_id=payment.id, db=db_session, current_user=admin_user)
    assert exc_info.value.status_code == 409

    # Edit pending payment amount before approving
    payment = payments_router.update_pending_payment(
        payment_id=payment.id,
        payload=PaymentReceivedUpdate(amount=Decimal("500.00")),
        db=db_session,
        current_user=admin_user,
    )
    assert payment.unused_amount == Decimal("500.00")

    payments_router.advance_payment_status(payment_id=payment.id, db=db_session, current_user=admin_user)
    allocations = payments_router.auto_pay_invoices(payment_id=payment.id, db=db_session, current_user=admin_user)

    assert len(allocations) == 2
    assert allocations[0].invoice_id == older_inv.id
    assert allocations[0].amount_applied == Decimal("300.00")
    assert allocations[1].invoice_id == newer_inv.id
    assert allocations[1].amount_applied == Decimal("200.00")

    refreshed_old = invoices_router.get_invoice(invoice_id=older_inv.id, db=db_session, current_user=admin_user)
    refreshed_new = invoices_router.get_invoice(invoice_id=newer_inv.id, db=db_session, current_user=admin_user)
    assert refreshed_old.status == "PAID"
    assert refreshed_old.balance_due == Decimal("0.00")
    assert refreshed_new.status == "PARTIALLY_PAID"
    assert refreshed_new.balance_due == Decimal("200.00")

    # Tenant isolation
    with pytest.raises(HTTPException) as tenant_exc:
        payments_router.get_payment(payment_id=payment.id, db=db_session, current_user=other_tenant_admin)
    assert tenant_exc.value.status_code == 404
