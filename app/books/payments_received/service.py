from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.books.invoices.models import BooksInvoice
from app.books.payments_received.models import BooksPaymentAllocation, BooksPaymentReceived
from app.books.payments_received.schemas import PaymentReceivedCreate, PaymentReceivedUpdate

CHEQUE_TRANSITIONS: Dict[str, str] = {
    "RECEIVED": "DEPOSITED",
    "DEPOSITED": "CLEARED",
    "CLEARED": "APPROVED",
}


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_payment(
    db: Session,
    company_id: int,
    payload: PaymentReceivedCreate,
) -> BooksPaymentReceived:
    """Create a tenant-scoped payment received; cheques enter RECEIVED, others PENDING."""
    dup = db.scalar(
        select(BooksPaymentReceived).where(
            BooksPaymentReceived.company_id == company_id,
            BooksPaymentReceived.payment_number == payload.payment_number,
        )
    )
    if dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment '{payload.payment_number}' already exists.",
        )

    initial_status = "RECEIVED" if payload.payment_mode == "CHEQUE" else "PENDING"
    payment = BooksPaymentReceived(
        company_id=company_id,
        payment_number=payload.payment_number,
        customer_name=payload.customer_name,
        payment_mode=payload.payment_mode,
        status=initial_status,
        amount=_round_money(payload.amount),
        unused_amount=_round_money(payload.amount),
        payment_date=payload.payment_date,
        reference_number=payload.reference_number.strip() if payload.reference_number else None,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment '{payload.payment_number}' already exists.",
        )
    db.refresh(payment)
    return payment


def list_payments(db: Session, company_id: int) -> List[BooksPaymentReceived]:
    """List tenant-scoped payments received ordered newest first."""
    return list(
        db.scalars(
            select(BooksPaymentReceived)
            .where(BooksPaymentReceived.company_id == company_id)
            .order_by(BooksPaymentReceived.payment_date.desc(), BooksPaymentReceived.id.desc())
        ).all()
    )


def get_payment(db: Session, company_id: int, payment_id: int) -> BooksPaymentReceived:
    """Fetch a tenant-scoped payment or raise 404."""
    payment = db.scalar(
        select(BooksPaymentReceived).where(
            BooksPaymentReceived.id == payment_id,
            BooksPaymentReceived.company_id == company_id,
        )
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found.",
        )
    return payment


def update_pending_payment(
    db: Session,
    company_id: int,
    payment_id: int,
    payload: PaymentReceivedUpdate,
) -> BooksPaymentReceived:
    """Allow edits only while payment is PENDING."""
    payment = get_payment(db, company_id, payment_id)
    if payment.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only PENDING payments can be edited (current status: '{payment.status}').",
        )

    if payload.amount is not None:
        applied = Decimal(str(payment.amount)) - Decimal(str(payment.unused_amount))
        new_amount = _round_money(payload.amount)
        if new_amount < applied:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Updated amount cannot be less than already allocated total.",
            )
        payment.amount = new_amount
        payment.unused_amount = _round_money(new_amount - applied)

    if payload.payment_date is not None:
        payment.payment_date = payload.payment_date
    if payload.payment_mode is not None:
        payment.payment_mode = payload.payment_mode
    if payload.reference_number is not None:
        payment.reference_number = payload.reference_number.strip()

    db.commit()
    db.refresh(payment)
    return payment


def advance_payment_status(db: Session, company_id: int, payment_id: int) -> BooksPaymentReceived:
    """Advance payment status (cheques: RECEIVED -> DEPOSITED -> CLEARED -> APPROVED)."""
    payment = get_payment(db, company_id, payment_id)
    if payment.payment_mode == "CHEQUE":
        next_status = CHEQUE_TRANSITIONS.get(payment.status)
        if not next_status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cheque payment cannot advance from '{payment.status}'.",
            )
        payment.status = next_status
    else:
        if payment.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment in '{payment.status}' status cannot be approved again.",
            )
        payment.status = "APPROVED"

    db.commit()
    db.refresh(payment)
    return payment


def auto_pay_invoices(
    db: Session,
    company_id: int,
    payment_id: int,
) -> List[BooksPaymentAllocation]:
    """
    Allocate unused balance of an APPROVED payment to the customer's oldest due
    open invoices within the same tenant.
    """
    payment = get_payment(db, company_id, payment_id)
    if payment.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment must be APPROVED before allocating to invoices.",
        )
    remaining = Decimal(str(payment.unused_amount))
    if remaining <= Decimal("0.00"):
        return []

    open_invoices = list(
        db.scalars(
            select(BooksInvoice)
            .where(
                BooksInvoice.company_id == company_id,
                BooksInvoice.customer_name == payment.customer_name,
                BooksInvoice.status.in_(["ISSUED", "PARTIALLY_PAID"]),
                BooksInvoice.balance_due > Decimal("0.00"),
            )
            .order_by(BooksInvoice.due_date.asc(), BooksInvoice.id.asc())
        ).all()
    )

    allocations: List[BooksPaymentAllocation] = []
    for inv in open_invoices:
        if remaining <= Decimal("0.00"):
            break
        balance = Decimal(str(inv.balance_due))
        to_apply = _round_money(min(remaining, balance))
        if to_apply <= Decimal("0.00"):
            continue

        alloc = BooksPaymentAllocation(
            company_id=company_id,
            payment_id=payment.id,
            invoice_id=inv.id,
            amount_applied=to_apply,
        )
        db.add(alloc)
        allocations.append(alloc)

        new_balance = _round_money(balance - to_apply)
        inv.balance_due = new_balance
        inv.status = "PAID" if new_balance == Decimal("0.00") else "PARTIALLY_PAID"
        remaining = _round_money(remaining - to_apply)

    payment.unused_amount = remaining
    db.commit()
    for alloc in allocations:
        db.refresh(alloc)
    return allocations
