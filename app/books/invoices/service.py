from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.books.invoices.models import BooksInvoice, BooksInvoiceLine
from app.books.invoices.schemas import InvoiceCreate, InvoiceLineCreate, InvoiceUpdate


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_invoice_totals(
    lines: List[InvoiceLineCreate],
) -> Tuple[Decimal, Decimal, Decimal, List[Tuple[InvoiceLineCreate, Decimal]]]:
    """Compute subtotal, GST/tax total, grand total, and per-line totals."""
    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")
    computed_lines: List[Tuple[InvoiceLineCreate, Decimal]] = []

    for line in lines:
        line_sub = _round_money(line.quantity * line.unit_price)
        line_tax = _round_money((line_sub * line.tax_rate_pct) / Decimal("100"))
        line_total = _round_money(line_sub + line_tax)
        subtotal += line_sub
        tax_amount += line_tax
        computed_lines.append((line, line_total))

    grand_total = _round_money(subtotal + tax_amount)
    return _round_money(subtotal), _round_money(tax_amount), grand_total, computed_lines


def create_invoice(db: Session, company_id: int, payload: InvoiceCreate) -> BooksInvoice:
    """Create a tenant-scoped BOOKS invoice with calculated line totals and taxes."""
    existing = db.scalar(
        select(BooksInvoice).where(
            BooksInvoice.company_id == company_id,
            BooksInvoice.invoice_number == payload.invoice_number,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice '{payload.invoice_number}' already exists.",
        )

    subtotal, tax_amount, total_amount, computed_lines = compute_invoice_totals(payload.lines)
    invoice = BooksInvoice(
        company_id=company_id,
        invoice_number=payload.invoice_number,
        customer_name=payload.customer_name,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        balance_due=total_amount,
        status="ISSUED",
    )
    for line, line_total in computed_lines:
        invoice.lines.append(
            BooksInvoiceLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate_pct=line.tax_rate_pct,
                line_total=line_total,
            )
        )

    db.add(invoice)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice '{payload.invoice_number}' already exists.",
        )
    db.refresh(invoice)
    return invoice


def list_invoices(
    db: Session,
    company_id: int,
    status_filter: Optional[str] = None,
) -> List[BooksInvoice]:
    """List tenant-scoped invoices ordered by due date ascending."""
    stmt = select(BooksInvoice).where(BooksInvoice.company_id == company_id)
    if status_filter:
        stmt = stmt.where(BooksInvoice.status == status_filter.strip().upper())
    return list(db.scalars(stmt.order_by(BooksInvoice.due_date.asc(), BooksInvoice.id.asc())).all())


def get_invoice(db: Session, company_id: int, invoice_id: int) -> BooksInvoice:
    """Fetch a single tenant-scoped invoice or raise 404."""
    invoice = db.scalar(
        select(BooksInvoice).where(
            BooksInvoice.id == invoice_id,
            BooksInvoice.company_id == company_id,
        )
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found.",
        )
    return invoice


def update_invoice(
    db: Session,
    company_id: int,
    invoice_id: int,
    payload: InvoiceUpdate,
) -> BooksInvoice:
    """Update an unpaid/partially-paid invoice; rejects edits on PAID or VOID invoices."""
    invoice = get_invoice(db, company_id, invoice_id)
    if invoice.status in ("PAID", "VOID"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit invoice in '{invoice.status}' status.",
        )

    if payload.customer_name is not None:
        invoice.customer_name = payload.customer_name.strip()

    if payload.due_date is not None:
        if payload.due_date < invoice.issue_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="due_date cannot be earlier than issue_date.",
            )
        invoice.due_date = payload.due_date

    if payload.lines is not None:
        paid_so_far = Decimal(str(invoice.total_amount)) - Decimal(str(invoice.balance_due))
        subtotal, tax_amount, total_amount, computed_lines = compute_invoice_totals(payload.lines)
        if total_amount < paid_so_far:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Updated total cannot be less than amount already paid.",
            )
        invoice.lines.clear()
        for line, line_total in computed_lines:
            invoice.lines.append(
                BooksInvoiceLine(
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_rate_pct=line.tax_rate_pct,
                    line_total=line_total,
                )
            )
        invoice.subtotal = subtotal
        invoice.tax_amount = tax_amount
        invoice.total_amount = total_amount
        invoice.balance_due = _round_money(total_amount - paid_so_far)

    db.commit()
    db.refresh(invoice)
    return invoice


def void_invoice(db: Session, company_id: int, invoice_id: int) -> BooksInvoice:
    """Void an invoice that has no applied payments."""
    invoice = get_invoice(db, company_id, invoice_id)
    if invoice.status == "VOID":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice is already void.",
        )
    paid_so_far = Decimal(str(invoice.total_amount)) - Decimal(str(invoice.balance_due))
    if paid_so_far > Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot void an invoice with applied payments.",
        )

    invoice.status = "VOID"
    invoice.balance_due = Decimal("0.00")
    db.commit()
    db.refresh(invoice)
    return invoice
