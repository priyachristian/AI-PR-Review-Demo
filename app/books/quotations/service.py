from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.books.quotations.models import BooksQuotation, BooksQuotationLine
from app.books.quotations.schemas import (
    BooksQuotationCreate,
    BooksQuotationUpdate,
    QuotationLineCreate,
)

ALLOWED_QUOTATION_TRANSITIONS: Dict[str, Set[str]] = {
    "DRAFT": {"SENT", "CANCELLED"},
    "SENT": {"ACCEPTED", "REJECTED", "EXPIRED", "CANCELLED"},
    "ACCEPTED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
    "CANCELLED": set(),
}


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_quotation_totals(
    lines: List[QuotationLineCreate],
    discount_amount: Decimal,
) -> Tuple[Decimal, Decimal, Decimal, List[Tuple[QuotationLineCreate, Decimal]]]:
    """Compute subtotal, tax after discount validation, and grand total."""
    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")
    computed_lines: List[Tuple[QuotationLineCreate, Decimal]] = []

    for line in lines:
        line_sub = _round_money(line.quantity * line.unit_price)
        line_tax = _round_money((line_sub * line.tax_rate_pct) / Decimal("100"))
        line_total = _round_money(line_sub + line_tax)
        subtotal += line_sub
        tax_amount += line_tax
        computed_lines.append((line, line_total))

    subtotal = _round_money(subtotal)
    tax_amount = _round_money(tax_amount)
    discount = _round_money(discount_amount)
    if discount > subtotal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount amount cannot exceed quotation subtotal.",
        )

    grand_total = _round_money((subtotal - discount) + tax_amount)
    return subtotal, tax_amount, grand_total, computed_lines


def create_quotation(
    db: Session,
    company_id: int,
    payload: BooksQuotationCreate,
) -> BooksQuotation:
    """Create a tenant-scoped BOOKS quotation starting in DRAFT status."""
    dup = db.scalar(
        select(BooksQuotation).where(
            BooksQuotation.company_id == company_id,
            BooksQuotation.quote_number == payload.quote_number,
        )
    )
    if dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Quotation '{payload.quote_number}' already exists.",
        )

    subtotal, tax_amount, grand_total, computed_lines = compute_quotation_totals(
        payload.lines,
        payload.discount_amount,
    )
    quotation = BooksQuotation(
        company_id=company_id,
        quote_number=payload.quote_number,
        customer_name=payload.customer_name,
        quote_date=payload.quote_date,
        expiry_date=payload.expiry_date,
        subtotal=subtotal,
        discount_amount=_round_money(payload.discount_amount),
        tax_amount=tax_amount,
        total_amount=grand_total,
        status="DRAFT",
    )
    for line, line_total in computed_lines:
        quotation.lines.append(
            BooksQuotationLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate_pct=line.tax_rate_pct,
                line_total=line_total,
            )
        )

    db.add(quotation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Quotation '{payload.quote_number}' already exists.",
        )
    db.refresh(quotation)
    return quotation


def list_quotations(
    db: Session,
    company_id: int,
    status_filter: Optional[str] = None,
) -> List[BooksQuotation]:
    """List tenant-scoped BOOKS quotations."""
    stmt = select(BooksQuotation).where(BooksQuotation.company_id == company_id)
    if status_filter:
        stmt = stmt.where(BooksQuotation.status == status_filter.strip().upper())
    return list(db.scalars(stmt.order_by(BooksQuotation.quote_date.desc(), BooksQuotation.id.desc())).all())


def get_quotation(db: Session, company_id: int, quotation_id: int) -> BooksQuotation:
    """Fetch a tenant-scoped BOOKS quotation or raise 404."""
    quotation = db.scalar(
        select(BooksQuotation).where(
            BooksQuotation.id == quotation_id,
            BooksQuotation.company_id == company_id,
        )
    )
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quotation {quotation_id} not found.",
        )
    return quotation


def update_quotation(
    db: Session,
    company_id: int,
    quotation_id: int,
    payload: BooksQuotationUpdate,
) -> BooksQuotation:
    """Allow edits only while quotation is DRAFT or SENT."""
    quotation = get_quotation(db, company_id, quotation_id)
    if quotation.status not in ("DRAFT", "SENT"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit quotation in '{quotation.status}' status.",
        )

    if payload.customer_name is not None:
        quotation.customer_name = payload.customer_name.strip()

    if payload.expiry_date is not None:
        if payload.expiry_date < quotation.quote_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="expiry_date cannot be earlier than quote_date.",
            )
        quotation.expiry_date = payload.expiry_date

    target_discount = (
        payload.discount_amount
        if payload.discount_amount is not None
        else Decimal(str(quotation.discount_amount))
    )

    if payload.lines is not None:
        subtotal, tax_amount, grand_total, computed_lines = compute_quotation_totals(
            payload.lines,
            target_discount,
        )
        quotation.lines.clear()
        for line, line_total in computed_lines:
            quotation.lines.append(
                BooksQuotationLine(
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_rate_pct=line.tax_rate_pct,
                    line_total=line_total,
                )
            )
        quotation.subtotal = subtotal
        quotation.tax_amount = tax_amount
        quotation.discount_amount = _round_money(target_discount)
        quotation.total_amount = grand_total
    elif payload.discount_amount is not None:
        subtotal = Decimal(str(quotation.subtotal))
        tax_amount = Decimal(str(quotation.tax_amount))
        discount = _round_money(payload.discount_amount)
        if discount > subtotal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discount amount cannot exceed quotation subtotal.",
            )
        quotation.discount_amount = discount
        quotation.total_amount = _round_money((subtotal - discount) + tax_amount)

    db.commit()
    db.refresh(quotation)
    return quotation


def transition_quotation_status(
    db: Session,
    company_id: int,
    quotation_id: int,
    target_status: str,
    as_of_date: Optional[date] = None,
) -> BooksQuotation:
    """Transition quotation status using explicit state-machine rules and expiry check."""
    quotation = get_quotation(db, company_id, quotation_id)
    next_status = target_status.strip().upper()

    allowed = ALLOWED_QUOTATION_TRANSITIONS.get(quotation.status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition quotation from '{quotation.status}' to '{next_status}'.",
        )

    check_date = as_of_date or date.today()
    if next_status == "ACCEPTED" and check_date > quotation.expiry_date:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot accept an expired quotation.",
        )

    quotation.status = next_status
    db.commit()
    db.refresh(quotation)
    return quotation
